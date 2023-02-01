"""CZML utilities."""
import czml3
import czml3.base
import czml3.common
import czml3.enums
import czml3.properties
import czml3.types
import datetime as dt
import orekitfactory.time
import os.path
import typing

from org.orekit.time import AbsoluteDate

__all__ = ["Polygon", "write_czml"]


@czml3.core.attr.s(str=False, frozen=True, kw_only=True)
class Polygon(czml3.base.BaseCZMLObject):
    """Extension of czml3.properties.Polygon that includes outline properties."""

    fill = czml3.core.attr.ib(default=None)
    outline = czml3.core.attr.ib(default=None)
    outlineColor = czml3.core.attr.ib(default=None)
    outlineWidth = czml3.core.attr.ib(default=None)
    positions = czml3.core.attr.ib()
    show = czml3.core.attr.ib(default=None)
    arcType = czml3.core.attr.ib(default=None)
    granularity = czml3.core.attr.ib(default=None)
    material = czml3.core.attr.ib(default=None)
    shadows = czml3.core.attr.ib(default=None)
    distanceDisplayCondition = czml3.core.attr.ib(default=None)
    classificationType = czml3.core.attr.ib(default=None)
    zIndex = czml3.core.attr.ib(default=None)


@czml3.core.attr.s(str=False, frozen=True, kw_only=True)
class Position(czml3.core.BaseCZMLObject, czml3.common.Interpolatable, czml3.common.Deletable):
    """Defines a position. The position can optionally vary over time."""

    referenceFrame = czml3.core.attr.ib(default=None)
    cartesian = czml3.core.attr.ib(default=None)
    cartographicRadians = czml3.core.attr.ib(default=None)
    cartographicDegrees = czml3.core.attr.ib(default=None)
    cartesianVelocity = czml3.core.attr.ib(default=None)
    reference = czml3.core.attr.ib(default=None)
    interval: int | None = czml3.core.attr.ib(default=None)
    
    def __attrs_post_init__(self):
        if all(
            val is None
            for val in (
                self.cartesian,
                self.cartographicDegrees,
                self.cartographicRadians,
                self.cartesianVelocity,
                self.reference,
            )
        ):
            raise ValueError(
                "One of cartesian, cartographicDegrees, cartographicRadians or reference must be given"
            )

def write_czml(fname: str, packets: czml3.Packet | typing.Sequence[czml3.Packet], name: str = None, clock=None):
    """Write the czml packets to a file.

    Args:
        fname (str): The file name.
        packets (czml3.Packet | typing.Sequence[czml3.Packet]): The packets to include in the document.
        name (str, optional): The name to provide to the czml document. If None, the file basename will be used.
        Defaults to None.
        clock (czml3.types.IntervalValue, optional): The document clock to use. Default to None.
    """
    if not fname.endswith(".czml"):
        fname = f"{fname}.czml"

    if not name:
        name = os.path.basename(fname)[0:-5]

    if isinstance(packets, czml3.Packet):
        packets = [packets]

    doc = czml3.Document(
        [
            czml3.Preamble(name=name, clock=clock),
            *packets,
        ]
    )
    with open(fname, "w") as f:
        doc.dump(f)


def format_boolean(
    value: bool
    | orekitfactory.time.DateIntervalList
    | orekitfactory.time.DateInterval
    | typing.Sequence[AbsoluteDate | dt.datetime | typing.Sequence[AbsoluteDate | dt.datetime]],
    span: None | orekitfactory.time.DateInterval = None,
    add_false: bool = False,
) -> bool | czml3.types.Sequence:
    """Format a boolean value.

    Args:
        value (bool | orekitfactory.time.DateIntervalList | orekitfactory.time.DateInterval |
        typing.Sequence[AbsoluteDate  |  dt.datetime  |  typing.Sequence[AbsoluteDate  |  dt.datetime]]): The value. If
        a boolean, that value will be returned. Otherwise, the value will be coerced into a DateIntervalList, and a
        `Sequence` will be provided set to true for each interval.
        span (None | orekitfactory.time.DateInterval, optional): The total timespan. If specified and the `value` is
        an interval list, intervals setting a value to `False` will be added to the resuling sequence.  Ignored if
        `value` is a `bool`. Defaults to None.
        add_false (bool, optional): When `True` and `value` is an interval list, add complimentary intervals to
        specify `False`. This value is ignored when `span` is set. Defaults to `False`.

    Returns:
        bool | czml3.types.Sequence: The value to be used.
    """
    if value is None:
        return True
    elif isinstance(value, bool):
        return value
    else:
        lst = orekitfactory.time.as_dateintervallist(value)

        if span:
            no_lst = orekitfactory.time.list_subtract(span, lst)
        elif add_false:
            no_lst = orekitfactory.time.list_compliment(lst)
        else:
            no_lst = []

        if len(lst) == 0:
            return False
        else:
            return czml3.types.Sequence(
                [
                    *[czml3.types.IntervalValue(start=ivl.start_dt, end=ivl.stop_dt, value=True) for ivl in lst],
                    *[czml3.types.IntervalValue(start=ivl.start_dt, end=ivl.stop_dt, value=False) for ivl in no_lst],
                ]
            )
