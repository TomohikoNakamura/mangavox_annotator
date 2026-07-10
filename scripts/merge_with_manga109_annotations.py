from argparse import ArgumentParser, Namespace
from pathlib import Path

from loguru import logger

from config import MANGA_TITLES
from mangavox_api.annotation_helper import MangaVoxForAnnotation
from mangavox_api.manga109_ann import Manga109
from mangavox_api.mangavox_ann import MangaVox

DEFAULT_WORKSPACE_ROOT = Path("data/workspace")
DEFAULT_MANGA109_ANNOTATION_ROOT = Path(
    "data/manga109/Manga109_released_2023_12_07/annotations"
)


def parse_args() -> Namespace:
    """Parse command line arguments for merging MangaVox annotations."""
    parser = ArgumentParser(
        description="Merge public MangaVox XML files with Manga109 annotations."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        metavar="PATH",
        help="Single-title mode: MANGAVOX_XML MANGA109_XML OUTPUT_XML.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process every title in config.MANGA_TITLES.",
    )
    parser.add_argument(
        "--titles",
        nargs="+",
        choices=MANGA_TITLES,
        help="Titles to process. Defaults to all configured titles.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Directory containing public MangaVox XML files.",
    )
    parser.add_argument(
        "--manga109-annotation-root",
        type=Path,
        default=DEFAULT_MANGA109_ANNOTATION_ROOT,
        help="Directory containing Manga109 annotation XML files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow batch mode to overwrite existing _v1.xml files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned batch operations without writing files.",
    )
    args = parser.parse_args()
    if args.paths:
        if len(args.paths) != 3:
            parser.error("Specify three PATH arguments for one title.")
        if args.all or args.titles or args.overwrite or args.dry_run:
            parser.error(
                "Batch options cannot be combined with single-title PATH arguments."
            )
    else:
        # No paths means batch mode. --all remains accepted for compatibility.
        args.all = True
    return args


def merge_with_manga109_annotations(
    mangavox_xml_path: Path, manga109_ann_path: Path, output_path: Path
) -> None:
    """Merge a public MangaVox XML file with its Manga109 annotations."""

    # Read MangaVox annotations
    manga_vox = MangaVox.read(mangavox_xml_path)

    # Read Manga109 annotations
    manga109_ann = Manga109.read(manga109_ann_path)

    # Merge MangaVox annotations with Manga109 annotations
    manga_vox.merge_with_manga109_ann(manga109_ann)

    # Handle merged characters
    if manga_vox.title == "HinagikuKenzan":
        if manga_vox.pages is None:
            raise ValueError(
                "MangaVox pages are empty. Please check the MangaVox XML file."
            )
        # Character ID `<character id="000274ce" name="石川剣"/>` is merged into <character id="000274af" name="石川 剣,石川 夢幻斎">
        for page in manga_vox.pages.page:
            for body in page.bodies:
                if body.character == "000274ce":
                    body.character = "000274af"
            for face in page.faces:
                if face.character == "000274ce":
                    face.character = "000274af"

    # Update the assigned attribute of the voices
    manga_vox.update_assigned(page_index=None)  # Update all pages

    # Save the merged annotations in the annotation XML format.
    annotated_manga_vox = MangaVoxForAnnotation.from_mangavox(manga_vox)
    annotated_manga_vox.write(output_path)
    logger.info(f"Merged annotations saved to {output_path}")


def merge_all_with_manga109_annotations(args: Namespace) -> None:
    """Create <title>_v1.xml for every title requested in batch mode."""
    titles = args.titles or MANGA_TITLES
    jobs = [
        (
            args.workspace_root / f"{title}.xml",
            args.manga109_annotation_root / f"{title}.xml",
            args.workspace_root / f"{title}_v1.xml",
        )
        for title in titles
    ]

    if args.dry_run:
        for mangavox_xml_path, manga109_ann_path, output_path in jobs:
            logger.info(f"{mangavox_xml_path} + {manga109_ann_path} -> {output_path}")
        return

    for mangavox_xml_path, manga109_ann_path, output_path in jobs:
        if not mangavox_xml_path.is_file():
            raise FileNotFoundError(f"MangaVox XML file not found: {mangavox_xml_path}")
        if not manga109_ann_path.is_file():
            raise FileNotFoundError(
                f"Manga109 annotation XML file not found: {manga109_ann_path}"
            )
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use --overwrite to replace it."
            )

    for mangavox_xml_path, manga109_ann_path, output_path in jobs:
        logger.info(f"{mangavox_xml_path} + {manga109_ann_path} -> {output_path}")
        merge_with_manga109_annotations(
            mangavox_xml_path, manga109_ann_path, output_path
        )


def main() -> None:
    """Run a single merge or batch merge according to command line arguments."""
    args = parse_args()
    if args.all:
        merge_all_with_manga109_annotations(args)
    else:
        merge_with_manga109_annotations(*args.paths)


if __name__ == "__main__":
    main()
