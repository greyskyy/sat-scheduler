"""Core scheduler data classes."""
import dataclasses
import dacite
import enum
import json
import orekitfactory.time
import typing
import uuid

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


_DACITE_CONFIG = dacite.Config(
    type_hooks={
        orekitfactory.time.DateInterval: orekitfactory.time.as_dateinterval,
        orekitfactory.time.DateIntervalList: orekitfactory.time.as_dateintervallist,
    }
)
"""Dacite config used for creating dataclasses from dictionaries."""


class ScheduleBase:
    """Base class for schedule data classes."""

    def to_dict(self) -> dict:
        """Convert this object to a dictionary.

        Returns:
            dict: The dictionary for this class.
        """
        return {f.name: self.__getattribute__(f.name) for f in dataclasses.fields(self)}

    def to_json(self) -> str:
        """Convert this object to a json structure.

        Returns:
            str: A json string representing this object.
        """
        return ScheduleEncoder().encode(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict):
        """Create a class instance from the provided dictionary.

        Args:
            data (dict): The dictionary.

        Returns:
            typing.Any: The data class instance.
        """
        return dacite.from_dict(data_class=cls, data=data, config=_DACITE_CONFIG)

    @classmethod
    def from_json(cls, json_data):
        """Create a class instance from the provided json.

        Args:
            json_data (str|bytearray|file-like): The source json. May be a string, bytearray, or any object
            provided a `read()` method.

        Returns:
            _T: The class instance.
        """
        read = getattr(json_data, "read", None)
        if read and callable(read):
            data = json.load(json_data)
        else:
            data = json.loads(json_data)
        return cls.from_dict(cls, data)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScheduleActivity(ScheduleBase):
    """Individual schedule activity."""

    interval: orekitfactory.time.DateInterval
    """Activity interval."""
    id: typing.Optional[str] = None
    """Unique id of this activity, auto-generated if not provided."""
    sat_id: typing.Optional[str] = None
    """Satellite id for this activity."""
    payload_id: typing.Optional[str] = None
    """Payload id for this activity."""
    properties: typing.Optional[dict] = None
    """Extra properties for this activity."""

    def __post_init__(self):
        """Finalize the object."""
        if not self.id:
            object.__setattr__(self, "id", str(uuid.uuid4()))

    def __str__(self) -> str:
        """The string representation of this object.

        Returns:
            str: This object, as a string.
        """
        return f"sat={self.sat_id} payload={self.payload_id} start={self.interval.start} stop={self.interval.stop}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class Schedule(ScheduleBase):
    """Schedule."""

    id: str
    """The schedule id."""
    intervals: orekitfactory.time.DateIntervalList = None
    """Scheduled activity intevals."""
    activities: list[ScheduleActivity] = None
    """Scheduled payload activities."""

    def __post_init__(self):
        """Finalize the object."""
        if not self.id:
            object.__setattr__(self, "id", str(uuid.uuid4()))

        if not self.intervals:
            object.__setattr__(self, "intervals", orekitfactory.time.DateIntervalList())

        if not self.activities:
            object.__setattr__(self, "activities", ())
        else:
            self.activities.sort(key=lambda a: a.interval)
            object.__setattr__(self, "activities", tuple(self.activities))

    def add_intervals(self, ivl: orekitfactory.time.DateInterval | orekitfactory.time.DateIntervalList):
        """Copy the object, adding the intervals to the schedule.

        Args:
            ivl (orekitfactory.time.DateInterval | orekitfactory.time.DateIntervalList): The new set of intervals to
            combine with the existing schedule intervals.

        Returns:
            Schedule: The new schedule instance.
        """
        intervals = orekitfactory.time.list_union(self.intervals, ivl)

        return Schedule(id=self.id, intervals=intervals, activities=self.activities)

    def with_intervals(self, ivl: orekitfactory.time.DateInterval | orekitfactory.time.DateIntervalList):
        """Copy the object with a new set of intervals.

        Args:
            ivl (orekitfactory.time.DateInterval | orekitfactory.time.DateIntervalList): The new set of intervalus

        Returns:
            Schedule: The new schedule instance.
        """
        return Schedule(id=self.id, intervals=orekitfactory.time.as_dateintervallist(ivl), activities=self.activities)

    def with_activities(self, activities: typing.Sequence[ScheduleActivity]):
        """Copy this schedule with a new set of payload activities.

        Args:
            activities (typing.Sequence[ScheduleActivity]): The new activity sequence to add.

        Returns:
            Schedule: The new schedule instance.
        """
        return Schedule(id=self.id, intervals=self.intervals, activities=tuple(activities))


class ScheduleEncoder(json.JSONEncoder):
    """JsonEncoder class that properly encodes `Schedule` and `ScheduleActivity` instances."""

    def default(self, o):
        """Encode the object to json.

        Args:
            o (typing.Any): The object to be encoded.

        Returns:
            typing.Any: A serializable object type.
        """
        if isinstance(o, Schedule):
            return o.to_dict()
        elif isinstance(o, ScheduleActivity):
            return o.to_dict()
        elif isinstance(o, orekitfactory.time.DateInterval):
            return [str(o.start), str(o.stop)]
        elif isinstance(o, orekitfactory.time.DateIntervalList):
            return [[str(i.start), str(i.stop)] for i in o]
        else:
            return super().default(o)
