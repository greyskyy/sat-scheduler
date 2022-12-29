"""Core datastructures and functions used across various subcomponents."""
import dataclasses
import typing

from org.orekit.propagation import BoundedPropagator

from ..utils import DictableDataclass, IterableDataclass

from .satellite import SatelliteModel


@dataclasses.dataclass(frozen=True, eq=True)
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
