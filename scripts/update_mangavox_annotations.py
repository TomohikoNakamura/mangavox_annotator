import argparse
from datetime import datetime
from pathlib import Path
from typing import List

import yaml
from loguru import logger

from mangavox_api.annotation_helper import MangaVoxForAnnotation
from mangavox_api.utils import get_timestamp_in_iso8601_format


def apply_change_logs(
    change_log_file_list: List[Path], annotated_voices: MangaVoxForAnnotation
) -> MangaVoxForAnnotation:
    """Apply change logs to the MangaVox.

    Args:
        change_log_file_list (List[Path]): List of paths to change log directories.
        annotated_voices (MangaVoxForAnnotation): The MangaVoxForAnnotation object to apply changes to.

    Returns:
        MangaVoxForAnnotation: The updated MangaVoxForAnnotation object after applying change logs
    """
    change_logs = []
    for change_log_dir in change_log_file_list:
        if not change_log_dir.is_dir():
            continue
        # check config data for checking the version mismatch
        with open(change_log_dir / "config.yaml", "r") as fp:
            config_data = yaml.safe_load(fp.read())
        annotated_voices.check_change_applicability(config_data)
        #
        change_log_filename = change_log_dir / "change_log.yaml"
        with open(change_log_filename, "r") as fp:
            change_logs += yaml.safe_load(fp.read())
    change_logs = sorted(
        change_logs, key=lambda x: datetime.fromisoformat(x["timestamp"])
    )
    annotated_voices.apply_change_logs(change_logs)
    annotated_voices.update_assigned()
    return annotated_voices


def sanity_check(annotated_voices: MangaVoxForAnnotation):
    """Perform sanity checks on the MangaVox.

    Args:
        annotated_voices (MangaVoxForAnnotation): The MangaVoxForAnnotation object

    Raises:
        ValueError: If any sanity check fails, such as page_index being None.
    """
    check_flag = False
    for voice in annotated_voices.voices:
        if voice.page_index is None:
            check_flag = True
            logger.error(f"page_index is None: {voice}")
    if check_flag:
        raise ValueError("page_index is None")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the script.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="Update the MangaVox XML file.")
    parser.add_argument(
        "--change_log_dir",
        type=Path,
        default="../visualizer/logs",
        help="Directory to save change logs.",
    )
    parser.add_argument(
        "current_filename",
        type=Path,
        help="Path to the MangaVox XML file.",
    )
    parser.add_argument(
        "revised_filename",
        type=Path,
        help="Path to save the revised MangaVox XML file.",
    )
    args = parser.parse_args()
    return args


def revise_xmls(
    annotated_voices: MangaVoxForAnnotation, change_log_dir: Path
) -> MangaVoxForAnnotation:
    """Revise the MangaVox XML file by applying change logs.

    Args:
        annotated_voices (MangaVoxForAnnotation): The MangaVoxForAnnotation object to revise.
        change_log_dir (Path): Directory containing change logs to apply.

    Returns:
        MangaVoxForAnnotation: The revised MangaVoxForAnnotation object after applying change logs.
    """
    # check change logs
    if Path(change_log_dir / annotated_voices.title).exists():
        apply_logs = sorted(
            [
                _.parent
                for _ in Path(change_log_dir / annotated_voices.title).glob(
                    "*/change_log.yaml"
                )
            ]
        )
    else:
        apply_logs = []
    logger.info(f"Applying change logs: {apply_logs}")
    # apply change logs
    revised_annotated_voices = apply_change_logs(apply_logs, annotated_voices)
    # sanity check
    sanity_check(revised_annotated_voices)
    return revised_annotated_voices


def reset_indices(annotated_voices: MangaVoxForAnnotation) -> MangaVoxForAnnotation:
    """Reset indices of the MangaVox and perform necessary updates.

    Args:
        annotated_voices (MangaVoxForAnnotation): The MangaVoxForAnnotation object to reset.

    Returns:
        MangaVoxForAnnotation: The updated MangaVoxForAnnotation object with reset indices.
    """
    # reset indices
    annotated_voices.reset_index()
    annotated_voices.remove_unused_characters()
    annotated_voices.update_assigned()
    # sanity check
    annotated_voices.check_overlapping_voice_ids()
    annotated_voices.check_undefined_characters()
    return annotated_voices


if __name__ == "__main__":
    args = parse_args()
    # load MangaVox XML
    xml_file_path = args.current_filename
    annotated_voices = MangaVoxForAnnotation.read(xml_file_path)
    # revise MangaVox XML
    revised_annotated_voices = revise_xmls(annotated_voices, args.change_log_dir)
    # reset indices and save revised XML
    revised_annotated_voices = reset_indices(revised_annotated_voices)
    # update last modified timestamp
    revised_annotated_voices.last_modified = get_timestamp_in_iso8601_format()
    # save revised XML
    revised_annotated_voices.write(args.revised_filename)
