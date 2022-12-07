"""Core scheduler data classes."""
import collections.abc
import dataclasses
import enum
import typing

from org.orekit.propagation import BoundedPropagator

from ..models import SatelliteModel
from ..preprocessor import PreprocessedAoi, PreprocessingResult, aois_from_results


@dataclasses.dataclass(frozen=True, kw_only=True)
class Platform:
    model: SatelliteModel
    ephemeris: BoundedPropagator

    @property
    def id(self) -> str:
        return self.model.id


class Result(enum.IntEnum):
    """Collection of common scheduling results.

    Various scheduling algorithms should use these set of results per aoi access interval.
    """

    # scheduled 0 - 24
    SCHEDULED = 0
    """The aoi is placed on the schedule."""
    ALREADY_SCHEDULED = 1
    """The aoi was satisfied by a pre-existing activity on the schedule."""
    #  other successes 25-50
    NOT_DUE = 20
    """The aoi was not due at the time."""
    # scheduling failures 100-199

    # pre-processing failures 200-300
    FAILED_QUALITY = 200
    """Failed quality constraints."""
    FAILED_GEOMETRY = 210
    """Failed the geometric constraints."""
    FAILED_SUN_GEOMETRY = 220
    """Failed solar geometry constraints."""
    NO_ACCESS = 299
    """There was no access to the aoi in the time interval."""

    NO_DATA = 999
    """Default value to use when no other data is available."""

    @classmethod
    def _missing_(cls, value: typing.Any) -> typing.Any:
        if isinstance(value, str):
            value = value.replace("-", "_")
            for member in cls:
                if member.name.lower() == value.lower():
                    return member

        return super()._missing_(value)


class Platforms(typing.Mapping):
    """Platform collection."""

    def __init__(self, platforms: typing.Sequence[Platform]):
        """Class constructor.

        Args:
            platforms (typing.Sequence[Platform]): Sequence of platforms to add to this collection.
        """
        self.__data = {p.id: p for p in platforms}

    def __getitem__(self, __key: str) -> Platform:
        return self.__data[__key]

    def __iter__(self):
        """Iterate over this collection."""
        return self.__data.__iter__()

    def __len__(self) -> int:
        """Number of platforms in this collection."""
        return self.__data.__len__()
