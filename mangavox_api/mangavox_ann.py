"""mangavox_api.mangavox_ann
===================================
This module defines data classes for handling MangaVox annotations.
It includes classes for characters, voices, and the overall MangaVox annotation structure.

Copyright (C) 2025 National Institute of Advanced Industrial Science and Technology (AIST)
"""

from __future__ import annotations

import copy
import dataclasses
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import cv2
import numpy
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm
from xsdata.formats.dataclass.models.elements import XmlType

from mangavox_api.manga109_ann import Body, Face, Frame, Manga109, Pages, Text
from mangavox_api.utils import AnnotationMixin


@dataclasses.dataclass
class CharacterDetails:
    """Character details data class

    Attributes:
        hiragana (str): The hiragana name of the character
        jp_name (str): The Japanese name of the character
        roman (str): The romanized name of the character
        en_name (str): The English name of the character
    """

    hiragana: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    jp_name: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    roman: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    en_name: str = dataclasses.field(default="", metadata={"type": XmlType.ATTRIBUTE})

    def __post_init__(self):
        if isinstance(self.hiragana, list):
            self.hiragana = ",".join(self.hiragana)
        if isinstance(self.jp_name, list):
            self.jp_name = ",".join(self.jp_name)
        if isinstance(self.roman, list):
            self.roman = ",".join(self.roman)
        if isinstance(self.en_name, list):
            self.en_name = ",".join(self.en_name)

    @property
    def normalized_roman(self) -> str:
        """Get the normalized roman name

        Returns:
            str: The normalized roman name
        """
        roman_splitted = []
        for _ in self.roman.split(","):
            roman_splitted.extend(_.split(" "))
        return "".join([x.capitalize() for x in roman_splitted])


@dataclasses.dataclass
class Character:
    """Character data class

    Attributes:
        id (str): The character id
        name (str): The character name
        details (CharacterDetails): The character details
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    name: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    details: CharacterDetails = dataclasses.field(metadata={"type": XmlType.ELEMENT})

    @property
    def normalized_roman(self) -> str:
        """Get the normalized roman name

        Returns:
            str: The normalized roman name
        """
        if self.details is None:
            raise ValueError("Character details not found")
        return self.details.normalized_roman

    def sanity_check(self):
        """Sanity check for the character data

        Raises:
            ValueError: If any of the required fields are empty
        """
        if self.id is None:
            raise ValueError(f"Empty character ID: {self.id}")
        if self.name is None:
            raise ValueError(f"Empty character name: {self.name}")
        if self.details is None:
            raise ValueError(f"Empty character details: {self.details}")


@dataclasses.dataclass
class Characters:
    """Characters data class

    Attributes:
        character (List[Character]): List of characters
    """

    character: List[Character] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT}
    )

    def sanity_check(self):
        """Sanity check for the characters data"""
        for character in self.character:
            character.sanity_check()

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

    def get_character_details_by_id(self, character_id: str) -> CharacterDetails:
        """Get the character details by the character id

        Args:
            character_id (str): The character id

        Returns:
            CharacterDetails: The character details
        """
        for character in self.character:
            if character.id == character_id:
                return copy.deepcopy(character.details)
        raise ValueError(f"Character ID {character_id} not found")

    def __getitem__(self, index: int) -> Character:
        """Get the character by index

        Args:
            index (int): The index of the character

        Returns:
            Character: The character at the specified index
        """
        return self.character[index]

    def __len__(self) -> int:
        """Get the number of characters

        Returns:
            int: The number of characters
        """
        return len(self.character)


@dataclasses.dataclass
class Voice:
    """Voice data class

    Attributes:
        id (str): The voice id
        index (int): The voice index
        start (float): The start time of the voice
        end (float): The end time of the voice
        episode_index (int): The episode index
        actor_id (str): The actor id. If None, the voice is of the background chatter.
        character_id (str): The character id
        text_id (Optional[str]): The text id
        page_index (Optional[int]): The page index
        frame_id (Optional[str]): The frame id
        face_id (Optional[str]): The face id
        body_id (Optional[str]): The body id
        text (str): The spoken text
        audio_id (Optional[str]): The audio file id
    """

    id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    index: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    start: float = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    end: float = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    episode_index: int = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    character_id: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    actor_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    text_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    # association
    page_index: Optional[int] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    frame_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )  # frame id
    face_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )  # face id
    body_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )  # body id
    # text if it differs from manga109 annotation
    text: str = dataclasses.field(default="", metadata={"type": XmlType.TEXT})
    # audio file id
    audio_id: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )

    @property
    def normalized_character_id(self) -> str:
        """Get the normalized character ID

        Returns:
            str: The normalized character ID (without "v" suffix)
        """
        if "v" in self.character_id:
            return self.character_id[: self.character_id.find("v")]
        else:
            return self.character_id

    def find_associated_elements(
        self, pages: Pages
    ) -> List[Body | Face | Frame | Text]:
        """Find the associated elements (Body, Face, Frame, Text) for the voice

        Args:
            pages (Pages): The Pages object containing all pages

        Returns:
            List[Body | Face | Frame | Text]: A list of associated elements
        """
        associated_elements: List[Body | Face | Frame | Text] = []
        for page in pages.page:
            if page.index == self.page_index:
                for body in page.bodies:
                    if body.id == self.body_id:
                        associated_elements.append(body)
                for face in page.faces:
                    if face.id == self.face_id:
                        associated_elements.append(face)
                for frame in page.frames:
                    if frame.id == self.frame_id:
                        associated_elements.append(frame)
                for text in page.texts:
                    if text.id == self.text_id:
                        associated_elements.append(text)
        return associated_elements

    def sanity_check(self):
        """Sanity check for the voice instance

        Raises:
            ValueError: If any of the required fields are empty or invalid
        """
        # required fields: id, audio_id, index, start, end, episode_index, actor_id, character_id, page_index
        if self.id is None:
            raise ValueError(f"Empty voice ID: {self.id}")
        if self.audio_id is None:
            print(f"Empty audio ID: {self.audio_id}, {self}")
        if self.index is None:
            raise ValueError(f"Empty voice index: {self.index}")
        if self.start is None:
            raise ValueError(f"Empty start time: {self.start}")
        if self.end is None:
            raise ValueError(f"Empty end time: {self.end}")
        if self.episode_index is None:
            raise ValueError(f"Empty episode index: {self.episode_index}")
        if self.actor_id is None or self.actor_id == "":
            raise ValueError(f"Empty actor ID: {self.actor_id}")
        if self.character_id is None or self.character_id == "":
            raise ValueError(f"Empty character ID: {self.character_id}")
        if self.page_index is None:
            raise ValueError(f"Empty page index: {self.page_index}")
        # check orders of start--end
        if self.start >= self.end:
            raise ValueError(f"Invalid time range: {self.start} >= {self.end}")


@dataclasses.dataclass
class MangaVox(AnnotationMixin):
    """MangaVox data class

    Attributes:
        title (str): The title of the MangaVox annotation
        version (str): The version of the MangaVox annotation
        manga109_version (str): The version of the Manga109 annotation
        characters (Characters): The characters in the MangaVox annotation
        voices (List[Voice]): List of voices in the MangaVox annotation
        pages (Optional[Pages]): The pages in the MangaVox annotation
    """

    title: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    version: str = dataclasses.field(
        default="1.0", metadata={"type": XmlType.ATTRIBUTE}
    )
    manga109_version: str = dataclasses.field(
        default="1.0", metadata={"type": XmlType.ATTRIBUTE}
    )
    characters: Characters = dataclasses.field(
        default_factory=Characters, metadata={"type": XmlType.ELEMENT}
    )
    voices: List[Voice] = dataclasses.field(
        default_factory=list, metadata={"type": XmlType.ELEMENT, "name": "voice"}
    )
    pages: Optional[Pages] = dataclasses.field(
        default=None, metadata={"type": XmlType.ELEMENT}
    )

    # update methods
    def merge_with_manga109_ann(self: MangaVox, manga109_book: Manga109):
        """Merge MangaVox annotations with Manga109 annotations

        Args:
            manga109_book (Manga109): A Manga109 object representing the Manga109 annotations
        """
        self.pages = copy.deepcopy(manga109_book.pages)

    def update_assigned(self: MangaVox, page_index: Optional[int] = None):
        """Update the assigned attribute of the voices

        Args:
            page_index (int, optional): The page index to update. If None, update all pages.
        """
        if self.pages is None:
            raise ValueError("Pages not found in MangaVox object")

        def filter_elements(key: str, target_element: Voice, ids: Set):
            value = getattr(target_element, key)
            if value is not None:
                for v in value.split(","):
                    ids.add(v)
            return ids

        def update_attrib(
            key: str,
            targets: List[Text] | List[Face] | List[Frame] | List[Body],
            ids: Set,
        ):
            for target in targets:
                if target.id in ids:
                    setattr(target, key, True)

        def reset_attrib(
            key: str, targets: List[Text] | List[Face] | List[Frame] | List[Body]
        ):
            for target in targets:
                setattr(target, key, False)

        # Collect the IDs of the assigned elements
        text_ids: Set[str] = set()
        body_ids: Set[str] = set()
        face_ids: Set[str] = set()
        frame_ids: Set[str] = set()
        if page_index is not None:
            target_voices = list(
                filter(lambda x: x.page_index == page_index, self.voices)
            )
        else:
            target_voices = self.voices
        for voice in target_voices:
            text_ids = filter_elements("text_id", voice, text_ids)
            body_ids = filter_elements("body_id", voice, body_ids)
            face_ids = filter_elements("face_id", voice, face_ids)
            frame_ids = filter_elements("frame_id", voice, frame_ids)
        # Update the assigned attributes
        if page_index is not None:
            target_page = self.pages[page_index]
            for to_be_updateds, ids in zip(
                [
                    target_page.texts,
                    target_page.bodies,
                    target_page.faces,
                    target_page.frames,
                ],
                [text_ids, body_ids, face_ids, frame_ids],
            ):
                to_be_updateds = cast(
                    List[Text] | List[Body] | List[Face] | List[Frame], to_be_updateds
                )
                reset_attrib("assigned", to_be_updateds)
                update_attrib("assigned", to_be_updateds, ids)
        else:
            for page_index in range(len(self.pages)):
                target_page = self.pages[page_index]
                for to_be_updateds, ids in zip(
                    [
                        target_page.texts,
                        target_page.bodies,
                        target_page.faces,
                        target_page.frames,
                    ],
                    [text_ids, body_ids, face_ids, frame_ids],
                ):
                    to_be_updateds = cast(
                        List[Text] | List[Body] | List[Face] | List[Frame],
                        to_be_updateds,
                    )
                    reset_attrib("assigned", to_be_updateds)
                    update_attrib("assigned", to_be_updateds, ids)

    # check methods
    def check_overlapping_voice_ids(self):
        """Check the overlapping voice IDs

        Raises:
            ValueError: If any voice ID is duplicated
        """
        voice_ids = set()
        for voice in self.voices:
            if voice.id in voice_ids:
                raise ValueError(f"Overlapping voice ID: {voice.id}")
            voice_ids.add(voice.id)

    def check_overlapping_voice_indices(self):
        """Check the overlapping voice indices

        Raises:
            ValueError: If any voice index is duplicated
        """
        voice_indices = set()
        for voice in self.voices:
            if voice.index in voice_indices:
                raise ValueError(f"Overlapping voice index: {voice.index}")
            voice_indices.add(voice.index)

    def check_consistency_of_voice_indices(self):
        """Check the consistency of the voice indices

        Raises:
            ValueError: If the voice indices are not consistent
        """
        if len(self.voices) == 0:
            return
        # check the order of voice indices
        for i in range(len(self.voices) - 1):
            if self.voices[i].index != i:
                raise ValueError(f"Index mismatch: {self.voices[i].index} != {i}")
            if self.voices[i].index >= self.voices[i + 1].index:
                raise ValueError(
                    f"Voice index is not consistent: {self.voices[i].index} >= {self.voices[i + 1].index}"
                )

    def sanity_check(self: MangaVox):
        """Sanity check for the MangaVox object

        Raises:
            ValueError: If any of the required fields are empty or invalid
        """
        for voice in self.voices:
            voice.sanity_check()
        self.characters.sanity_check()
        # check the uniqueness of the voice IDs
        self.check_overlapping_voice_ids()
        # check the uniqueness of the voice index
        self.check_overlapping_voice_indices()
        # check the consistency of the voice indices
        self.check_consistency_of_voice_indices()

    # get methods
    def get_voice_by_id(self, target_id: str) -> Optional[Voice]:
        """Find the voice by ID

        Args:
            target_id (str): Target ID

        Returns:
            Optional[Voice]: An ExtendedVoice object
        """
        for voice in filter(lambda x: x.id == target_id, self.voices):
            return voice
        return None

    def get_voice_indices_by_time(self, target_time: float) -> List[int]:
        """Find the voice indices that are active at the target time

        Args:
            target_time (float): Target time

        Returns:
            List[int]: A list of voice indices
        """
        return [
            i
            for i, voice in enumerate(self.voices)
            if voice.start <= target_time <= voice.end
        ]

    # generate methods
    def sequential_generate_annotations_on_image(
        self,
        time_list: List[float],
        image_root: Path,
        frame_size: Tuple[int, int],
        verbose: bool = False,
        n_threads: int | None = None,
    ):
        """Generate the annotated images sequentially

        Args:
            time_list (List[float]): A list of target times
            image_root (Path): Path to the Manga109 image root directory
            frame_size (Tuple[int, int]): Frame size of the output video
            verbose (bool): If True, print debug information
            n_threads (int): Number of threads to use for parallel processing. If -1, use all available threads.

        Yields:
        """

        #
        def filter_elements(
            target_frame_ids: str,
            target_list: List[Frame] | List[Face] | List[Body] | List[Text],
        ) -> List[Frame | Face | Body | Text]:
            return list(
                filter(lambda x: x.id in target_frame_ids.split(","), target_list)
            )

        # Sanity check
        if self.pages is None:
            raise ValueError("Pages not found in MangaVox object")
        #
        self.voices = sorted(self.voices, key=lambda x: x.start)
        # Create a meta sequence for the current page
        meta_sequence = []
        current_page_index = 0
        current_max_voice_index = -1
        prev_matched_voice_indices: List[int] = []
        for i, current_time in enumerate(time_list):
            # Remove inactive voices
            matched_voice_indices = [
                index
                for index in prev_matched_voice_indices
                if self.voices[index].end > current_time
            ]
            # Add new active voices
            if len(matched_voice_indices) > 0:
                current_max_voice_index = max(
                    current_max_voice_index, max(matched_voice_indices)
                )
            for index in range(current_max_voice_index + 1, len(self.voices)):
                if self.voices[index].start <= current_time <= self.voices[index].end:
                    matched_voice_indices.append(index)
                elif self.voices[index].start > current_time:
                    break
            # check matched_voice_indices change
            if i == 0 or (matched_voice_indices != prev_matched_voice_indices):
                # Update the current page index
                page_indices = cast(
                    List[int],
                    [
                        self.voices[index].page_index
                        for index in matched_voice_indices
                        if self.voices[index].page_index is not None
                    ],
                )
                if len(set(page_indices)) > 1:
                    # background_chatterではないものがユニークであればOK
                    org_page_indices = page_indices
                    page_indices = []
                    for index in matched_voice_indices:
                        if self.voices[index].page_index is None:
                            continue
                        if (
                            self.characters.get_character_details_by_id(
                                self.voices[index].character_id
                            ).roman
                            == "gaya"
                        ):
                            continue
                        page_indices.append(cast(int, self.voices[index].page_index))
                    if len(set(page_indices)) > 1:
                        raise ValueError(f"page_indices is not unique: {page_indices}")
                    if verbose:
                        logger.info(
                            f"Ignore background_chatter to make page_index unique: {org_page_indices} -> {page_indices}"
                        )
                    del org_page_indices
                if len(page_indices) > 0:
                    current_page_index = page_indices[0]
                # write annotations
                to_be_drawn: Dict[str, Any] = {
                    "n_calls": 1,
                    "page": current_page_index,
                    "voice": [self.voices[i] for i in matched_voice_indices],
                    "frame": [],
                    "face": [],
                    "body": [],
                    "text": [],
                }
                for voice in [self.voices[i] for i in matched_voice_indices]:
                    if voice.frame_id is not None:
                        frame_list = self.pages.page[current_page_index].frames
                        for frame in filter_elements(voice.frame_id, frame_list):
                            to_be_drawn["frame"].append(frame)
                    if voice.body_id is not None:
                        body_list = self.pages.page[current_page_index].bodies
                        for body in filter_elements(voice.body_id, body_list):
                            to_be_drawn["body"].append(body)
                    if voice.face_id is not None:
                        face_list = self.pages.page[current_page_index].faces
                        for face in filter_elements(voice.face_id, face_list):
                            to_be_drawn["face"].append(face)
                    if voice.text_id is not None:
                        text_list = self.pages.page[current_page_index].texts
                        for text in filter_elements(voice.text_id, text_list):
                            to_be_drawn["text"].append(text)
                # create meta sequence
                meta_sequence.append(to_be_drawn)
            else:
                meta_sequence[-1]["n_calls"] += 1
            # update the previous matched voice indices
            prev_matched_voice_indices = matched_voice_indices
        # generate frames
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            results = []
            total_n_calls = 0
            for meta in meta_sequence:
                results.append(
                    executor.submit(
                        _generate_image,
                        meta["n_calls"],
                        meta["page"],
                        meta["voice"],
                        meta["frame"],
                        meta["face"],
                        meta["body"],
                        meta["text"],
                        image_root,
                        frame_size,
                    )
                )
                total_n_calls += meta["n_calls"]
            with tqdm(
                total=total_n_calls,
                desc="Generating annotated images",
                smoothing=0.6,
                dynamic_ncols=True,
                mininterval=1.0,
                disable=not verbose,
            ) as pbar:
                for result in results:
                    image, n_calls = result.result()
                    for _ in range(n_calls):
                        yield image
                    pbar.update(n_calls)


def _generate_image(
    n_calls: int,
    page_index: int,
    voice_list: List[Voice],
    frame_list: List[Frame],
    face_list: List[Face],
    body_list: List[Body],
    text_list: List[Text],
    image_root: Path,
    frame_size: Tuple[int, int],
) -> Tuple[numpy.ndarray, int]:
    """Generate an annotated image for the given page index and voice list

    Args:
        n_calls (int): Number of calls to generate the image
        page_index (int): Page index to generate the image for
        voice_list (List[Voice]): List of voices to annotate
        frame_list (List[Frame]): List of frames to annotate
        face_list (List[Face]): List of faces to annotate
        body_list (List[Body]): List of bodies to annotate
        text_list (List[Text]): List of texts to annotate
        image_root (Path): Path to the Manga109 image root directory
        frame_size (Tuple[int, int]): Frame size of the output video

    Returns:
        Tuple[numpy.ndarray, int]: The annotated image as a numpy array and the number of calls
    """
    image = Image.open(f"{image_root}/{page_index:03d}.jpg")
    if len(voice_list) > 0:
        for frame in frame_list:
            frame.draw_rectangle(image)
        for face in face_list:
            face.draw_rectangle(image)
        for body in body_list:
            body.draw_rectangle(image)
        for text in text_list:
            text.draw_rectangle(image)
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=40)
        draw.text((0, 0), "Annotated", font=font, fill="red")
    resized_image = image.resize(frame_size)
    numpy_resized_image = numpy.array(resized_image)
    video_frame = cv2.cvtColor(numpy_resized_image, cv2.COLOR_RGB2BGR)
    return video_frame, n_calls
