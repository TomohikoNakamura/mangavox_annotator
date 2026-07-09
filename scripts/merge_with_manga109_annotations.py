from argparse import ArgumentParser, Namespace
from pathlib import Path

from loguru import logger

from mangavox_api.manga109_ann import Manga109
from mangavox_api.mangavox_ann import MangaVox


def parse_args() -> Namespace:
    """Parse command line arguments for merging MangaVox annotations with Manga109 annotations.

    Returns:
        Namespace: Parsed command line arguments.
    """
    parser = ArgumentParser(
        description="Merge MangaVox annotations with Manga109 annotations."
    )
    parser.add_argument(
        "mangavox_xml_path", type=Path, help="Path to the MangaVox XML file."
    )
    parser.add_argument(
        "manga109_ann_path", type=Path, help="Path to the Manga109 annotation file."
    )
    parser.add_argument(
        "output_path", type=Path, help="Path to save the merged annotations."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Read MangaVox annotations
    manga_vox = MangaVox.read(args.mangavox_xml_path)

    # Read Manga109 annotations
    manga109_ann = Manga109.read(args.manga109_ann_path)

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

    # Save the merged annotations back to a file
    manga_vox.write(args.output_path)
    logger.info(f"Merged annotations saved to {args.output_path}")
