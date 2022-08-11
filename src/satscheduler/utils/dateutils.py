"""Utility methods and classes."""
from dataclasses import dataclass
from datetime import timedelta
import functools
from typing import Iterable, Iterator
from org.orekit.time import AbsoluteDate, DateTimeComponents
from org.orekit.data import DataContext
from functools import cached_property, singledispatch


def string_to_absolutedate(iso_date: str, context: DataContext = None) -> AbsoluteDate:
    """Parse a string into an AbsoluteDate.

    Args:
        iso_date (str): The ISO-8601 time string
        context (DataContext, optional): The data context to use. Defaults to None.

    Returns:
        AbsoluteDate: The AbsoluteDate.
    """
    if not context:
        context = DataContext.getDefault()

    return AbsoluteDate(
        DateTimeComponents.parseDateTime(iso_date), context.getTimeScales().getUTC()
    )


@functools.total_ordering
class DateInterval:
    """Interval of time."""

    def __init__(self, start: AbsoluteDate, stop: AbsoluteDate):
        """Class constructor.

        Args:
            start (AbsoluteDate): The starting time.
            stop (AbsoluteDate): The stopping time.
        """
        self.__start = start
        self.__stop = stop

        if self.__start.compareTo(self.__stop) > 0:
            self.__start = stop
            self.__stop = start

    @property
    def start(self) -> AbsoluteDate:
        """Starting time of the interval.

        Returns:
            AbsoluteDate: The interval's starting time.
        """
        return self.__start

    @property
    def stop(self) -> AbsoluteDate:
        """Stopping time of the interval.

        Returns:
            AbsoluteDate: The interval's stop time
        """
        return self.__stop

    @cached_property
    def duration_secs(self) -> float:
        """The duration of this interval, in floating point seconds.

        Returns:
            float: The duration, in seconds.
        """
        return self.__stop.durationFrom(self.__start)

    @cached_property
    def duration(self) -> timedelta:
        """The duration as a `timedelta`.

        Returns:
            timedelta: The interval duration as a `timedelta`
        """
        return timedelta(seconds=self.duration_secs)

    @cached_property
    def to_tuple(self) -> tuple[AbsoluteDate]:
        """Representation of this interval as a tuple of (start,stop).

        Returns:
            tuple[AbsoluteDate]: The resulting tuple.
        """
        return (self.__start, self.__stop)

    @cached_property
    def to_list(self) -> list[AbsoluteDate]:
        """Representations of this interval a list of [start,stop].

        Returns:
            list[AbsoluteDate]: _description_
        """
        return [self.__start, self.__stop]

    def contains(
        self, other, startInclusive: bool = True, stopInclusive: bool = False
    ) -> bool:
        """Determine if this interval contains the provided time or interval.

        Args:
            other (AbsoluteDate|DateInterval): The date or interval to check for containment
            startInclusive (bool, optional): Whether the start of this interval is closed. Defaults to True.
            stopInclusive (bool, optional): Whether stop of this interval is closed. Defaults to False.

        Raises:
            TypeError: _description_

        Returns:
            bool: _description_
        """
        return _contained_in(
            other,
            self.start,
            self.stop,
            startInclusive=startInclusive,
            stopInclusive=stopInclusive,
        )

    def overlaps(
        self, other, startInclusive: bool = True, stopInclusive: bool = False
    ) -> bool:
        """Determine if this list contains the other list or date.

        Args:
            other (DateInterval): The interval to check for overlap
            startInclusive (bool, optional): Whether this interval's start point should be considered in overlap. Defaults to True.
            stopInclusive (bool, optional): Whether this interval's stop point should be considered in overlap. Defaults to False.

        Returns:
            bool: True when the intervals overlap; False otherwise
        """
        v0 = 0 if startInclusive else -1
        v1 = 0 if stopInclusive else 1

        if other is None:
            return False

        return (
            self.start.compareTo(other.stop) <= v0
            and self.stop.compareTo(other.start) >= v1
        )

    def union(self, other):
        """Combine this interval with another interval as the earliest start to latest stop of the two intervals.
        Note that this will return a valid union even if the intervals are non-overlapping.

        Args:
            other (DateInterval): The other interval.

        Returns:
            DateInterval: An interval describing the earliest start to the latest stop.
        """
        t0 = self.start if self.start.compareTo(other.start) <= 0 else other.start
        t1 = self.stop if self.stop.compareTo(other.stop) >= 0 else other.stop

        return DateInterval(t0, t1)

    def intersect(self, other):
        """Insersect this interval with another interval.

        Args:
            other (DateInterval): The other interval.

        Returns:
            DateInterval|None: Return the interval of overlap betwen the two intervals, or None.
        """
        t0 = self.start if self.start.compareTo(other.start) >= 0 else other.start
        t1 = self.stop if self.stop.compareTo(other.stop) <= 0 else other.stop

        if t0.compareTo(t1) < 0:
            return DateInterval(t0, t1)
        else:
            return None

    def strictly_before(self, other) -> bool:
        """Determine if this interval is strictly before the other date or interval.

        Args:
            other (AbsoluteDate|DateInterval): The other date or interval.

        Returns:
            bool: True when this interval is strictly before the other date or interval; False otherwise
        """
        return _strictly_before(other, self.__start, self.__stop)

    def strictly_after(self, other) -> bool:
        """Determine if this interval is strictly after the other date or interval.

        Args:
            other (DateInterval): The other date or interval.

        Returns:
            bool: True when this interval is strictly after the other date or interval; False otherwise
        """
        _strictly_after(other, self.__start, self.__stop)

    def __lt__(self, other) -> bool:
        if other is None:
            return False

        rv = self.start.compareTo(other.start)
        if rv == 0:
            return self.stop.compareTo(other.stop) < 0
        else:
            return rv < 0

    def __eq__(self, other) -> bool:
        if other is None:
            return False
        return self.start.equals(other.start) and self.stop.equals(other.stop)

    def __str__(self) -> str:
        return f"[{self.start.toString()}, {self.stop.toString()}]"


@singledispatch
def _contained_in(
    other,
    start: AbsoluteDate,
    stop: AbsoluteDate,
    startInclusive: bool = True,
    stopInclusive: bool = False,
) -> bool:
    """Determine whether the other object is contained in the interval defined by [start, stop]

    Args:
        other (AbsoluteDate|DateInterval): The other object to check for containment.
        start (AbsoluteDate): The interval start time.
        stop (AbsoluteDate): The interval stop time.
        startInclusive (bool, optional): Indicate the the interval should be closed at the start. Defaults to True.
        stopInclusive (bool, optional): Indicate the interval should be closed at the stop. Defaults to False.

    Raises:
        ValueError: When the `other` parameter is not a valid type handled by this method.

    Returns:
        bool: True when contained, False otherwise.
    """
    if other is None:
        return False
    raise ValueError(f"Unknown interval class type: {type(other)}")


@_contained_in.register
def _contained_in_date(
    date: AbsoluteDate,
    start: AbsoluteDate,
    stop: AbsoluteDate,
    startInclusive: bool = True,
    stopInclusive: bool = False,
) -> bool:
    v0 = 0 if startInclusive else -1
    v1 = 0 if stopInclusive else 1

    return start.compareTo(date) <= v0 and stop.compareTo(date) >= v1


@_contained_in.register
def _contained_in_ivl(
    ivl: DateInterval,
    start: AbsoluteDate,
    stop: AbsoluteDate,
    startInclusive: bool = True,
    stopInclusive: bool = False,
) -> bool:
    v0 = 0 if startInclusive else -1
    v1 = 0 if stopInclusive else 1

    return start.compareTo(ivl.start) <= v0 and stop.compareTo(ivl.stop) >= v1


@singledispatch
def _strictly_before(other, start: AbsoluteDate, stop: AbsoluteDate) -> bool:
    """Determine whether the other object is strictly before the interval defined by the start, stop interval.

    Args:
        other (None|AbsoluteDate|DateInterval): The object to check.
        start (AbsoluteDate): Start of the interval to check against.
        stop (AbsoluteDate): Stop of the interval to check against.

    Raises:
        ValueError: When `other` is an unknown type (known types are: None|AbsoluteDate|DateInterval)

    Returns:
        bool: When `other` is strictly before the interval.
    """
    if other is None:
        return False
    raise ValueError(f"Unknown interval class type: {type(other)}")


@_strictly_before.register
def _strictly_before_date(
    date: AbsoluteDate, start: AbsoluteDate, stop: AbsoluteDate
) -> bool:
    return stop.compareTo(date) < 0


@_strictly_before.register
def _strictly_before_ivl(
    ivl: DateInterval, start: AbsoluteDate, stop: AbsoluteDate
) -> bool:
    return stop.compareTo(ivl.start) < 0


@singledispatch
def _strictly_after(other, start: AbsoluteDate, stop: AbsoluteDate) -> bool:
    """Determine whether the other object is strictly after the interval defined by the start, stop interval.

    Args:
        other (None|AbsoluteDate|DateInterval): The object to check.
        start (AbsoluteDate): Start of the interval to check against.
        stop (AbsoluteDate): Stop of the interval to check against.

    Raises:
        ValueError: When `other` is an unknown type (known types are: None|AbsoluteDate|DateInterval)

    Returns:
        bool: When `other` is strictly after the interval.
    """
    if other is None:
        return False
    raise ValueError(f"Unknown interval class type: {type(other)}")


@_strictly_after.register
def _strictly_after_date(
    date: AbsoluteDate, start: AbsoluteDate, stop: AbsoluteDate
) -> bool:
    return start.compareTo(date) > 0


@_strictly_after.register
def _strictly_after_ivl(
    ivl: DateInterval, start: AbsoluteDate, stop: AbsoluteDate
) -> bool:
    return start.compreTo(ivl.stop) > 0


class DateIntervalList:
    """A list of non-overlapping DateInterval instances.
    This list is sorted in ascending interval order.
    """

    def __init__(
        self,
        interval: DateInterval = None,
        intervals: Iterable[DateInterval] = None,
        _dates: tuple[AbsoluteDate] = None,
        reduce_input=True,
    ):
        """_summary_

        Args:
            interval (DateInterval, optional): Create an interval list from a single interval. Defaults to None.
            intervals (tuple[DateInterval], optional): Create a list from a set of intervals. Defaults to None.
            reduce_input (bool, optional): When true, reduce the input list. Only set to False when the input list is explicitly built non-overlapping. Generally always True. Defaults to True.
        """
        if _dates:
            self.__dates = _dates
        elif interval:
            self.__dates = (interval.start, interval.stop)
        elif intervals:
            if reduce_input:
                self.__dates = DateIntervalList._reduce(intervals)
            else:
                self.__dates = DateIntervalList._flatten(intervals)
        else:
            self.__dates: tuple[AbsoluteDate] = ()

    @cached_property
    def span(self) -> DateInterval:
        """The interval from the earliest start to the latest stop of all intervals in the list.

        Returns:
            DateInterval: The span interval
        """
        return DateInterval(self.__dates[0], self.__dates[-1])

    def to_date_list(self) -> tuple[AbsoluteDate]:
        """Convert this list into a flattened date tuple.

        Returns:
            tuple[AbsoluteDate]: The flattened start/stop dates
        """
        return self.__dates

    def contains(
        self, other, startInclusive: bool = True, stopInclusive: bool = False
    ) -> bool:
        """Determine if this interval contains the provided time or interval.

        Args:
            other (AbsoluteDate|DateInterval): The date or interval to check for containment
            startInclusive (bool, optional): Whether the start of this interval is closed. Defaults to True.
            stopInclusive (bool, optional): Whether stop of this interval is closed. Defaults to False.

        Raises:
            TypeError: _description_

        Returns:
            bool: _description_
        """
        for (start, stop) in self.__dates[::2]:
            if _contained_in(
                other,
                start,
                stop,
                startInclusive=startInclusive,
                stopInclusive=stopInclusive,
            ):
                return True
            elif _strictly_after(other, start, stop):
                return False
        return False

    def __iter__(self) -> Iterator[DateInterval]:
        tmp = [iter(self.__dates)] * 2
        for (start, stop) in zip(*tmp, strict=True):
            yield DateInterval(start, stop)

    def __getitem__(self, idx: int) -> DateInterval:
        return DateInterval(self.__dates[idx * 2], self.__dates[idx * 2 + 1])

    def __len__(self) -> int:
        return int(self.__dates.__len__() / 2)

    def __sizeof__(self) -> int:
        return int(self.__dates.__sizeof__() / 2)

    @staticmethod
    def _reduce(intervals: Iterable[DateInterval]) -> tuple[AbsoluteDate]:
        combined = list(intervals)
        combined.sort()

        i: int = 1
        while i < len(combined):
            j: int = i - 1

            if combined[i].overlaps(
                combined[j], startInclusive=True, stopInclusive=True
            ):
                combined[j] = combined[j].union(combined[i])
                combined.pop(i)
            else:
                i = i + 1

        dates = []
        for i in combined:
            dates.extend((i.start, i.stop))

        return tuple(dates)

    @staticmethod
    def _flatten(intervals: Iterable[DateInterval]) -> tuple[AbsoluteDate]:
        dates = []
        for i in intervals:
            dates.extend((i.start, i.stop))
        return dates


class SafeListBuilder:
    """Build an interval given a known containing interval.

    This class enables building a DateIntervalList incrementally.
    """

    def __init__(self, start: AbsoluteDate = None, stop: AbsoluteDate = None):
        """Class constructor.

        Args:
            start (AbsoluteDate, optional): The earliest start time. Defaults to None.
            stop (AbsoluteDate, optional): The latest stop time. Defaults to None.
        """
        self.__start = start
        self.__stop = stop
        self.__dates = []

    def add_start(self, date: AbsoluteDate):
        if len(self.__dates) % 2 != 0:
            raise ValueError("Cannot add a second start to the builder.")

        self.__dates.append(date)

    def add_stop(self, date: AbsoluteDate):
        if not self.__dates:
            self.__dates.append(self.__start)
        if len(self.__dates) % 2 == 0:
            raise ValueError("Cannot add a second stop to the builder.")

        self.__dates.append(date)

    def build_list(self) -> DateIntervalList:
        intervals = []
        if len(self.__dates) % 2:
            self.__dates.append(self.__stop)

        for start, stop in zip(*[iter(self.__dates)] * 2):
            intervals.append(DateInterval(start, stop))

        return DateIntervalList(inervals=intervals, reduce_input=True)


def _verifylist(list1) -> DateIntervalList:
    if list1 is None:
        raise ValueError("List cannot be None")

    if isinstance(list1, DateIntervalList):
        return list1
    else:
        return DateIntervalList(intervals=list1)


class IntervalListOperations:
    """This class contains a collection of set operations to be performed on DateIntervalList instances."""

    @staticmethod
    def union(list1: DateIntervalList, list2: DateIntervalList) -> DateIntervalList:
        """Compute the union of the two lists. Overlapping intervals will be combined.

        Args:
            list1 (DateIntervalList): The first list.
            list2 (DateIntervalList): The second list.

        Returns:
            DateIntervalList: The list containing the union of the two lists.
        """
        if list1 is None or list2 is None:
            raise ValueError("Cannot union a list which is None")

        combined = list(list1)
        combined.extend(list2)

        return DateIntervalList(intervals=combined, reduce_input=True)

    @staticmethod
    def intersection(
        list1: DateIntervalList, list2: DateIntervalList
    ) -> DateIntervalList:
        """Compute the intersection of the provided interval lists.
        The intersection computes the periods which are contained in one interval of each list.

        Args:
            list1 (DateIntervalList): The first list.
            list2 (DateIntervalList): The second list.

        Returns:
            DateIntervalList: The list containing intervals contained within both lists.
        """
        list1 = _verifylist(list1)
        list2 = _verifylist(list2)

        i: int = 0
        j: int = 0
        results: list[DateInterval] = []
        while i < len(list1) and j < len(list2):
            l1 = list1[i] if i < len(list1) else None
            l2 = list2[j] if j < len(list2) else None

            # if only l1 is specified
            if l1 and l2:
                intersect = l1.intersect(l2)
                if intersect:
                    results.append(intersect)
                if l1 < l2:
                    i = i + 1
                else:
                    j = j + 1
        return DateIntervalList(intervals=results, reduce_input=False)

    @staticmethod
    def subtract(list1: DateIntervalList, list2: DateIntervalList) -> DateIntervalList:
        """Subtract the `list2` intervals from the `list1` intervals.

        Args:
            list1 (DateIntervalList): The minutend (list from which intervals will be subtracted).
            list2 (DateIntervalList): The subtrahend (list which will be subtracted from the other quantity.)

        Returns:
            DateIntervalList: The resulting intervals, or None.
        """
        list1 = _verifylist(list1)
        list2 = _verifylist(list2)

        # compute the intersection
        holes = IntervalListOperations.intersection(list1, list2)

        return IntervalListOperations.intersection(
            list1, IntervalListOperations.compliment(holes, list1.span)
        )

    @staticmethod
    def compliment(l: DateIntervalList, span: DateInterval = None) -> DateIntervalList:
        l = _verifylist(l)
        if span is None:
            span = l.span

        dates = list(
            filter(
                lambda d: _contained_in(
                    d, span.start, span.stop, startInclusive=True, stopInclusive=True
                ),
                l.to_date_list(),
            )
        )

        dates.insert(0, span.start)
        dates.append(span.stop)

        if dates[0].equals(dates[1]):
            dates.pop(0)
            dates.pop(0)

        if dates and dates[-1].equals(dates[-2]):
            dates.pop()
            dates.pop()

        if len(dates) % 2 != 0:
            dates.pop()

        return DateIntervalList(_dates=dates)


if __name__ == "__main__":

    from orekit.pyhelpers import datetime_to_absolutedate, setup_orekit_curdir

    setup_orekit_curdir(".data/orekit-data-master.zip")

    from datetime import datetime as dt

    dt1 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:00:00"))
    dt2 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:05:00"))
    dt3 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:10:00"))
    dt4 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:15:00"))

    dt5 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:00:00"))
    dt6 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:05:00"))
    dt7 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:10:00"))
    dt8 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:15:00"))

    ivl1 = DateInterval(dt1, dt2)
    ivl2 = DateInterval(dt3, dt4)
    ivl3 = DateInterval(dt1, dt3)

    ivl4 = DateInterval(dt5, dt7)
    ivl5 = DateInterval(dt6, dt8)

    print(ivl1)
    print(ivl2)
    print(ivl1 < ivl2)
    print(ivl1.intersect(ivl2))
    print(ivl1.union(ivl2))
    print(ivl1.intersect(ivl3))

    print(ivl1.contains(ivl1.start))
    print(ivl1.contains(ivl1.stop))
    print(ivl1.contains(ivl1.start, startInclusive=False))
    print(ivl1.contains(ivl1.stop, stopInclusive=True))
    print(ivl1.contains(ivl2.stop))

    print(ivl1.overlaps(ivl2))
    print(ivl3.overlaps(ivl2))
    print(ivl2.overlaps(ivl3))

    print("set1")
    print(f"  {ivl1}")
    print(f"  {ivl4}")
    print("set2")
    print(f"  {ivl2}")
    print(f"  {ivl3}")
    print(f"  {ivl5}")

    print("Intersection")
    for i in IntervalListOperations.intersection((ivl1, ivl4), (ivl2, ivl3, ivl5)):
        print(f"  {i}")

    print("Union")
    for i in IntervalListOperations.union((ivl1, ivl4), (ivl2, ivl3, ivl5)):
        print(f"  {i}")

    print("Subtract")
    for i in IntervalListOperations.subtract((ivl2, ivl3, ivl5), (ivl1, ivl4)):
        print(f"  {i}")
