"""Core common utilities."""
import dataclasses
import datetime as dt
import typing

import orekit.pyhelpers
import orekitfactory.factory
import orekitfactory.time

from org.orekit.time import AbsoluteDate


class IterableDataclass:
    """Base class to create an interable dataclass.

    Must be applied to a class annotated with dataclasses.dataclass.
    """

    def __iter__(self):
        """Provide an iterable for this class."""
        return iter(dataclasses.astuple(self))


class DictableDataclass:
    """Base class to add a converstion to a dictionary from a dataclass."""

    def asdict(self) -> dict:
        """Convert this dataclass to a dictionary.

        Returns:
            dict: A `dict` instance representing this dataclass.
        """
        return dataclasses.asdict(self)


class DefaultFactoryDict(dict):
    """A `dict` instance with a default provided by the provided factory method."""

    def __init__(self, factory: typing.Callable[[typing.Any], typing.Any]):
        """Class constructor.

        Args:
            factory (typing.Callable([Any],Any)): The callable consuming a key and producing a default value.
        """
        self._factory = factory

    def __missing__(self, key):
        """Call the factory to generate a value for the missing key.

        Args:
            key (typing.Any): The dictionary key.

        Returns:
            typing.Any: The new value for the provide key.
        """
        self[key] = self._factory(key)
        return self[key]


def to_datetime(value: AbsoluteDate | dt.datetime | str) -> dt.datetime:
    """Convert the argument to an aware datetime.

    Args:
        value (AbsoluteDate | dt.datetime | str): The value to convert.

    Returns:
        dt.datetime: The value, as an aware datetime.
    """
    if value is None:
        return value
    elif isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    else:
        return orekit.pyhelpers.absolutedate_to_datetime(orekitfactory.factory.to_absolute_date(value)).replace(
            tzinfo=dt.timezone.utc
        )


class DateIndexed:
    """Mapping class providing collection objects indexed by datetime instances.

    The provided dates indicate transitions between intervals. Once created, indexing by a time will return the
    object corresponding to the interval in which the time is contained.
    """

    def __init__(
        self, dates: typing.Sequence[AbsoluteDate | dt.datetime | str], value_type: typing.Type, default_item=None
    ):
        """Class constructor.

        Args:
            dates (typing.Sequence[AbsoluteDate  |  dt.datetime  |  str]): Transition dates between intervals.
            value_type (typing.Type): A no-argument function that produces collections for each interval. Standard types
            are `list` and `dict`.
            default_item (Any, optional): The default type to provide when a secondary key is not found. Defaults
            to None.
        """
        self.__default_item = default_item
        data = {dt.datetime.fromtimestamp(0.0, dt.timezone.utc): value_type()}

        for d in dates:
            data[to_datetime(d)] = value_type()

        self.__data = sorted(data.items())

    def dates(self) -> typing.Iterable[dt.datetime]:
        """Iterator over the dates in this map.

        Returns:
            typing.Iterable[dt.datetime]: An iterator over all the index keys in this map.
        """
        for d in self.__data:
            yield d[0]

    def iter_key(self, key) -> typing.Iterator[tuple[dt.datetime, typing.Any]]:
        """Iterate over the value from all dates.

        Args:
            key (Any): The secondary key to retrieve the value for each date.

        Returns:
            typing.Iterator[tuple[dt.datetime, typing.Any]]: An iterator of 2-dimensional tuples containing the
            datetime starting the interval and the value at the requested key.
        """
        for item in self.__data:
            try:
                yield item[0], item[1][key]
            except (KeyError, IndexError):
                if self.__default_item is not None:
                    yield self.__default_item

    def _find(self, d: dt.datetime):
        for item in reversed(self.__data):
            if item[0] <= d:
                return item

        raise IndexError(f"Invalid index '{d}' in DateIndex collection.")

    def __getitem__(self, key):
        """Retrieve the item at the provided key.

        Args:
            key (Any|tuple[datetime,Any]|list[datetime,Any]): The key. When a 2-dimensional list or tuple is provided
            the first element is the datetime and the second is the secondary key.

        Returns:
            Any: The value.
        """
        if isinstance(key, (tuple, list, typing.Sequence)):
            t = to_datetime(key[0])
            item = self._find(t)
            try:
                return item[1][key[1]]
            except (IndexError, KeyError):
                if self.__default_item is not None:
                    return self.__default_item
                else:
                    raise
        else:
            return self._find(to_datetime(key))[1]

    def __setitem__(self, key, value):
        """Assign a value to the (date,key) tuple key.

        Args:
            key (tuple(dt.datetime, Any)): The key tuple. The first value is the datetime instance, the second is
            the index or key where the vaule will be assigned.
            value (Any): The value to assign.

        Raises:
            ValueError: when the key is not a tuple or list.
        """
        if isinstance(key, (tuple, list)):
            t = to_datetime(key[0])
            item = self._find(t)
            item[1][key[1]] = value
        else:
            raise ValueError("Cannot assign date slice. Keys must be 2-dimensional when setting a value.")

    def __len__(self) -> int:
        """The number of dates in the collection."""
        return len(self.__data)
