"""Mix MangaVox character tracks into an ALL-equivalent FLAC file."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import soundfile as sf  # type: ignore
from loguru import logger

from config import MANGA_TITLES

DEFAULT_AUDIO_ROOT = Path("data/manga2voice/concatenated_voices")
DEFAULT_OUTPUT_ROOT = Path("data/manga2voice/voices")
DEFAULT_BACKGROUND_GAIN_DB = -12.0
DEFAULT_TARGET_PEAK_DBFS = -1.0


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
        help="Gain applied to *_Gaya.flac tracks.",
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


def mix_tracks(
    track_paths: list[Path],
    background_gain_db: float,
    target_peak_dbfs: float,
) -> tuple[np.ndarray, int, dict[str, float]]:
    first_data, sample_rate, channel_count = load_track(track_paths[0])
    expected_frames = first_data.shape[0]
    mixed = np.zeros_like(first_data, dtype=np.float64)
    background_gain = 10 ** (background_gain_db / 20)
    foreground_count = 0
    background_count = 0

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

        is_background = track_path.stem.endswith("_Gaya")
        gain = background_gain if is_background else 1.0
        mixed += data * gain
        if is_background:
            background_count += 1
        else:
            foreground_count += 1

    pre_scale_peak = float(np.max(np.abs(mixed)))
    target_peak = 10 ** (target_peak_dbfs / 20)
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
        track_paths = sorted(audio_dir.glob(f"{title}_*.flac"))
        if not audio_dir.is_dir():
            raise FileNotFoundError(f"Audio directory not found: {audio_dir}")
        if not track_paths:
            raise FileNotFoundError(f"No FLAC tracks found under {audio_dir}")
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"Output already exists: {output_path}. Use --overwrite to replace it."
            )
        jobs.append((title, track_paths, output_path))

    if not -100.0 < args.target_peak_dbfs <= 0.0:
        raise ValueError("--target-peak-dbfs must be in (-100, 0].")

    for title, track_paths, output_path in jobs:
        mixed, sample_rate, stats = mix_tracks(
            track_paths, args.background_gain_db, args.target_peak_dbfs
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
        target_peak = 10 ** (args.target_peak_dbfs / 20)
        if written_peak > target_peak + 1e-6:
            raise ValueError(
                f"Written output peak exceeds target: {written_peak} > {target_peak}."
            )

        logger.info(f"Wrote {output_path}")
        logger.info(
            f"title={title}, tracks={len(track_paths)}, "
            f"foreground={int(stats['foreground_tracks'])}, "
            f"background={int(stats['background_tracks'])}, "
            f"sample_rate={int(stats['sample_rate'])}, "
            f"duration={stats['duration_seconds']:.3f}s, "
            f"pre_scale_peak={stats['pre_scale_peak']:.6f}, "
            f"scale={stats['scale']:.6f}, written_peak={written_peak:.6f}"
        )


if __name__ == "__main__":
    main()
