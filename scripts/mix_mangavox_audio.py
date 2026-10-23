# Copyright (C) 2025 National Institute of Advanced Industrial Science and Technology (AIST)

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import soundfile as sf  # type: ignore
from loguru import logger

from config import GAYA_UTT_GAINS_IN_DB, MANGA_TITLES

DEFAULT_AUDIO_ROOT = Path("data/manga2voice/concatenated_voices")
DEFAULT_OUTPUT_ROOT = Path("data/manga2voice/voices")
DEFAULT_XML_ROOT = Path("data/workspace")
DEFAULT_XML_SUFFIX = "_v1.xml"
DEFAULT_BACKGROUND_GAIN_DB = -40.0
DEFAULT_GAYA_MARGIN_SECONDS = 0.1
DEFAULT_TARGET_PEAK_DBFS = -1.0
GayaRange = tuple[float, float, float, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mix per-character MangaVox FLAC tracks into an ALL FLAC file."
    )
    parser.add_argument(
        "titles",
        nargs="*",
        default=MANGA_TITLES,
        help="Manga titles. Defaults to every title in config.py.",
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=DEFAULT_AUDIO_ROOT,
        help="Root containing <title> directories.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for <title>_ALL.flac.",
    )
    parser.add_argument(
        "--background-gain-db",
        type=float,
        default=DEFAULT_BACKGROUND_GAIN_DB,
        help=(
            "Default gain applied to *_Gaya.flac tracks outside configured "
            "voice-id ranges."
        ),
    )
    parser.add_argument(
        "--xml-root",
        type=Path,
        default=DEFAULT_XML_ROOT,
        help="Root containing <title><xml-suffix> annotation XML files.",
    )
    parser.add_argument(
        "--xml-suffix",
        default=DEFAULT_XML_SUFFIX,
        help="Annotation XML suffix used with --xml-root.",
    )
    parser.add_argument(
        "--gaya-margin-seconds",
        type=float,
        default=DEFAULT_GAYA_MARGIN_SECONDS,
        help="Time margin added before and after configured Gaya voice ranges.",
    )
    parser.add_argument(
        "--target-peak-dbfs",
        type=float,
        default=DEFAULT_TARGET_PEAK_DBFS,
        help="Maximum output sample peak in dBFS.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output file.",
    )
    return parser.parse_args()


def load_track(path: Path) -> tuple[np.ndarray, int, int]:
    data, sample_rate = sf.read(path, dtype="float64", always_2d=True)
    return data, sample_rate, data.shape[1]


def db_to_gain(db: float) -> float:
    return 10 ** (db / 20)


def get_audio_id_from_track_path(title: str, track_path: Path) -> str:
    prefix = f"{title}_"
    if not track_path.stem.startswith(prefix):
        raise ValueError(f"Unexpected track filename for {title}: {track_path.name}")
    return track_path.stem.removeprefix(prefix)


def load_gaya_voice_ranges(
    xml_path: Path,
    voice_gains_in_db: dict[str, float],
    margin_seconds: float,
) -> dict[str, list[GayaRange]]:
    if not voice_gains_in_db:
        return {}
    if not xml_path.is_file():
        raise FileNotFoundError(f"Annotation XML not found: {xml_path}")

    root = ET.parse(xml_path).getroot()
    ranges_by_audio_id: dict[str, list[GayaRange]] = {}
    seen_voice_ids: set[str] = set()
    for element in root.iter():
        if element.tag not in {"voice", "aligned_voice"}:
            continue
        voice_id = element.attrib.get("id")
        if voice_id not in voice_gains_in_db:
            continue
        audio_id = element.attrib.get("audio_id")
        if not audio_id or not audio_id.endswith("_Gaya"):
            raise ValueError(
                f"Configured Gaya voice id {voice_id} in {xml_path} "
                f"does not have a *_Gaya audio_id."
            )
        start = float(element.attrib["start"])
        end = float(element.attrib["end"])
        if end < start:
            raise ValueError(f"Invalid range for voice id {voice_id}: {start} > {end}")
        start = max(0.0, start - margin_seconds)
        end += margin_seconds
        ranges_by_audio_id.setdefault(audio_id, []).append(
            (start, end, db_to_gain(voice_gains_in_db[voice_id]), voice_id)
        )
        seen_voice_ids.add(voice_id)

    missing_voice_ids = sorted(set(voice_gains_in_db) - seen_voice_ids)
    if missing_voice_ids:
        raise ValueError(
            f"{xml_path} does not contain configured Gaya voice ids: "
            f"{', '.join(missing_voice_ids)}"
        )

    for ranges in ranges_by_audio_id.values():
        ranges.sort()
    return ranges_by_audio_id


def apply_gaya_gain_ranges(
    data: np.ndarray,
    sample_rate: int,
    default_gain: float,
    ranges: list[GayaRange],
) -> np.ndarray:
    gain_curve = np.full(data.shape[0], default_gain, dtype=np.float64)
    for start, end, gain, _voice_id in ranges:
        start_frame = max(0, math.floor(start * sample_rate))
        end_frame = min(data.shape[0], math.ceil(end * sample_rate))
        if start_frame < end_frame:
            gain_curve[start_frame:end_frame] = gain
    return data * gain_curve[:, np.newaxis]


def mix_tracks(
    title: str,
    track_paths: list[Path],
    background_gain_db: float,
    gaya_voice_ranges: dict[str, list[GayaRange]],
    target_peak_dbfs: float,
) -> tuple[np.ndarray, int, dict[str, float]]:
    first_data, sample_rate, channel_count = load_track(track_paths[0])
    expected_frames = first_data.shape[0]
    mixed = np.zeros_like(first_data, dtype=np.float64)
    background_gain = db_to_gain(background_gain_db)
    foreground_count = 0
    background_count = 0
    configured_gaya_voice_count = 0

    for track_path in track_paths:
        data, current_sample_rate, current_channel_count = load_track(track_path)
        if current_sample_rate != sample_rate:
            raise ValueError(
                f"Sample rate mismatch: {track_path} has {current_sample_rate}, "
                f"expected {sample_rate}."
            )
        if current_channel_count != channel_count:
            raise ValueError(
                f"Channel count mismatch: {track_path} has {current_channel_count}, "
                f"expected {channel_count}."
            )
        if data.shape[0] != expected_frames:
            actual_duration = data.shape[0] / sample_rate
            expected_duration = expected_frames / sample_rate
            raise ValueError(
                f"Duration mismatch: {track_path} has {actual_duration:.6f}s, "
                f"expected {expected_duration:.6f}s."
            )

        if track_path.stem.endswith("_Gaya"):
            audio_id = get_audio_id_from_track_path(title, track_path)
            ranges = gaya_voice_ranges.get(audio_id, [])
            data = apply_gaya_gain_ranges(data, sample_rate, background_gain, ranges)
            background_count += 1
            configured_gaya_voice_count += len(ranges)
        else:
            foreground_count += 1
        mixed += data

    pre_scale_peak = float(np.max(np.abs(mixed)))
    target_peak = db_to_gain(target_peak_dbfs)
    if not math.isfinite(pre_scale_peak):
        raise ValueError("The mixed signal contains NaN or infinite values.")
    scale = min(1.0, target_peak / pre_scale_peak) if pre_scale_peak else 1.0
    mixed *= scale
    post_scale_peak = float(np.max(np.abs(mixed)))
    if post_scale_peak > target_peak + 1e-12:
        raise ValueError(
            f"Output peak exceeds target: {post_scale_peak} > {target_peak}."
        )

    stats = {
        "sample_rate": float(sample_rate),
        "duration_seconds": expected_frames / sample_rate,
        "foreground_tracks": float(foreground_count),
        "background_tracks": float(background_count),
        "configured_gaya_voices": float(configured_gaya_voice_count),
        "pre_scale_peak": pre_scale_peak,
        "scale": scale,
        "post_scale_peak": post_scale_peak,
    }
    return mixed, sample_rate, stats


def main() -> None:
    args = parse_args()
    jobs = []
    for title in args.titles:
        audio_dir = args.audio_root / title
        output_path = args.output_root / f"{title}_ALL.flac"
        xml_path = args.xml_root / f"{title}{args.xml_suffix}"
        track_paths = sorted(audio_dir.glob(f"{title}_*.flac"))
        if not audio_dir.is_dir():
            raise FileNotFoundError(f"Audio directory not found: {audio_dir}")
        if not track_paths:
            raise FileNotFoundError(f"No FLAC tracks found under {audio_dir}")
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"Output already exists: {output_path}. Use --overwrite to replace it."
            )
        jobs.append((title, track_paths, output_path, xml_path))

    if not -100.0 < args.target_peak_dbfs <= 0.0:
        raise ValueError("--target-peak-dbfs must be in (-100, 0].")
    if args.gaya_margin_seconds < 0.0:
        raise ValueError("--gaya-margin-seconds must be non-negative.")

    for title, track_paths, output_path, xml_path in jobs:
        gaya_voice_ranges = load_gaya_voice_ranges(
            xml_path,
            GAYA_UTT_GAINS_IN_DB.get(title, {}),
            args.gaya_margin_seconds,
        )
        mixed, sample_rate, stats = mix_tracks(
            title,
            track_paths,
            args.background_gain_db,
            gaya_voice_ranges,
            args.target_peak_dbfs,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, mixed, sample_rate, format="FLAC", subtype="PCM_24")

        written_data, written_sample_rate = sf.read(
            output_path, dtype="float64", always_2d=True
        )
        written_peak = float(np.max(np.abs(written_data)))
        if written_sample_rate != sample_rate or written_data.shape != mixed.shape:
            raise ValueError(
                f"Written output format differs from the mix: {output_path}"
            )
        target_peak = db_to_gain(args.target_peak_dbfs)
        if written_peak > target_peak + 1e-6:
            raise ValueError(
                f"Written output peak exceeds target: {written_peak} > {target_peak}."
            )

        logger.info(f"Wrote {output_path}")
        logger.info(
            f"title={title}, tracks={len(track_paths)}, "
            f"foreground={int(stats['foreground_tracks'])}, "
            f"background={int(stats['background_tracks'])}, "
            f"configured_gaya_voices={int(stats['configured_gaya_voices'])}, "
            f"sample_rate={int(stats['sample_rate'])}, "
            f"duration={stats['duration_seconds']:.3f}s, "
            f"pre_scale_peak={stats['pre_scale_peak']:.6f}, "
            f"scale={stats['scale']:.6f}, written_peak={written_peak:.6f}"
        )


if __name__ == "__main__":
    main()
