import argparse
from dataclasses import asdict
from pathlib import Path

import yaml

from manga2voice_api.annotation_helper import MangaVoxForAnnotation
from manga2voice_api.utils import get_timestamp_in_iso8601_format


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Create a change list for the MangaVox XML file."
    )
    parser.add_argument(
        "old_mangavox_filename",
        type=Path,
        help="Path to the old MangaVox XML file.",
    )
    parser.add_argument(
        "new_mangavox_filename",
        type=Path,
        help="Path to the new MangaVox XML file.",
    )
    parser.add_argument(
        "changelist_filename", type=Path, help="Path to the changelist YAML file."
    )
    args = parser.parse_args()
    return args


def sanity_check(args: argparse.Namespace):
    """Sanity check for the changelist.

    Args:
        args (argparse.Namespace): Parsed command line arguments.
    """
    # check if the changelist is correct
    old_annotated_voices = MangaVoxForAnnotation.read(args.old_mangavox_filename)
    with open(args.changelist_filename, "r", encoding="utf-8") as fp:
        change_logs = yaml.safe_load(fp)["change_logs"]
    old_annotated_voices.apply_change_logs(change_logs, update_abnormal_keys=True)
    new_annotated_voices = MangaVoxForAnnotation.read(args.new_mangavox_filename)
    #
    if old_annotated_voices.voices != new_annotated_voices.voices:
        raise ValueError("The changelist is incorrect.")


def create_changelist(args: argparse.Namespace):
    """Create a changelist for the MangaVox XML file.

    Args:
        args (argparse.Namespace): Parsed command line arguments.
    """
    old_annotated_voices = MangaVoxForAnnotation.read(args.old_mangavox_filename)
    new_annotated_voices = MangaVoxForAnnotation.read(args.new_mangavox_filename)
    #
    change_logs = []
    for old_annotated_voice in old_annotated_voices.voices:
        new_annotated_voice = new_annotated_voices.get_voice_by_id(
            old_annotated_voice.id
        )
        if new_annotated_voice is None:
            change_logs.append(
                {
                    "voice_id": old_annotated_voice.id,
                    "delete": True,
                    "timestamp": get_timestamp_in_iso8601_format(),
                }
            )
        else:
            diff = old_annotated_voice.diff(new_annotated_voice)
            if len(diff) > 0:
                change_logs.append(
                    {
                        "voice_id": old_annotated_voice.id,
                        "change": diff,
                        "timestamp": get_timestamp_in_iso8601_format(),
                    }
                )
    for new_annotated_voice in new_annotated_voices.voices:
        old_annotated_voice2 = old_annotated_voices.get_voice_by_id(
            new_annotated_voice.id
        )
        if old_annotated_voice2 is None:
            change_logs.append(
                {
                    "voice_id": new_annotated_voice.id,
                    "add": asdict(new_annotated_voice),
                    "timestamp": get_timestamp_in_iso8601_format(),
                }
            )
    #
    conf = {
        "old_filename": str(args.old_mangavox_filename),
        "new_filename": str(args.new_mangavox_filename),
    }
    data = {
        "conf": conf,
        "change_logs": change_logs,
    }
    with open(args.changelist_filename, "w", encoding="utf-8") as fp:
        yaml.dump(data, fp, allow_unicode=True)

    # sanity check
    sanity_check(args)


if __name__ == "__main__":
    args = parse_args()
    create_changelist(args)
