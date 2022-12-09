"""Schedule data structures and operations."""
import dacite
import dataclasses
import json
import orekitfactory.time
import typing
import uuid

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
