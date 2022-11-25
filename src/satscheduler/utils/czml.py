"""CZML utilities."""
import czml3
import czml3.base
import czml3.enums
import czml3.properties
import czml3.types

__all__ = ["Polygon"]


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
