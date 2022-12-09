"""Core common utilities."""
import dataclasses
import typing


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
