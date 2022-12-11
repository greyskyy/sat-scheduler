"""Generate czml packets from models."""
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import datetime as dt
import orekitfactory.factory
import orekitfactory.time

from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate

from .core import Platform


def platform_czml(
    platform: Platform, earth: ReferenceEllipsoid = None, step: float | int | dt.timedelta = None
) -> czml3.Packet:
    data = platform.model.data

    interval = orekitfactory.time.as_dateinterval(platform.ephemeris.getMinDate(), platform.ephemeris.getMaxDate())

    if step is None:
        step = dt.timedelta(seconds=300)
    elif isinstance(step, (float, int)):
        step = dt.timedelta(seconds=step)

    if earth is None:
        earth = orekitfactory.factory.get_reference_ellipsoid(
            model="wgs84", frameName="itrf", iersConventions="2010", simpleEop=False
        )

    # function to generate the cartesian position array
    def generate_carts():
        t: AbsoluteDate = interval.start
        step_secs: float = 300.0
        while t.isBeforeOrEqualTo(interval.stop):
            pv = platform.ephemeris.getPVCoordinates(t, earth.getBodyFrame())
            yield t.durationFrom(interval.start)
            yield pv.getPosition().getX()
            yield pv.getPosition().getY()
            yield pv.getPosition().getZ()

            t = t.shiftedBy(step_secs)

    show = czml3.types.Sequence(
        [czml3.types.IntervalValue(start=interval.start_dt, end=interval.stop_dt, value=True)]
    )

    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.LEFT,
        outlineWidth=data.maybe_get("outlineWidth", 2),
        show=show,
        font=data.maybe_get("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL_AND_OUTLINE,
        text=data.name,
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
        fillColor=czml3.properties.Color.from_str(data.maybe_get("fillColor", data.maybe_get("color", "#00FF00"))),
        outlineColor=czml3.properties.Color.from_str(
            data.maybe_get("outlineColor", data.maybe_get("color", "#000000"))
        ),
    )

    bb = czml3.properties.Billboard(
        horizontalOrigin=czml3.enums.HorizontalOrigins.CENTER,
        image=(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9"
            "hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdv"
            "qGQAAADJSURBVDhPnZHRDcMgEEMZjVEYpaNklIzSEfLfD4qNnXAJSFWfhO7w2Zc0T"
            "f9QG2rXrEzSUeZLOGm47WoH95x3Hl3jEgilvDgsOQUTqsNl68ezEwn1vae6lceSEE"
            "YvvWNT/Rxc4CXQNGadho1NXoJ+9iaqc2xi2xbt23PJCDIB6TQjOC6Bho/sDy3fBQT"
            "8PrVhibU7yBFcEPaRxOoeTwbwByCOYf9VGp1BYI1BA+EeHhmfzKbBoJEQwn1yzUZt"
            "yspIQUha85MpkNIXB7GizqDEECsAAAAASUVORK5CYII="
        ),
        scale=data.maybe_get("scale", 1.5),
        show=show,
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
    )

    path = czml3.properties.Path(
        show=show,
        width=1,
        resolution=120,
        material=czml3.properties.Material(solidColor=czml3.properties.SolidColorMaterial(color=label.fillColor)),
    )

    pos = czml3.properties.Position(
        interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.HERMITE,
        interpolationDegree=3,
        referenceFrame=czml3.enums.ReferenceFrames.FIXED,
        epoch=interval.start_dt,
        cartesian=list(generate_carts()),
    )

    return czml3.Packet(
        id=platform.id,
        name=platform.model.name,
        availability=czml3.types.TimeInterval(start=interval.start_dt, end=interval.stop_dt),
        billboard=bb,
        label=label,
        path=path,
        position=pos,
    )
