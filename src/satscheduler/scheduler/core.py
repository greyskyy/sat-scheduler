"""Core scheduler data classes."""
import dataclasses
import enum
import typing

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
