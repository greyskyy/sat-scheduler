"""Methods for generating CZML for aois."""
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import math
import orekitfactory.time
import typing

from org.hipparchus.geometry.spherical.twod import Vertex

from ..configuration import AoiConfiguration
from ..utils.czml import format_boolean

from .aoi import Aoi


def _positions(aoi: Aoi) -> czml3.properties.PositionList:
    coords = []
    for c in aoi.polygon.boundary.coords:
        if math.isfinite(c[0]) and math.isfinite(c[1]):
            coords.extend(c)
            coords.append(10)  # 10m elevation

    return czml3.properties.PositionList(cartographicDegrees=coords)


def _zone_positions(aoi: Aoi) -> czml3.properties.PositionList:
    zone = aoi.createZone()
    initialVert: Vertex = zone.getBoundaryLoops().get(0)
    nextVert: Vertex = initialVert.getOutgoing().getEnd()

    s2_points = [initialVert.getLocation()]

    while initialVert.getLocation().distance(nextVert.getLocation()) > 1e-10:
        s2_points.append(nextVert.getLocation())
        nextVert = nextVert.getOutgoing().getEnd()

    coords = []
    for p in s2_points:
        lat = 0.5 * math.pi - p.getPhi()
        lon = p.getTheta()

        coords.extend([lon, lat, 100])

    return czml3.properties.PositionList(cartographicRadians=coords)


def aoi_czml(
    aoi: Aoi,
    config: AoiConfiguration,
    zones: bool = False,
    show: bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval] = None,
    fill_show: bool | orekitfactory.time.DateIntervalList | typing.Sequence[orekitfactory.time.DateInterval] = None,
) -> czml3.Packet:
    """Generate a czml packet for the provided aoi.

    Args:
        aoi (Aoi): The aoi
        zones (bool, optional): Flag indicating whether to use the aoi boundary (False) or the schedulable zone
        (True). Defaults to False.
        config (dict, optional): Configuration dictionary. Defaults to {}.

    Returns:
        czml3.Packet: The CZML packet
    """
    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.CENTER,
        show=config.maybe_get("labels", True),
        font=config.maybe_get("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL_AND_OUTLINE,
        outlineWidth=2,
        text=f"{aoi.country} ({aoi.id})",
        verticalOrigin=czml3.enums.VerticalOrigins.BASELINE,
        fillColor=czml3.properties.Color.from_str(config.maybe_get("color", "#FF0000")),
    )

    if zones:
        positions = _zone_positions(aoi)
    else:
        positions = _positions(aoi)

    if aoi.polygon.centroid.bounds:
        position = czml3.properties.Position(
            cartographicDegrees=[
                aoi.polygon.centroid.coords[0][0],
                aoi.polygon.centroid.coords[0][1],
                1000,
            ]
        )
    else:
        position = None

    show = format_boolean(show)
    fill_show = format_boolean(fill_show)

    if fill_show:
        polygon = czml3.properties.Polygon(
            positions=positions,
            material=czml3.properties.Material(solidColor=czml3.properties.SolidColorMaterial(color=label.fillColor)),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            show=fill_show,
            zIndex=10,
        )
    else:
        polygon = None

    return czml3.Packet(
        id=f"aoi/{aoi.id}",
        name=aoi.id,
        label=label,
        polygon=polygon,
        polyline=czml3.properties.Polyline(
            positions=positions,
            material=czml3.properties.Material(
                polylineOutline=czml3.properties.PolylineOutlineMaterial(
                    color=label.fillColor, outlineColor=label.fillColor, outlineWidth=3
                ),
            ),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            clampToGround=True,
            zIndex=10,
            show=show,
        ),
        position=position,
    )
