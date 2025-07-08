import asyncio
import dataclasses
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy
import soundfile as sf  # type: ignore
import yaml
from fastapi import Request

from manga2voice_api.annotation_helper import MangaVoxForAnnotation


def generate_client_uid(request: Request) -> str:
    """Generate a unique client identifier based on the request's host and user-agent.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        str: A SHA-256 hash of the client data.
    """
    if request.client is None:
        raise ValueError("Request client is not available")
    client_data = f"{request.client.host}-{request.headers.get('user-agent', '')}"
    return hashlib.sha256(client_data.encode()).hexdigest()


def json_to_hash(json_data: dict) -> str:
    """Generate a SHA-256 hash from a JSON object.

    Args:
        json_data (dict): The JSON data to hash.

    Returns:
        str: A SHA-256 hash of the JSON data.
    """
    return hashlib.sha256(
        json.dumps(json_data, ensure_ascii=False).encode()
    ).hexdigest()


# Data containers
@dataclasses.dataclass(frozen=True)
class Constants:
    """Constants for the application.

    Attributes:
        PAGE_RANGE (Tuple[int, int]): Range of pages in the manga.
        IMAGE_ROOT (Path): Root directory for images.
    """

    PAGE_RANGE: Tuple[int, int]
    IMAGE_ROOT: Path


@dataclasses.dataclass
class PreLoadedData:
    """Pre-loaded data for the application.

    Attributes:
        aligned_voices (MangaVoxForAnnotation): Aligned voices data.
        audio_raw_data_dict (Dict[str, bytes]): Dictionary of character_name -> audio_raw_data
        image_data (List[bytes]): List of image data for each page.
        voice_existence_dict (Dict[str, List[str]]): Dictionary of voice_id -> list of active character_name
        clipped_voices (Dict[str, Dict[str, Tuple[numpy.ndarray, int]]]): Dictionary of voice_id -> character_name -> (audio data, sample rate)
    """

    aligned_voices: MangaVoxForAnnotation
    audio_raw_data_dict: Dict[str, bytes]
    image_data: List[bytes]
    voice_existence_dict: Dict[str, List[str]] | None
    clipped_voices: Dict[str, Dict[str, Optional[Tuple[numpy.ndarray, int]]]] | None


@dataclasses.dataclass
class OutputData:
    """Output data for the application.

    Attributes:
        change_log_filename (Optional[Path]): Path to the change log file.
        change_log_lock (Optional[asyncio.Lock]): Lock for managing concurrent access to the change log file.
    """

    change_log_filename: Path
    change_log_lock: asyncio.Lock


# App state class
@dataclasses.dataclass
class AppState:
    constants: Optional[Constants] = None
    pre_loaded_data: Optional[PreLoadedData] = None
    output_data: Optional[OutputData] = None

    def sanity_check(self) -> None:
        """Perform sanity checks on the app state.

        Raises:
            ValueError: If any of the required attributes are not set.
        """
        if self.constants is None:
            raise ValueError("Constants are not set in AppState")
        if self.pre_loaded_data is None:
            raise ValueError("Pre-loaded data is not set in AppState")
        if self.output_data is None:
            raise ValueError("Output data is not set in AppState")


# utility functions
def wrap_audio_data(data: numpy.ndarray, sample_rate: int) -> io.BytesIO:
    """Wrap audio data into a BytesIO object in WAV format.

    Args:
        data (numpy.ndarray): The audio data to wrap.
        sample_rate (int): The sample rate of the audio data.

    Returns:
        io.BytesIO: A BytesIO object containing the audio data in WAV format.
    """
    buffer = io.BytesIO()
    sf.write(buffer, data, sample_rate, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer


def validate_audio_id_for_voice_id(
    aligned_voices: MangaVoxForAnnotation, voice_existence_dict: Dict[str, List[str]]
) -> List[str]:
    """
    Check if audio_id in the voice is in the list of active characters.

    Args:
        aligned_voices (MangaVoxForAnnotation): MangaVoxForAnnotation object
        voice_existence_dict (Dict[str, List[str]]): Dictionary of voice_id -> list of active character_name

    Returns:
        List[str]: List of voice_id that has incorrect audio_id
    """
    incorrect_voice_ids = []
    for voice in aligned_voices.voices:
        if voice.audio_id:  # if audio_id is not None
            # check if audio_id is in the list of active characters
            if voice.audio_id not in voice_existence_dict[voice.id]:
                incorrect_voice_ids.append(voice.id)
    return incorrect_voice_ids


def apply_change_logs(
    change_log_file_list: List[Path], aligned_voices: MangaVoxForAnnotation
) -> MangaVoxForAnnotation:
    """Apply change logs to the aligned voices data.

    Args:
        change_log_file_list (List[Path]): List of paths to change log directories.
        aligned_voices (MangaVoxForAnnotation): The MangaVoxForAnnotation object to apply changes to

    Returns:
        MangaVoxForAnnotation: The updated MangaVoxForAnnotation object after applying the change logs.
    """
    change_logs = []
    for change_log_dir in change_log_file_list:
        if not change_log_dir.is_dir():
            continue
        # Check config data for checking the version mismatch
        with open(change_log_dir / "config.yaml", "r") as fp:
            config_data = yaml.safe_load(fp.read())
        aligned_voices.check_change_applicability(config_data)
        #
        change_log_filename = change_log_dir / "change_log.yaml"
        with open(change_log_filename, "r") as fp:
            change_logs += yaml.safe_load(fp.read())
    change_logs = sorted(
        change_logs, key=lambda x: datetime.fromisoformat(x["timestamp"])
    )
    aligned_voices.apply_change_logs(change_logs)
    aligned_voices.update_assigned()
    return aligned_voices
