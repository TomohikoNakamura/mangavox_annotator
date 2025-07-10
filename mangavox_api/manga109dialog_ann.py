"""mangavox_api.manga109dialog_ann
===================================
This module defines data classes for handling Manga109 dialog annotations.
It includes classes for mapping speakers to text, representing pages, and the overall dialog annotation structure.
"""

import dataclasses
from typing import List

from xsdata.formats.dataclass.models.elements import XmlType

from mangavox_api.utils import AnnotationMixin


@dataclasses.dataclass
class Speaker2Text:
    """Speaker to Text mapping data class

    Attributes:
        id (str): The unique identifier for the mapping
        text_id (str): The identifier for the text spoken by the speaker
        speaker_id (str): The identifier for the speaker
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    text_id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    speaker_id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})


@dataclasses.dataclass
class Page:
    """Page data class

    Attributes:
        index (int): The page index
        width (int): The width of the page
        height (int): The height of the page
        speaker_to_texts (List[Speaker2Text]): List of Speaker2Text mappings on the page
    """

    index: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    width: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    height: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    speaker_to_texts: List[Speaker2Text] = dataclasses.field(
        default_factory=list,
        metadata={"type": XmlType.ELEMENT, "name": "speaker_to_text"},
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


@dataclasses.dataclass
class Manga109Dialog(AnnotationMixin):
    """Manga109 dialog annotation data class

    Attributes:
        title (str): The title
        pages (Pages): The pages
    """

    title: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    pages: Pages = dataclasses.field(
        default_factory=Pages, metadata={"type": XmlType.ELEMENT}
    )
