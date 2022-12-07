"""Schedule data structures and operations."""
import dataclasses
import orekitfactory.time
import typing
import uuid


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScheduleActivity:
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
            object.__setattr__(self, "id", uuid.uuid4())


    def __str__(self) -> str:
        return f"sat={self.sat_id} payload={self.payload_id} start={self.interval.start} stop={self.interval.stop}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class Schedule:
    """Schedule."""

    id: str
    intervals: orekitfactory.time.DateIntervalList = None
    activities: list[ScheduleActivity] = None

    def __post_init__(self):
        """Finalize the object."""
        if not self.id:
            object.__setattr__(self, "id", str(uuid.uuid4()))

        if not self.intervals:
            object.__setattr__(self, "intervals", orekitfactory.time.DateIntervalList())

        if not self.activities:
            object.__setattr__(self, "activities", ())
        else:
            object.__setattr__(self, "activities", tuple(self.activities))

    def with_intervals(self, ivl: orekitfactory.time.DateInterval | orekitfactory.time.DateIntervalList):
        intervals = orekitfactory.time.list_union(self.intervals, ivl)

        return Schedule(id=self.id, intervals=intervals, activities=self.activities)

    def with_activities(self, activities: typing.Sequence[ScheduleActivity]):
        return Schedule(id=self.id, intervals=self.intervals, activities=tuple(activities))
