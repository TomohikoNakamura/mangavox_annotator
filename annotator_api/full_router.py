import argparse
import asyncio
import io
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from annotator_api.utils import (
    AppState,
    Constants,
    OutputData,
    PreLoadedData,
    apply_change_logs,
)
from mangavox_api.annotation_helper import MangaVoxForAnnotation

router = APIRouter()


# GET APIS, Different from main2.py
@router.get("/audio")
async def get_audio(request: Request):
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.audio_raw_data_dict is None:
        raise HTTPException(
            status_code=500,
            detail="Audio data not loaded. Please check the server logs.",
        )

    target_audio_raw_data = state.pre_loaded_data.audio_raw_data_dict["all"]

    headers = {
        "Content-Type": "audio/mpeg",  # MIME type. Assume MP3 format for audio data.
        "Content-Length": str(len(target_audio_raw_data)),
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        io.BytesIO(target_audio_raw_data),
        media_type="audio/mpeg",
        headers=headers,
    )


def pre_init(args: argparse.Namespace) -> AppState:
    """Pre-initialize the application by loading necessary data and applying change logs.

    Args:
        args (argparse.Namespace): Parsed command line arguments.

    Returns:
        AppState: An instance of AppState containing pre-loaded data, constants, and output data.
    """
    # Parse annotation XML file
    xml_file_path = args.aligned_voices_filename
    aligned_voices = MangaVoxForAnnotation.read(xml_file_path)
    # Check change logs
    if Path(args.change_log_dir / aligned_voices.title).exists():
        apply_logs = sorted(
            [
                _.parent
                for _ in Path(args.change_log_dir / aligned_voices.title).glob(
                    "*/change_log.yaml"
                )
            ]
        )
    else:
        apply_logs = []
    logger.info(f"Applying change logs: {apply_logs}")
    var_args = vars(args)
    var_args["apply_logs"] = apply_logs
    args = argparse.Namespace(**var_args)
    #
    aligned_voices = apply_change_logs(args.apply_logs, aligned_voices)
    #
    CONSTANTS = Constants(
        (
            0,
            max(
                [
                    v.page_index
                    for v in aligned_voices.voices
                    if v.page_index is not None
                ]
            ),
        ),
        args.image_root,
    )

    # Load audio data
    audio_path = args.audio_filename
    if args.audio_filename.suffix[1:] != "mp3":
        # If not mp3 file, convert to mp3
        logger.info(
            f"Converting audio file to MP3 format for compatibility. Given: {args.audio_filename.suffix}"
        )
        mp3_fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        mp3_file_path = Path(mp3_fp.name)
        mp3_fp.close()
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(args.audio_filename), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_file_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        audio_path = mp3_file_path
        logger.info(f"Converted audio file saved at: {audio_path}")
        # raise ValueError(
        #     f"Audio file must be in MP3 format. Given: {args.audio_filename.suffix}"
        # )
    with open(audio_path, "rb") as fp:
        audio_raw_data = fp.read()

    # Load image data
    image_data = []
    for i in range(CONSTANTS.PAGE_RANGE[0], CONSTANTS.PAGE_RANGE[1] + 1):
        image_path = CONSTANTS.IMAGE_ROOT / f"{i:03d}.jpg"
        with open(image_path, "rb") as fp:
            image_data.append(fp.read())

    PRE_LOADED_DATA = PreLoadedData(
        aligned_voices,
        {
            "all": audio_raw_data
        },  # Dictionary with a single key "all" for all audio data
        image_data,
        None,
        None,
    )

    change_log_filename = (
        args.change_log_dir
        / aligned_voices.title
        / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        / "change_log.yaml"
    )
    change_log_filename.parent.mkdir(parents=True, exist_ok=True)
    if change_log_filename.exists():
        raise FileExistsError(f"Change log file already exists: {change_log_filename}")
    # Write meta data for reproducibility
    with open(change_log_filename.parent / "config.yaml", "w", encoding="utf-8") as fp:
        yaml.dump(
            {
                "aligned_voices_filename": str(args.aligned_voices_filename),
                "audio_filename": str(args.audio_filename),
                "apply_logs": [str(log) for log in args.apply_logs],
                "annotation_version": {
                    "created": aligned_voices.created,
                    "last_modified": aligned_voices.last_modified,
                },
            },
            fp,
            allow_unicode=True,
            encoding="utf-8",
        )

    OUTPUT_DATA = OutputData(change_log_filename, asyncio.Lock())
    return AppState(
        pre_loaded_data=PRE_LOADED_DATA,
        constants=CONSTANTS,
        output_data=OUTPUT_DATA,
    )
