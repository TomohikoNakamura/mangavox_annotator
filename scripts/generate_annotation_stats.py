from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import soundfile as sf  # type: ignore

from mangavox_api.annotation_helper import MangaVoxForAnnotation
from mangavox_api.mangavox_ann import Voice

TITLE_METADATA = {
    "LoveHina_vol01": {"display_name": "ラブひな", "era": "1990s", "genre": "ラブコメ"},
    "HinagikuKenzan": {
        "display_name": "ひなぎく見参！一本桜花町編",
        "era": "2000s",
        "genre": "恋愛",
    },
    "SaladDays_vol01": {"display_name": "サラダデイズ", "era": "1990s", "genre": "恋愛"},
    "EverydayOsakanaChan": {
        "display_name": "エヴリデイおさかなちゃん",
        "era": "1990s",
        "genre": "動物",
    },
    "YasasiiAkuma": {"display_name": "やさしい悪魔", "era": "1990s", "genre": "ファンタジー"},
    "TaiyouNiSmash": {"display_name": "太陽にスマッシュ！", "era": "2000s", "genre": "スポーツ"},
    "AkkeraKanjinchou": {"display_name": "あっけら貫刃帖", "era": "2000s", "genre": "バトル"},
    "Akuhamu": {"display_name": "あくはむ", "era": "2000s", "genre": "4コマ"},
}

TITLE_ORDER = [
    "LoveHina_vol01",
    "HinagikuKenzan",
    "SaladDays_vol01",
    "EverydayOsakanaChan",
    "YasasiiAkuma",
    "TaiyouNiSmash",
    "AkkeraKanjinchou",
    "Akuhamu",
]

AUDIO_EXTENSIONS = (".flac", ".wav", ".mp3", ".ogg", ".m4a")


@dataclass
class AnnotationStats:
    title: str
    display_name: str
    era: str
    genre: str
    total_duration_hours: float
    speech_duration_hours: float
    character_count: int
    male_actor_ids: list[str]
    female_actor_ids: list[str]
    voice_count: int
    assigned_frame_count: int
    assigned_text_count: int
    assigned_face_count: int
    assigned_body_count: int

    @property
    def male_actor_count(self) -> int:
        return len(self.male_actor_ids)

    @property
    def female_actor_count(self) -> int:
        return len(self.female_actor_ids)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MangaVox annotation statistics tables."
    )
    parser.add_argument(
        "xml_paths",
        nargs="*",
        type=Path,
        help="MangaVox XML files. Defaults to data/workspace/*_revised_v8.xml.",
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=Path("data/manga2voice/concatenated_voices"),
        help="Root directory containing <title>/<title>_<audio_id> audio files.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format.",
    )
    return parser.parse_args()


def default_xml_paths() -> list[Path]:
    return sorted(Path("data/workspace").glob("*_revised_v8.xml"))


def split_ids(value: str | None) -> list[str]:
    if value is None or value == "":
        return []
    return [item for item in value.split(",") if item]


def count_assigned_elements(voices: Iterable[Voice], key: str) -> int:
    return sum(len(split_ids(getattr(voice, key))) for voice in voices)


def count_characters(voices: Iterable[Voice]) -> int:
    return len({voice.character_id for voice in voices})


def collect_actor_ids(voices: Iterable[Voice]) -> tuple[list[str], list[str]]:
    male_actor_ids: set[str] = set()
    female_actor_ids: set[str] = set()
    for voice in voices:
        if voice.actor_id is None:
            continue
        if re.search(r"\dM\d", voice.actor_id):
            male_actor_ids.add(voice.actor_id)
        elif re.search(r"\dF\d", voice.actor_id):
            female_actor_ids.add(voice.actor_id)
    return sorted(male_actor_ids), sorted(female_actor_ids)


def iter_audio_files(audio_root: Path, title: str) -> list[Path]:
    title_audio_dir = audio_root / title
    if title_audio_dir.is_dir():
        return sorted(
            path
            for path in title_audio_dir.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        )
    return sorted(
        path
        for path in audio_root.glob(f"{title}_*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def audio_duration_seconds(audio_path: Path) -> float:
    info = sf.info(audio_path)
    return info.frames / info.samplerate


def total_audio_duration_seconds(audio_root: Path, title: str) -> float:
    audio_files = iter_audio_files(audio_root, title)
    if not audio_files:
        raise FileNotFoundError(
            f"No audio files found for {title} under {audio_root}. "
            "Use --audio-root to specify the concatenated voices directory."
        )
    return max(audio_duration_seconds(path) for path in audio_files)


def collect_stats(xml_path: Path, audio_root: Path) -> AnnotationStats:
    annotated_voices = MangaVoxForAnnotation.read(xml_path)
    metadata = TITLE_METADATA.get(annotated_voices.title, {})
    aligned_voices = [voice for voice in annotated_voices.voices if voice.audio_id]
    male_actor_ids, female_actor_ids = collect_actor_ids(aligned_voices)

    return AnnotationStats(
        title=annotated_voices.title,
        display_name=metadata.get("display_name", annotated_voices.title),
        era=metadata.get("era", ""),
        genre=metadata.get("genre", ""),
        total_duration_hours=total_audio_duration_seconds(
            audio_root, annotated_voices.title
        )
        / 3600,
        speech_duration_hours=sum(
            voice.end - voice.start for voice in aligned_voices
        )
        / 3600,
        character_count=count_characters(aligned_voices),
        male_actor_ids=male_actor_ids,
        female_actor_ids=female_actor_ids,
        voice_count=len(aligned_voices),
        assigned_frame_count=count_assigned_elements(aligned_voices, "frame_id"),
        assigned_text_count=count_assigned_elements(aligned_voices, "text_id"),
        assigned_face_count=count_assigned_elements(aligned_voices, "face_id"),
        assigned_body_count=count_assigned_elements(aligned_voices, "body_id"),
    )


def sort_stats(stats: list[AnnotationStats]) -> list[AnnotationStats]:
    order = {title: index for index, title in enumerate(TITLE_ORDER)}
    return sorted(stats, key=lambda item: (order.get(item.title, len(order)), item.title))


def format_float(value: float) -> str:
    return f"{value:.1f}"


def render_markdown(stats: list[AnnotationStats]) -> str:
    all_male_actor_ids = set().union(*(item.male_actor_ids for item in stats))
    all_female_actor_ids = set().union(*(item.female_actor_ids for item in stats))

    lines = [
        "## 作品一覧",
        "|作品名 | 年代 | ジャンル | 作品の時間長 [h] | 発話時間の合計 [h] | キャラ | 演技者数（男性）| 演技者数（女性） | 発話数 |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for item in stats:
        lines.append(
            f"| {item.display_name} | {item.era} | {item.genre} | "
            f"{format_float(item.total_duration_hours)} | "
            f"{format_float(item.speech_duration_hours)} | "
            f"{item.character_count} | {item.male_actor_count} | "
            f"{item.female_actor_count} | {item.voice_count} |"
        )
    lines.append("|  |  |  |  |  |  |  |  |  |")
    lines.append(
        f"| {len(stats)}作品 | {len({item.era for item in stats if item.era})}種の年代 | "
        f"{len({item.genre for item in stats if item.genre})}ジャンル | "
        f"{format_float(sum(item.total_duration_hours for item in stats))} | "
        f"{format_float(sum(item.speech_duration_hours for item in stats))} | "
        f"{sum(item.character_count for item in stats)} | "
        f"{len(all_male_actor_ids)} | {len(all_female_actor_ids)} | "
        f"{sum(item.voice_count for item in stats)} |"
    )
    lines.extend(
        [
            "",
            "## 発話とManga109のframe, text, face, body要素との対応付け数",
            "|作品名 | 対応付けられたframe要素の数 | 対応付けられたtext要素の数 | 対応付けられたface要素の数 | 対応付けられたbody要素の数 |",
            "|:---:|:---:|:---:|:---:|:---:|",
        ]
    )
    for item in stats:
        lines.append(
            f"| {item.display_name} | {item.assigned_frame_count} | "
            f"{item.assigned_text_count} | {item.assigned_face_count} | "
            f"{item.assigned_body_count} |"
        )
    lines.append("|  |  |  |  |  |")
    lines.append(
        f"| {len(stats)}作品 | {sum(item.assigned_frame_count for item in stats)} | "
        f"{sum(item.assigned_text_count for item in stats)} | "
        f"{sum(item.assigned_face_count for item in stats)} | "
        f"{sum(item.assigned_body_count for item in stats)} |"
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    xml_paths = args.xml_paths if args.xml_paths else default_xml_paths()
    if not xml_paths:
        raise FileNotFoundError("No XML files found.")

    stats = sort_stats(
        [
            collect_stats(path, args.audio_root)
            for path in xml_paths
        ]
    )
    if args.format == "json":
        print(json.dumps([asdict(item) for item in stats], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(stats))


if __name__ == "__main__":
    main()
