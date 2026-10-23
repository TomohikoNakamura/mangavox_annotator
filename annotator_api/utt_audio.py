"""Audio clipping helpers for utterance-level annotation mode.

UTT mode serves short clips around a voice instead of the full audio stream.
These helpers keep the mapping between absolute annotation times and the
relative region drawn inside each clipped waveform in one place.

Copyright (C) 2025 National Institute of Advanced Industrial Science and Technology (AIST)
"""

import io
import math
from typing import Dict, List, Optional, Tuple, TypedDict

import numpy
import soundfile as sf  # type: ignore

from mangavox_api.annotation_helper import ExtendedVoice

DEFAULT_MARGINS = (0.5, 0.5)


class ClipMetadata(TypedDict):
    """Metadata needed by the frontend to draw an absolute-time voice region.

    clip_start/clip_end are absolute seconds in the source audio. region_start
    and region_end are seconds relative to the clipped audio returned to
    WaveSurfer.
    """

    character_name: str
    clip_start: float
    clip_end: float
    region_start: float
    region_end: float
    duration: float


def _validate_time_range(start: float, end: float) -> None:
    """Validate an annotation time range before converting it to samples."""

    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Start and end must be finite values.")
    if start < 0:
        raise ValueError("Start time must be non-negative.")
    if start >= end:
        raise ValueError(f"Invalid time range: {start} >= {end}")


def _time_to_frame(time: float, sample_rate: int) -> int:
    """Convert seconds to a sample index using nearest-sample rounding."""

    return round(time * sample_rate)


def clip_audio_range(
    character_name: str,
    audio_raw_data: bytes,
    start_time: float,
    end_time: float,
    margins: Tuple[float, float] = DEFAULT_MARGINS,
) -> Optional[Tuple[numpy.ndarray, int, ClipMetadata]]:
    """Clip a single utterance range from one character audio stream.

    The returned metadata maps the original absolute annotation time to the
    relative region shown inside the clipped audio.

    Returns None when the requested core utterance is silent for this character;
    the caller uses that to exclude the character from active audio candidates.
    """
    _validate_time_range(start_time, end_time)

    with sf.SoundFile(io.BytesIO(audio_raw_data)) as audio_file:
        n_frames = audio_file.frames
        sample_rate = audio_file.samplerate
        audio_duration = n_frames / sample_rate

        if start_time >= audio_duration:
            raise ValueError(
                f"Start time exceeds audio duration: {start_time} >= {audio_duration}"
            )

        core_start_frame = max(0, _time_to_frame(start_time, sample_rate))
        core_end_frame = min(n_frames, _time_to_frame(end_time, sample_rate))
        if core_start_frame >= core_end_frame:
            raise ValueError(
                "Invalid start and end time. "
                f"[start: {core_start_frame / sample_rate}, "
                f"end: {core_end_frame / sample_rate}]"
            )

        audio_file.seek(core_start_frame)
        core_data = audio_file.read(core_end_frame - core_start_frame)
        if numpy.abs(core_data).max() == 0:
            return None

        clip_start_frame = max(0, _time_to_frame(start_time - margins[0], sample_rate))
        clip_end_frame = min(
            n_frames, _time_to_frame(end_time + margins[1], sample_rate)
        )
        if clip_start_frame >= clip_end_frame:
            raise ValueError(
                "Invalid start and end time. "
                f"[start: {clip_start_frame / sample_rate}, "
                f"end: {clip_end_frame / sample_rate}]"
            )

        audio_file.seek(clip_start_frame)
        data = audio_file.read(clip_end_frame - clip_start_frame)

    clip_start = clip_start_frame / sample_rate
    clip_end = clip_end_frame / sample_rate
    duration = clip_end - clip_start
    metadata: ClipMetadata = {
        "character_name": character_name,
        "clip_start": clip_start,
        "clip_end": clip_end,
        "region_start": max(0.0, start_time - clip_start),
        "region_end": min(duration, end_time - clip_start),
        "duration": duration,
    }
    return data, sample_rate, metadata


def clip_voice_for_all_characters(
    voice: ExtendedVoice,
    audio_raw_data_dict: Dict[str, bytes],
    margins: Tuple[float, float] = DEFAULT_MARGINS,
) -> Tuple[
    List[str],
    Dict[str, Optional[Tuple[numpy.ndarray, int]]],
    Dict[str, ClipMetadata],
]:
    """Clip one voice against every available character audio stream.

    This is used both during UTT startup cache creation and after a saved
    start/end edit invalidates one cached voice. Only characters with non-silent
    audio in the requested interval are returned as active candidates.
    """

    active_characters: List[str] = []
    clipped_voices: Dict[str, Optional[Tuple[numpy.ndarray, int]]] = {}
    metadata_dict: Dict[str, ClipMetadata] = {}
    for character_name, audio_raw_data in audio_raw_data_dict.items():
        clipped = clip_audio_range(
            character_name,
            audio_raw_data,
            voice.start,
            voice.end,
            margins=margins,
        )
        if clipped is None:
            continue
        audio_data, sample_rate, metadata = clipped
        active_characters.append(character_name)
        clipped_voices[character_name] = (audio_data, sample_rate)
        metadata_dict[character_name] = metadata
    return active_characters, clipped_voices, metadata_dict
