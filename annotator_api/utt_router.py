import argparse
import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy
import soundfile as sf  # type: ignore
import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from tqdm import tqdm

from annotator_api.utils import (
    AppState,
    Constants,
    OutputData,
    PreLoadedData,
    apply_change_logs,
    wrap_audio_data,
)
from mangavox_api.annotation_helper import ExtendedVoice, MangaVoxForAnnotation

router = APIRouter()


# Utilities
def _check_and_clip_utterances_from_audio(
    character_name: str,
    voices: List[ExtendedVoice],
    audio_raw_data: bytes,
    margins: List[float] = [0.5, 0.5],
) -> Tuple[str, List[Optional[Tuple[numpy.ndarray, int]]]]:
    """Check and clip utterances from audio data for a specific character.

    Args:
        character_name (str): Name of the character.
        voices (List[ExtendedVoice]): List of voice elements.
        audio_raw_data (bytes): Raw audio data for the character.
        margins (List[float]): Margins to apply to the start and end times of the voices. [s]

    Returns:
        Tuple[str, List[Optional[Tuple[numpy.ndarray, int]]]]: Character name and a list of clipped audio data tuples (audio data, sample rate) or None for silent sections.
    """
    clipped_audio_list: List[Optional[Tuple[numpy.ndarray, int]]] = []
    with sf.SoundFile(io.BytesIO(audio_raw_data)) as audio_file:
        n_frames = audio_file.frames
        sample_rate = audio_file.samplerate
        for voice in voices:
            # convert time in second to frame index
            start = max(0, int(voice.start * sample_rate))
            end = min(n_frames, int(voice.end * sample_rate))
            if start >= end:
                raise ValueError(
                    f"Invalid start and end time. [start: {start / sample_rate}, end: {end / sample_rate}]"
                )
            # read audio data
            audio_file.seek(start)
            data = audio_file.read(end - start)
            is_silent = numpy.abs(data).max() == 0
            if is_silent:
                # if the audio is silent, append None
                clipped_audio_list.append(None)
            else:
                # Clip audio data with margins
                start = max(0, int((voice.start - margins[0]) * sample_rate))
                end = min(n_frames, int((voice.end + margins[1]) * sample_rate))
                if start >= end:
                    raise ValueError(
                        f"Invalid start and end time. [start: {start / sample_rate}, end: {end / sample_rate}]"
                    )
                # read audio data
                audio_file.seek(start)
                data = audio_file.read(end - start)
                clipped_audio_list.append((data, sample_rate))
    assert len(clipped_audio_list) == len(voices)
    return character_name, clipped_audio_list


def check_and_clip_utterances_from_audio(
    aligned_voices: MangaVoxForAnnotation, audio_raw_data_dict: Dict[str, bytes]
) -> Tuple[
    Dict[str, List[str]], Dict[str, Dict[str, Optional[Tuple[numpy.ndarray, int]]]]
]:
    """Check and clip utterances from audio data for each character.

    Args:
        aligned_voices (MangaVoxForAnnotation): MangaVoxForAnnotation object
        audio_raw_data_dict (Dict[str, bytes]): Dictionary of character_name -> audio_raw_data

    Returns:
        Tuple[Dict[str, List[str]], Dict[str, Dict[str, Optional[Tuple[numpy.ndarray, int]]]]]:
            - voice_existence_dict: Dictionary of voice_id -> list of active character_name
            - resultant_clipped_voices: Dictionary of voice_id -> Dictionary of character_name -> (audio data, sample rate) or None for silent sections
    """
    # voice_id -> list of active character_name
    character_name_list: List[str] = []
    clipped_voice_list: List[List[Optional[Tuple[numpy.ndarray, int]]]] = []
    with ThreadPoolExecutor() as executor:
        results = []
        for character_name, audio_raw_data in audio_raw_data_dict.items():
            results.append(
                executor.submit(
                    _check_and_clip_utterances_from_audio,
                    character_name,
                    aligned_voices.voices,
                    audio_raw_data,
                )
            )
        for r in tqdm(results, desc="Clipping audio"):
            clipped_voices: List[Optional[Tuple[numpy.ndarray, int]]] = []
            character_name, clipped_voices = r.result()
            character_name_list.append(character_name)  # num. characters
            clipped_voice_list.append(clipped_voices)  # num. characters x num. voices

    voice_existence_dict: Dict[str, List[str]] = dict()
    resultant_clipped_voices: Dict[
        str, Dict[str, Optional[Tuple[numpy.ndarray, int]]]
    ] = dict()
    for voice_index in range(len(aligned_voices.voices)):
        voice_id = aligned_voices.voices[voice_index].id
        active_characters = []
        _clipped_voices: Dict[str, Optional[Tuple[numpy.ndarray, int]]] = dict()
        for character_index in range(len(character_name_list)):
            character_name = character_name_list[character_index]
            if clipped_voice_list[character_index][voice_index] is not None:
                active_characters.append(character_name)
                _clipped_voices[character_name] = clipped_voice_list[character_index][
                    voice_index
                ]
        voice_existence_dict[voice_id] = active_characters
        resultant_clipped_voices[voice_id] = _clipped_voices
    return voice_existence_dict, resultant_clipped_voices


# GET APIs
@router.get("/audio/{character_name}")
async def get_audio(character_name: str, request: Request) -> StreamingResponse:
    """Get the raw audio data for a specific character.

    Args:
        character_name (str): The name of the character for which to retrieve audio data.

    Returns:
        StreamingResponse: A streaming response containing the audio data in FLAC format.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if character_name not in state.pre_loaded_data.audio_raw_data_dict:
        raise HTTPException(status_code=404, detail="Character not found.")

    target_audio_raw_data = state.pre_loaded_data.audio_raw_data_dict[character_name]

    headers = {
        "Content-Type": "audio/flac",  # MIME type
        "Content-Length": str(len(target_audio_raw_data)),
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(
        io.BytesIO(target_audio_raw_data), media_type="audio/flac", headers=headers
    )


@router.get("/audio_characters/{voice_id}")
async def check_audio_existence(voice_id: str, request: Request) -> List[str]:
    """Check if a voice ID exists in the audio data.

    Args:
        voice_id (str): The ID of the voice to check.

    Returns:
        Dict[str, List[str]]: A dictionary containing the voice ID and a list of character names where the voice exists.
    """
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if state.pre_loaded_data.voice_existence_dict is None:
        raise HTTPException(status_code=500, detail="Voice existence data not loaded.")

    if voice_id not in state.pre_loaded_data.voice_existence_dict:
        raise HTTPException(status_code=404, detail=f"Voice ID '{voice_id}' not found.")

    return state.pre_loaded_data.voice_existence_dict[voice_id]


@router.get("/audio/{character_name}/{voice_id}")
async def get_audio_by_voice_id(
    character_name: str, voice_id: str, request: Request
) -> StreamingResponse:
    """Get the audio data for a specific character and voice ID.

    Args:
        character_name (str): The name of the character.
        voice_id (str): The ID of the voice to retrieve.

    Returns:
        StreamingResponse: A streaming response containing the audio data in WAV format."""
    state: AppState = request.app.state.app_data
    if state.pre_loaded_data is None:
        raise HTTPException(
            status_code=500,
            detail="Application state not initialized. Please check the server logs.",
        )
    if character_name not in state.pre_loaded_data.audio_raw_data_dict:
        raise HTTPException(status_code=404, detail="Character not found.")

    if state.pre_loaded_data.aligned_voices is None:
        raise HTTPException(status_code=500, detail="Annotation data not loaded.")

    if state.pre_loaded_data.clipped_voices is None:
        raise HTTPException(status_code=500, detail="Clipped audio data not loaded.")

    if character_name not in state.pre_loaded_data.clipped_voices[voice_id]:
        raise HTTPException(status_code=404, detail="Silent section")

    clipped_voice = state.pre_loaded_data.clipped_voices[voice_id][character_name]
    if clipped_voice is None:
        raise HTTPException(status_code=404, detail="Silent section")

    audio_data, sample_rate = clipped_voice
    buffer = wrap_audio_data(audio_data, sample_rate)
    # clip audio data from start to end
    headers = {
        "Content-Type": "audio/wav",  # MIME type
        "Content-Length": str(len(buffer.getbuffer())),
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Disable caching
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(buffer, media_type="audio/wav", headers=headers)


def load_audio_files(audio_dir: Path) -> Tuple[List[Dict[str, str]], Dict[str, bytes]]:
    """Load audio files from the specified directory.

    Args:
        audio_dir (Path): Path to the directory containing audio files.

    Returns:
        Tuple[List[Dict[str, str]], Dict[str, bytes]]: A tuple containing a list of dictionaries with character names and filenames, and a dictionary mapping character names to raw audio data.
    """
    audio_file_list = []
    audio_raw_data_dict = dict()
    title = audio_dir.name
    for filename in tqdm(
        sorted(list(audio_dir.glob("*.flac"))), desc="Loading audio files"
    ):
        character_name = "_".join(filename.stem.replace(title + "_", "").split("_")[1:])
        audio_file_list.append(
            dict(character_name=character_name, filename=str(filename))
        )
        with open(filename, "rb") as fp:
            audio_raw_data_dict[character_name] = fp.read()
    return audio_file_list, audio_raw_data_dict


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

    # Load audio files
    audio_file_list, audio_raw_data_dict = load_audio_files(args.audio_dir)
    # Clip utterances and precompute voice existence
    voice_existence_dict, clipped_audio = check_and_clip_utterances_from_audio(
        aligned_voices, audio_raw_data_dict
    )

    # Load images
    image_data = []
    for i in range(CONSTANTS.PAGE_RANGE[0], CONSTANTS.PAGE_RANGE[1] + 1):
        image_path = CONSTANTS.IMAGE_ROOT / f"{i:03d}.jpg"
        with open(image_path, "rb") as fp:
            image_data.append(fp.read())

    PRE_LOADED_DATA = PreLoadedData(
        aligned_voices,
        audio_raw_data_dict,
        image_data,
        voice_existence_dict,
        clipped_audio,
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
                "audio_file_list": audio_file_list,
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
        constants=CONSTANTS,
        pre_loaded_data=PRE_LOADED_DATA,
        output_data=OUTPUT_DATA,
    )
