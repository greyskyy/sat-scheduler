"""Generate czml packets from models."""
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import datetime as dt
import math
import orekitfactory.factory
import orekitfactory.time
import typing

from org.orekit.bodies import GeodeticPoint
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate
from org.orekit.frames import Transform
from java.util import List

from .core import Platform
from .sensor import SensorModel

from ..utils.czml import format_boolean

# Patch CZML types for various numbers
czml3.types.TYPE_MAPPING[int] = "number"
czml3.types.TYPE_MAPPING[float] = "number"


def platform_czml(
    platform: Platform, earth: ReferenceEllipsoid = None, step: float | int | dt.timedelta = None
) -> czml3.Packet:
    """Generate the platform czml.

    Args:
        platform (Platform): The platform.
        earth (ReferenceEllipsoid, optional): The reference earth ellipsoid. Defaults to None.
        step (float | int | dt.timedelta, optional): The spacing betweed data points. Defaults to None.

    Returns:
        czml3.Packet: The czml packet describing the satellite position.
    """
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


def sensor_czml(
    platform: Platform,
    sensor: SensorModel,
    attitude_mode: str = "mission",
    earth: ReferenceEllipsoid = None,
    step: float | int | dt.timedelta = None,
    show: bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval] = None,
    fill_show: bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval] = None,
) -> list[czml3.Packet]:
    """Compute a sensor footprint on the surface of an ellipsoid.

    Args:
        platform (Platform): The satellite platform object, describes the ephemeris.
        sensor (SensorModel): The sensor model to project.
        attitude_mode (str, optional): The attitude mode used. Defaults to "mission".
        earth (ReferenceEllipsoid, optional): The ellipsoid definition. Defaults to None.
        step (float | int | dt.timedelta, optional): Step duration to use during propagation. Defaults to None.
        show (bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval], optional):
        The value or intervals for when to show the projection outline. Defaults to None.
        fill_show (bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval],
        optional): The value or intervals for when to fill the projection polygon. Defaults to None.

    Returns:
        list[czml3.Packet]: List of czml packets used to display the sensor projection.
    """
    if step is None:
        step = dt.timedelta(seconds=300)
    elif isinstance(step, (float, int)):
        step = dt.timedelta(seconds=step).createFovInBodyFrame()

    defaults = platform.model.data.maybe_get

    if earth is None:
        earth = orekitfactory.factory.get_reference_ellipsoid(
            model="wgs84", frameName="itrf", iersConventions="2010", simpleEop=False
        )

    fov = sensor.createFovInBodyFrame()
    interval = orekitfactory.time.as_dateinterval(platform.ephemeris.getMinDate(), platform.ephemeris.getMaxDate())

    p0_coords = []
    p1_coords = []
    p2_coords = []
    p3_coords = []

    t = interval.start
    step_secs = step.total_seconds()
    while t.isBeforeOrEqualTo(interval.stop):
        state = platform.ephemeris.propagate(t)
        inertialToBody_tx = state.getFrame().getTransformTo(earth.getBodyFrame(), state.getDate())
        fovToBody_tx = Transform(state.getDate(), state.toTransform().getInverse(), inertialToBody_tx)

        footprint = fov.getFootprint(fovToBody_tx, earth, math.radians(10))
        locs = List.cast_(footprint.get(0))

        p0: GeodeticPoint = GeodeticPoint.cast_(locs.get(0))
        p1: GeodeticPoint = GeodeticPoint.cast_(locs.get(1))
        p2: GeodeticPoint = GeodeticPoint.cast_(locs.get(2))
        p3: GeodeticPoint = GeodeticPoint.cast_(locs.get(3))

        delta_secs = t.durationFrom(interval.start)
        p0_coords.extend((delta_secs, p0.getLongitude(), p0.getLatitude(), p0.getAltitude()))
        p1_coords.extend((delta_secs, p1.getLongitude(), p1.getLatitude(), p1.getAltitude()))
        p2_coords.extend((delta_secs, p2.getLongitude(), p2.getLatitude(), p2.getAltitude()))
        p3_coords.extend((delta_secs, p3.getLongitude(), p3.getLatitude(), p3.getAltitude()))

        t = t.shiftedBy(step_secs)

    show = format_boolean(show, span=interval)
    fill_show = format_boolean(fill_show, span=interval)

    color = czml3.properties.Color.from_str(defaults("color", "#0000FF"))
    if fill_show:
        polygon = czml3.properties.Polygon(
            show=fill_show,
            positions=czml3.properties.PositionList(
                references=[
                    czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-0#position"),
                    czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-1#position"),
                    czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-2#position"),
                    czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-3#position"),
                ]
            ),
            material=czml3.properties.Material(solidColor=czml3.properties.SolidColorMaterial(color=color)),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            zIndex=10,
        )
    else:
        polygon = None

    interval_czml = czml3.types.TimeInterval(start=interval.start_dt, end=interval.stop_dt)
    return [
        czml3.Packet(
            id=f"footprint/{platform.id}/{sensor.id}-0",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p0_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{platform.id}/{sensor.id}-1",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p1_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{platform.id}/{sensor.id}-2",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p2_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{platform.id}/{sensor.id}-3",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p3_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{platform.id}/{sensor.id}",
            name=f"{platform.id}/{sensor.id}",
            availability=interval_czml,
            polygon=polygon,
            polyline=czml3.properties.Polyline(
                positions=czml3.properties.PositionList(
                    references=[
                        czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-0#position"),
                        czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-1#position"),
                        czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-2#position"),
                        czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-3#position"),
                        czml3.types.ReferenceValue(string=f"footprint/{platform.id}/{sensor.id}-0#position"),
                    ]
                ),
                material=czml3.properties.Material(
                    polylineOutline=czml3.properties.PolylineOutlineMaterial(outlineColor=color, outlineWidth=3),
                ),
                arcType=czml3.enums.ArcTypes.GEODESIC,
                clampToGround=True,
                zIndex=10,
                show=show,
            ),
        ),
    ]
