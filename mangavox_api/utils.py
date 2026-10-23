"""mangavox_api.utils
===================================
This module provides utility functions and classes for handling annotations in the MangaVox format.
It includes a mixin class for reading and writing annotation files, computing hash values, and managing timestamps.

Copyright (C) 2025 National Institute of Advanced Industrial Science and Technology (AIST)
"""

from __future__ import annotations

import dataclasses
import hashlib
from abc import ABC
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self, cast

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig


def get_timestamp_in_iso8601_format() -> str:
    """Get the current timestamp in ISO8601 format

    Returns:
        str: The current timestamp in ISO8601 format
    """
    return datetime.now(timezone.utc).isoformat()


class AnnotationMixin(ABC):
    """Base class for annotation objects

    This class provides methods for reading and writing annotation files,
    computing hash values, and managing timestamps.
    It is intended to be used as a mixin for other annotation classes.
    """

    @classmethod
    def read(cls, input_filename: str | Path) -> Self:
        """Read an annotation file and return an instance of the class

        Args:
            input_filename (str | Path): Path to the input file

        Returns:
            AnnotationBase: An instance of the class
        """
        if isinstance(input_filename, str):
            input_filename = Path(input_filename)
        parser = XmlParser()
        manga109 = parser.from_path(input_filename, cls)
        return manga109

    def write(self, filename: str | Path):
        """Write the annotation object to a file in XML format

        Args:
            filename (str | Path): Path to the output file
        """
        xml_config = SerializerConfig(pretty_print=True)
        serializer = XmlSerializer(config=xml_config)
        ret = serializer.render(self)
        with open(filename, "w", encoding="utf-8") as fp:
            fp.write(ret)

    def compute_hash(self) -> str:
        """Compute the hash value

        This method computes a hash value based on the dataclass fields.

        Returns:
            str: The hash value
        """
        if not dataclasses.is_dataclass(self):
            raise TypeError("compute_hash can only be called on dataclass instances")
        data_str = str(dataclasses.asdict(cast(Any, self)))
        return hashlib.sha256(data_str.encode()).hexdigest()
