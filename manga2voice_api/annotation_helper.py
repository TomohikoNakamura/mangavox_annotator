"""manga2voice_api.annotation_helper
===================================
This module provides helper functions and classes for handling annotations in the MangaVox format.
It includes functions to convert dictionaries to dataclasses, manage voice annotations, and handle MangaVox annotations.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Set, Type, cast

from loguru import logger
from xsdata.formats.dataclass.models.elements import XmlType
from xsdata.formats.dataclass.parsers import DictDecoder

from manga2voice_api.manga109_ann import Body, Face, Frame, Text
from manga2voice_api.mangavox_ann import MangaVox, Voice


def dict_to_dataclass(cls: Type, data: dict) -> Any:
    """Convert a dictionary to a dataclass instance

    Args:
        cls (Type): The dataclass type to convert to
        data (dict): The dictionary to convert

    Returns:
        Any: An instance of the dataclass
    """
    if not isinstance(data, dict):
        # Basic data types (int, float, str, etc.) are returned as is
        return data

    fieldtypes = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    return cls(
        **{
            key: dict_to_dataclass(fieldtypes[key], value)
            for key, value in data.items()
        }
    )


@dataclasses.dataclass
class Note:
    """A note element

    Attributes:
        text (str): The text of the note
    """

    text: str = dataclasses.field(default="", metadata={"type": XmlType.TEXT})


@dataclasses.dataclass(kw_only=True)
class ExtendedVoice(Voice):
    """Extended Voice class with additional attributes and methods

    Attributes:
        id (str): The voice id
        index (int): The voice index
        start (float): The start time of the voice
        end (float): The end time of the voice
        episode_index (int): The episode index
        actor_id (str): The actor id
        character_id (str): The character id
        text_id (Optional[str]): The text id
        page_index (Optional[int]): The page index
        frame_id (Optional[str]): The frame id
        face_id (Optional[str]): The face id
        body_id (Optional[str]): The body id
        text (str): The spoken text
        audio_id (Optional[str]): The audio id
        frame_assignment_reason (Optional[str]): The frame assignment reason
        face_assignment_reason (Optional[str]): The face assignment reason
        body_assignment_reason (Optional[str]): The body assignment reason
        note (Note): A note element
        annotation_comment (Optional[Note]): An annotation comment element
    """
    # assignment reasons: manual, IoU, dialog
    frame_assignment_reason: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    face_assignment_reason: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    body_assignment_reason: Optional[str] = dataclasses.field(
        default=None, metadata={"type": XmlType.ATTRIBUTE}
    )
    # note element
    note: Note = dataclasses.field(
        default_factory=Note, metadata={"type": XmlType.ELEMENT}
    )
    annotation_comment: Optional[Note] = dataclasses.field(
        default=None, metadata={"type": XmlType.ELEMENT}
    )

    def update(self, annotation: Dict, verbose: bool = False) -> List[Dict]:
        """Update the voice with the given annotation

        Args:
            annotation (Dict): A dictionary containing the new annotation data
            verbose (bool): Whether to print the log

        Returns:
            List[Dict]: A list of change logs
        """
        annotation_dict: Dict = DictDecoder().decode(annotation)
        annotation = dict_to_dataclass(ExtendedVoice, annotation_dict)
        change_logs = []
        # check start, end times
        for key in ["start", "end"]:
            current_value = getattr(self, key)
            new_value = getattr(annotation, key)
            if round(current_value, 3) != round(new_value, 3):
                change_logs.append({"key": key, "from": current_value, "to": new_value})
                self._apply_change_log(change_logs[-1], verbose)
        # check id correspondence
        for key in [
            "text_id",
            "page_index",
            "frame_id",
            "body_id",
            "face_id",
            "character_id",
            "actor_id",
            "audio_id",
            "text",
        ]:
            current_value = getattr(self, key)
            new_value = getattr(annotation, key)
            if current_value != new_value:
                change_logs.append({"key": key, "from": current_value, "to": new_value})
                self._apply_change_log(change_logs[-1], verbose)
        # check annotation comment
        for key in ["annotation_comment"]:
            current_value = getattr(self, key)
            new_value = getattr(annotation, key)
            # update annotation comment
            if current_value != new_value:
                change_logs.append(
                    {
                        "key": key,
                        "from": current_value
                        if current_value is None
                        else current_value.text,
                        "to": new_value if new_value is None else new_value.text,
                    }
                )
                self._apply_change_log(change_logs[-1], verbose)
        return change_logs

    def _apply_change_log(
        self,
        change_item: Dict,
        verbose: bool = False,
        update_abnormal_keys: bool = False,
    ):
        """Apply a change log item to the voice instance

        Args:
            change_item (Dict): A change log item
                key: str
                from: Any
                to: Any
            verbose (bool): Whether to print the log
            update_abnormal_keys (bool): Whether to update abnormal keys
        """
        key = change_item["key"]
        current_value = change_item["from"]
        new_value = change_item["to"]
        if key == "start" or key == "end":
            # sanity check
            if round(getattr(self, key), 3) != round(current_value, 3):
                raise ValueError(f"Change log is not applicable: {self.id}, {key}")
            # set
            if verbose:
                logger.info(
                    f"{self.id}, {key}: {round(current_value, 3)} -> {round(new_value, 3)}"
                )
            setattr(self, key, new_value)
        elif key in [
            "text_id",
            "page_index",
            "frame_id",
            "body_id",
            "face_id",
            "character_id",
            "actor_id",
            "audio_id",
            "text",
        ]:
            # sanity check
            if getattr(self, key) != current_value:
                raise ValueError(f"Change log is not applicable: {self.id}, {key}")
            # set
            if verbose:
                logger.info(f"{self.id}, {key}: {current_value} -> {new_value}")
            setattr(self, key, new_value)
            if key in ["frame_id", "face_id", "body_id"]:
                reason_key = f"{key[: key.find('_')]}_assignment_reason"
                current_value = getattr(self, reason_key)
                if current_value is None:
                    if verbose:
                        logger.info(f"{self.id}, {reason_key}: None -> manual")
                    setattr(self, reason_key, "manual")
                elif "manual" not in current_value:
                    if verbose:
                        logger.info(
                            f"{self.id}, {reason_key}: {current_value} -> {current_value}+manual"
                        )
                    setattr(self, reason_key, current_value + "+manual")
                elif "manual" in current_value:
                    pass
                else:
                    raise ValueError(f"Invalid {reason_key}: {current_value}")
        elif key == "annotation_comment":
            if getattr(self, key) is None:
                if current_value is not None:
                    raise ValueError(f"Change log is not applicable: {self.id}, {key}")
                if verbose:
                    logger.info(f"{self.id}, {key}: None -> {new_value}")
                setattr(self, key, Note(new_value))
            else:
                if getattr(self, key).text != current_value:
                    raise ValueError(f"Change log is not applicable: {self.id}, {key}")
                if new_value is None or new_value == "":
                    # remove empty annotation comment
                    if verbose:
                        logger.info(f"{self.id}, {key}: {current_value} -> None")
                    setattr(self, key, None)
                else:
                    # update annotation comment
                    if verbose:
                        logger.info(f"{self.id}, {key}: {current_value} -> {new_value}")
                    getattr(self, key).text = new_value
        else:
            if update_abnormal_keys:
                if verbose:
                    logger.info(
                        f"Update abnormal key: {self.id}, {key}: {current_value} -> {new_value}"
                    )
                if not hasattr(self, key):
                    raise ValueError(f"Invalid key: {key}")
                setattr(self, key, new_value)
            else:
                raise ValueError(f"Invalid key: {key}")

    def diff(self, target: ExtendedVoice) -> List[Dict]:
        """Compare the current voice with the target voice and return the differences

        Args:
            target (ExtendedVoice): The target voice to compare with

        Returns:
            List[Dict]: A list of dictionaries containing the differences
        """
        changelist = []
        key_list = [_ for _ in super().__annotations__] + [
            _ for _ in self.__annotations__
        ]
        for key in key_list:
            my_value = getattr(self, key)
            target_value = getattr(target, key)
            if my_value != target_value:
                changelist.append(
                    {
                        "key": key,
                        "from": my_value.text
                        if isinstance(my_value, Note)
                        else my_value,
                        "to": target_value.text
                        if isinstance(target_value, Note)
                        else target_value,
                    }
                )
        return changelist

    def export_as_public_format(self) -> Voice:
        """Export the voice as a public format Voice object

        Returns:
            Voice: A Voice object with the public format
        """
        return Voice(
            id=self.id,
            index=self.index,
            start=self.start,
            end=self.end,
            episode_index=self.episode_index,
            actor_id=self.actor_id,
            character_id=self.character_id,
            text_id=self.text_id,
            page_index=self.page_index,
            frame_id=self.frame_id,
            face_id=self.face_id,
            body_id=self.body_id,
            text=self.text,
            audio_id=self.audio_id,
        )

@dataclasses.dataclass(kw_only=True)
class MangaVoxForAnnotation(MangaVox):
    """A MangaVox object for annotation

    Attributes:
        title (str): The title of the MangaVox annotation
        version (str): The version of the MangaVox annotation
        manga109_version (str): The version of the Manga109 annotation
        characters (Characters): The characters in the MangaVox annotation
        voices (List[ExtendedVoice]): A list of ExtendedVoice objects representing the aligned voices
        pages (Optional[Pages]): The pages in the MangaVox annotation
        created (str): The creation timestamp of the annotation
        last_modified (str): The last modified timestamp of the annotation
    """
    created: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    last_modified: str = dataclasses.field(metadata={"type": XmlType.ATTRIBUTE})
    voices: List[ExtendedVoice] = dataclasses.field(
        default_factory=list,
        metadata={"type": XmlType.ELEMENT, "name": "aligned_voice"},
    ) # type: ignore

    def reset_index(self):
        """Reset the indices of the voice elements"""
        n_voices = len(self.voices)
        self.voices = sorted(self.voices, key=lambda x: x.start)
        if n_voices != len(self.voices):
            raise ValueError(f"Length mismatch: {n_voices} != {len(self.voices)}")
        for i, voice in enumerate(self.voices):
            if voice.index != i:
                logger.info(f"Reset index: {voice.index} -> {i}")
                voice.index = i

    def remove_unused_characters(self):
        """Remove the unused characters"""
        used_character_ids = []
        for page in self.pages.page:
            for body in page.bodies:
                if body.character is not None:
                    used_character_ids.append(body.character)
            for face in page.faces:
                if face.character is not None:
                    used_character_ids.append(face.character)
        used_character_ids = set(
            [voice.character_id for voice in self.voices] + used_character_ids
        )

        for character in self.characters.character:
            if character.id not in used_character_ids:
                logger.info(f"Remove character: {character.id} {character.name}")
                self.characters.character.remove(character)

    def check_undefined_characters(self):
        """Check the undefined characters
        
        Raises:
            ValueError: If any voice or page body/face has an undefined character ID
        """
        character_ids = set([character.id for character in self.characters.character])
        for voice in self.voices:
            if voice.character_id not in character_ids:
                raise ValueError(f"Undefined character: {voice.character_id}")
        for page in self.pages.page:
            for body in page.bodies:
                if body.character is not None and body.character not in character_ids:
                    raise ValueError(f"Undefined character: {body.character}")
            for face in page.faces:
                if face.character is not None and face.character not in character_ids:
                    raise ValueError(f"Undefined character: {face.character}")

    def update_assigned(self, page_index: Optional[int] = None):
        """Update the assigned attribute of the voices

        Args:
            page_index (int, optional): The page index to update. If None, update all pages.

        """
        if self.pages is None:
            raise ValueError("Pages are not defined in the MangaVox annotation")

        def filter_elements(key: str, target_element: ExtendedVoice, ids: Set):
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
        if (
            page_index
        ):  # update only text/body/face/frame assigned attributes in the specified page
            target_voices = filter(lambda x: x.page_index == page_index, self.voices)
        else:
            target_voices = self.voices # type: ignore
        for voice in target_voices:
            text_ids = filter_elements("text_id", voice, text_ids)
            body_ids = filter_elements("body_id", voice, body_ids)
            face_ids = filter_elements("face_id", voice, face_ids)
            frame_ids = filter_elements("frame_id", voice, frame_ids)
        # Update the assigned attributes
        if (
            page_index
        ):  # update only text/body/face/frame assigned attributes in the specified page
            target_page = self.pages.page[page_index]
            for to_be_updateds, ids in zip(
                [
                    target_page.texts,
                    target_page.bodies,
                    target_page.faces,
                    target_page.frames,
                ],
                [text_ids, body_ids, face_ids, frame_ids],
            ):
                to_be_updateds = cast(List[Text] | List[Body] | List[Face] | List[Frame], to_be_updateds)
                # Reset the assigned attribute
                reset_attrib("assigned", to_be_updateds)
                update_attrib("assigned", to_be_updateds, ids)
        else:
            for page_index in range(len(self.pages.page)):
                target_page = self.pages.page[page_index]
                for to_be_updateds, ids in zip(
                    [
                        target_page.texts,
                        target_page.bodies,
                        target_page.faces,
                        target_page.frames,
                    ],
                    [text_ids, body_ids, face_ids, frame_ids],
                ):
                    to_be_updateds = cast(List[Text] | List[Body] | List[Face] | List[Frame], to_be_updateds)
                    reset_attrib("assigned", to_be_updateds)
                    update_attrib("assigned", to_be_updateds, ids)

    def apply_change_logs(
        self, change_logs: List[Dict], update_abnormal_keys: bool = False
    ):
        """Apply the change logs to the voices

        Args:
            change_logs (List[Dict]): A list of change logs
            update_abnormal_keys (bool): Whether to update abnormal keys

        Raises:
            ValueError: If the change log is not applicable
        """
        for change in change_logs:
            if "change" in change:
                for voice in self.voices:
                    if voice.id == change["voice_id"]:
                        for change_item in change["change"]:
                            voice._apply_change_log(
                                change_item, update_abnormal_keys=update_abnormal_keys
                            )
                            logger.info(
                                f"{voice.id}, {change_item['key']}: {change_item['from']} -> {change_item['to']}"
                            )
            elif "delete" in change:
                for i, voice in enumerate(self.voices):
                    if voice.id == change["voice_id"]:
                        logger.info(f"Delete voice: {voice.id}")
                        del self.voices[i]
                        break
            elif "add" in change:
                voice = dict_to_dataclass(ExtendedVoice, change["add"])
                # check the uniqueness of the voice ID
                if voice.id in [voice.id for voice in self.voices]:
                    raise ValueError(f"Duplicated voice ID: {voice.id}")
                self.voices.append(voice)
                logger.info(f"Add voice: {voice.id}")
            else:
                raise ValueError(f"Invalid change log: {change}")
        self.voices = sorted(self.voices, key=lambda x: x.start)

    def check_change_applicability(self, config_data: Dict) -> bool:
        """Check if the change logs are applicable to the current annotation

        Args:
            config_data (Dict): The configuration data containing the annotation version

        Raises:
            ValueError: If the annotation version does not match the current annotation
        """
        if config_data["annotation_version"]["created"] != self.created:
            raise ValueError(
                f"Annotation version mismatch: {config_data['annotation_version']['created']} != {self.created}"
            )
        if config_data["annotation_version"]["last_modified"] != self.last_modified:
            raise ValueError(
                f"Annotation version mismatch: {config_data['annotation_version']['last_modified']} != {self.last_modified}"
            )
        return True

