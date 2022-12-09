"""Core scheduler data classes."""
import dataclasses
import enum
import typing

from org.orekit.propagation import BoundedPropagator

from ..utils import IterableDataclass, DictableDataclass
from ..models import SatelliteModel
from ..preprocessor import PreprocessedAoi


def filter_aois_no_access(aois: typing.Sequence[PreprocessedAoi]) -> typing.Iterable[PreprocessedAoi]:
    """Filter the aois without accesses.

    Args:
        aois (typing.Sequence[PreprocessedAoi]): The aois to filter.

    Yields:
        Iterator[typing.Iterable[PreprocessedAoi]]: An interable of aois with accesses.
    """
    for aoi in aois:
        if len(aoi.intervals):
            yield aoi


@dataclasses.dataclass(frozen=True)
class SatPayloadId(IterableDataclass, DictableDataclass):
    """Unique key for a schedule."""

    sat_id: str = None
    """Satellite id."""
    payload_id: str = None
    """Payload id."""

    def __getitem__(self, index):
        """Get the indexed item.

        Args:
            index (int): Index

        Raises:
            IndexError: When index >=2.

        Returns:
            str: The value.
        """
        if index == 0:
            return self.sat_id
        elif index == 1:
            return self.payload_id
        else:
            raise IndexError(f"Index {index} out of range.")

    def __len__(self) -> int:
        """Length of this sequence (always return 2).

        Returns:
            int: Returns 2.
        """
        return 2


@dataclasses.dataclass(frozen=True, kw_only=True)
class Platform:
    """The satellite platform."""

    model: SatelliteModel
    """The satelite model."""
    ephemeris: BoundedPropagator
    """The propagated ephemeris."""

    @property
    def id(self) -> str:
        """The satellite id."""
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
    EXCEEDED_PAYLOAD_DUTY_CYCLE = 30
    """The aoi couldn't be scheduled because the payload was at its duty cycle limit."""
    SOLVER_INFEASIBLE_SOLUTION = 190
    """The solver problem was infeasible."""
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
        """Retrive the value for the provided key.

        Args:
            __key (str): The platform id key.

        Returns:
            Platform: The platform with the provided id.
        """
        return self.__data[__key]

    def __iter__(self):
        """Iterate over this collection."""
        return self.__data.__iter__()

    def __len__(self) -> int:
        """Number of platforms in this collection."""
        return self.__data.__len__()

    def generate_ids(
        self, include_platforms: bool = True, include_sensors: bool = True
    ) -> typing.Sequence[SatPayloadId]:
        """Generate the id sequence.

        Args:
            include_platforms (bool, optional): When true, include the satellite ids in the
            unique id sequence. Defaults to True.
            include_sensors (bool, optional): When true, include the payload ids in the unique id
            sequence. Defaults to True.

        Yields:
            Iterator[typing.Sequence[SatPayloadId]]: Sequence of ids.
        """
        for sat_id in self:
            if not include_sensors:
                yield SatPayloadId(sat_id=sat_id)
            else:
                for s in self[sat_id].model.sensors:
                    if not include_platforms:
                        yield SatPayloadId(payload_id=s.id)
                    else:
                        yield SatPayloadId(sat_id, s.id)
