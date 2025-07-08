"""manga2voice_api.manga109_ann
===================================
This module provides data classes and utilities for handling Manga109 annotations.
It includes classes for bounding boxes, characters, frames, faces, bodies, texts, and pages.
It also provides methods for drawing annotations on images and calculating areas and intersections of bounding boxes."""
from __future__ import annotations

import dataclasses
from abc import ABC
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw
from xsdata.formats.dataclass.models.elements import XmlType

from manga2voice_api.utils import AnnotationMixin

# Define a color map for drawing annotations
COLOR_MAP_FOR_DRAW = {
    "body": "#258039",
    "face": "#f5be41",
    "frame": "#31a9b8",
    "text": "#cf3721",
}


@dataclasses.dataclass
class BoundingBoxMixin(ABC):
    """Base class for bounding boxes in Manga109 annotations

    Attributes:
        xmin (int): Minimum x-coordinate of the bounding box
        ymin (int): Minimum y-coordinate of the bounding box
        xmax (int): Maximum x-coordinate of the bounding box
        ymax (int): Maximum y-coordinate of the bounding box
    """
    xmin: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    ymin: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    xmax: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    ymax: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})

    def area(self) -> float:
        """Calculate the area of the bounding box

        Returns:
            float: The area of the bounding box
        """
        return (self.xmax - self.xmin) * (self.ymax - self.ymin)

    def intersection_area(self, other) -> float:
        """Calculate the intersection area with another bounding box

        Args:
            other (BoundingBox): Another bounding box to calculate intersection with

        Returns:
            float: The area of the intersection
        """
        x_overlap = max(0, min(self.xmax, other.xmax) - max(self.xmin, other.xmin))
        y_overlap = max(0, min(self.ymax, other.ymax) - max(self.ymin, other.ymin))
        return x_overlap * y_overlap

    def bbox(self) -> Tuple[int, int, int, int]:
        """Get the bounding box coordinates as a tuple

        Returns:
            Tuple[int, int, int, int]: A tuple containing (xmin, ymin, xmax, ymax)
        """
        return (self.xmin, self.ymin, self.xmax, self.ymax)

    def draw_rectangle(
        self, image: Image.Image, score: Optional[float] = None, width: int = 10
    ):
        """Draw a rectangle on the image representing the bounding box

        Args:
            image (Image): The image to draw on
            score (Optional[float]): The score to display on the rectangle (default is None)
            width (int): The width of the rectangle outline (default is 10)
        """
        bbox = self.bbox()
        ann_type = self.ann_type()
        draw = ImageDraw.Draw(image)
        draw.rectangle(bbox, outline=COLOR_MAP_FOR_DRAW[ann_type], width=width)
        if score is not None:
            draw.text(
                (bbox[0], bbox[1]), f"{score:.2f}", fill=COLOR_MAP_FOR_DRAW[ann_type]
            )

    def ann_type(self):
        """Get the type of annotation for this bounding box"""
        return self.__class__.__name__.lower()

    def diff(self, other) -> List[str]:
        """Calculate the differences between this bounding box and another

        Args:
            other (BoundingBox): Another bounding box to compare with

        Returns:
            List[str]: A list of differences
        """
        differences = []
        for f in dataclasses.fields(self):
            if getattr(self, f.name) != getattr(other, f.name):
                differences.append(
                    f"{f.name}: {getattr(self, f.name)} != {getattr(other, f.name)}"
                )
        return differences


@dataclasses.dataclass
class Character:
    """Character data class

    Attributes:
        id (str): The character id
        name (str): The character name
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    name: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})


@dataclasses.dataclass
class Characters:
    """Characters data class

    Attributes:
        character (List[Character]): List of characters
    """

    character: List[Character] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT}
    )

    def get_character_name_by_id(self, character_id: str) -> str:
        """Get the character name by the character id

        Args:
            character_id (str): The character id

        Returns:
            str: The character name
        """
        for character in self.character:
            if character.id == character_id:
                return character.name
        raise ValueError(f"Character ID {character_id} not found")


@dataclasses.dataclass
class FrameCandidate:
    """Frame candidate data class

    Attributes:
        id (str): The frame candidate id
        score (float): The score of the frame candidate
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    score: float = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})


@dataclasses.dataclass(kw_only=True)
class Text(BoundingBoxMixin):
    """Text data class

    Attributes:
        id (str): The text id
        xmin (int): Minimum x-coordinate of the bounding box
        ymin (int): Minimum y-coordinate of the bounding box
        xmax (int): Maximum x-coordinate of the bounding box
        ymax (int): Maximum y-coordinate of the bounding box
        text (str): The text content
        frame_candidates (List[FrameCandidate]): List of frame candidates for this text
        assigned (Optional[bool]): Whether the text is assigned to a frame or not
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    text: str
    frame_candidates: List[FrameCandidate] = dataclasses.field(
        default_factory=list,
        metadata={"type": XmlType.ELEMENT, "name": "frame_candidate"},
    )
    assigned: Optional[bool] = dataclasses.field(
        default=False, metadata={"type": XmlType.ATTRIBUTE}
    )

    def copy(self, include_candidates: bool):
        """Create a copy of the Text object

        Args:
            include_candidates (bool): Whether to include frame candidates in the copy

        Returns:
            Text: A new Text object with the same attributes
        """
        if include_candidates:
            return Text(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                text=self.text,
                frame_candidates=self.frame_candidates,
            )
        else:
            return Text(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                text=self.text,
            )


@dataclasses.dataclass(kw_only=True)
class Body(BoundingBoxMixin):
    """Body data class

    Attributes:
        id (str): The body id
        xmin (int): Minimum x-coordinate of the bounding box
        ymin (int): Minimum y-coordinate of the bounding box
        xmax (int): Maximum x-coordinate of the bounding box
        ymax (int): Maximum y-coordinate of the bounding box
        character (str): The character associated with the body
        frame_candidates (List[FrameCandidate]): List of frame candidates for this body
        assigned (Optional[bool]): Whether the body is assigned to a frame or not
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    character: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    frame_candidates: List[FrameCandidate] = dataclasses.field(
        default_factory=list,
        metadata={"type": XmlType.ELEMENT, "name": "frame_candidate"},
    )
    assigned: Optional[bool] = dataclasses.field(
        default=False, metadata={"type": XmlType.ATTRIBUTE}
    )

    def copy(self, include_candidates: bool):
        """Create a copy of the Body object

        Args:
            include_candidates (bool): Whether to include frame candidates in the copy

        Returns:
            Body: A new Body object with the same attributes
        """
        if include_candidates:
            return Body(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                character=self.character,
                frame_candidates=self.frame_candidates,
            )
        else:
            return Body(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                character=self.character,
            )


@dataclasses.dataclass(kw_only=True)
class Frame(BoundingBoxMixin):
    """Frame data class

    Attributes:
        id (str): The frame id
        xmin (int): Minimum x-coordinate of the bounding box
        ymin (int): Minimum y-coordinate of the bounding box
        xmax (int): Maximum x-coordinate of the bounding box
        ymax (int): Maximum y-coordinate of the bounding box
        face_candidates (List[str]): List of face candidate ids associated with this frame
        text_candidates (List[str]): List of text candidate ids associated with this frame
        body_candidates (List[str]): List of body candidate ids associated with this frame
        assigned (Optional[bool]): Whether the frame is assigned or not
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    face_candidates: List[str] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "face_id"}
    )
    text_candidates: List[str] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "text_id"}
    )
    body_candidates: List[str] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "body_id"}
    )
    assigned: Optional[bool] = dataclasses.field(
        default=False, metadata={"type": XmlType.ATTRIBUTE}
    )

    def copy(self, include_candidates: bool):
        """Create a copy of the Frame object

        Args:
            include_candidates (bool): Whether to include candidates in the copy

        Returns:
            Frame: A new Frame object with the same attributes
        """
        if include_candidates:
            return Frame(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                face_candidates=self.face_candidates,
                text_candidates=self.text_candidates,
                body_candidates=self.body_candidates,
            )
        else:
            return Frame(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
            )


@dataclasses.dataclass(kw_only=True)
class Face(BoundingBoxMixin):
    """Face data class

    Attributes:
        id (str): The face id
        xmin (int): Minimum x-coordinate of the bounding box
        ymin (int): Minimum y-coordinate of the bounding box
        xmax (int): Maximum x-coordinate of the bounding box
        ymax (int): Maximum y-coordinate of the bounding box
        character (str): The character associated with the face
        frame_candidates (List[FrameCandidate]): List of frame candidates for this face
        assigned (Optional[bool]): Whether the face is assigned to a frame or not
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    character: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    frame_candidates: List[FrameCandidate] = dataclasses.field(
        default_factory=list,
        metadata={"type": XmlType.ELEMENT, "name": "frame_candidate"},
    )
    assigned: Optional[bool] = dataclasses.field(
        default=False, metadata={"type": XmlType.ATTRIBUTE}
    )

    def copy(self, include_candidates: bool):
        """Create a copy of the Face object

        Args:
            include_candidates (bool): Whether to include frame candidates in the copy

        Returns:
            Face: A new Face object with the same attributes
        """
        if include_candidates:
            return Face(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                character=self.character,
                frame_candidates=self.frame_candidates,
            )
        else:
            return Face(
                id=self.id,
                xmin=self.xmin,
                ymin=self.ymin,
                xmax=self.xmax,
                ymax=self.ymax,
                character=self.character,
            )


@dataclasses.dataclass
class Page:
    """Page data class

    Attributes:
        index (int): The page index
        width (int): The width of the page
        height (int): The height of the page
        texts (List[Text]): List of text annotations on the page
        bodies (List[Body]): List of body annotations on the page
        frames (List[Frame]): List of frame annotations on the page
        faces (List[Face]): List of face annotations on the page
    """

    index: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    width: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    height: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    texts: List[Text] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "text"}
    )
    bodies: List[Body] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "body"}
    )
    frames: List[Frame] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "frame"}
    )
    faces: List[Face] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "face"}
    )


@dataclasses.dataclass
class Pages:
    """Pages data class

    Attributes:
        page (List[Page]): List of pages
    """

    page: List[Page] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT}
    )

    def __getitem__(self, index: int) -> Page:
        """Get a page by its index

        Args:
            index (int): The page index

        Returns:
            Page: The page at the specified index
        """
        return self.page[index]

    def __len__(self) -> int:
        """Get the number of pages

        Returns:
            int: The number of pages
        """
        return len(self.page)


@dataclasses.dataclass
class Manga109(AnnotationMixin):
    """Manga109 data class

    Attributes:
        title (str): The title
        characters (Characters): The characters
        pages (Pages): The pages
    """

    title: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    characters: Characters = dataclasses.field(
        default_factory=Characters, metadata={"type": XmlType.ELEMENT}
    )
    pages: Pages = dataclasses.field(
        default_factory=Pages, metadata={"type": XmlType.ELEMENT}
    )
