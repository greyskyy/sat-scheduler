"""Utility to build a satellite's nadir trace."""
from .linebuilder import LineBuilder

from org.hipparchus.util import FastMath

from org.orekit.bodies import GeodeticPoint
from org.orekit.frames import Frame
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import SpacecraftState
from org.orekit.time import AbsoluteDate
from org.orekit.utils import PVCoordinates


class NadirTrace:
    """Utility class to build a nadir trace line from a satellite."""

    def __init__(self, earth: ReferenceEllipsoid, lineBuilder: LineBuilder = None):
        """Class constructor

        Args:
            earth (ReferenceEllipsoid): Earth representation.
            lineBuilder (LineBuilder, optional): The line builder. Defaults to None.
        """
        self.__earth = earth
        self.__line = lineBuilder if lineBuilder is not None else LineBuilder()

    def addState(self, state: SpacecraftState):
        """Add a new spacecraft state to the line.

        Args:
            state (SpacecraftState): The spacecraft state to add to the line.

        Returns:
            NadirTrace: This object instance, for method chaining.
        """
        pv = state.getPVCoordinates(self.__earth.getBodyFrame())

        return self.addPv(pv, self.__earth.getBodyFrame(), state.getDate())

    def addPv(self, pv: PVCoordinates, frame: Frame, date: AbsoluteDate):
        """Add a spacecraft position to the nadir line.

        Args:
            pv (PVCoordinates): The spacecraft position/velocity.
            frame (Frame): The frame in which `pv` is defined.
            date (AbsoluteDate): The date at which `pv` is defined.

        Returns:
            NadirTrace: This object instance, for method chaining
        """
        # project to ground
        nadir = self.__earth.projectToGround(
            pv.getPosition(), date, self.__earth.getFrame()
        )
        point = self.__earth.transform(nadir, self.__earth.getFrame(), date)

        # add current points to the list
        (lat, lon) = self._asTuple(point)
        self.__line.addPoint(lat, lon)

        return self

    def addStateAndNewline(self, state: SpacecraftState):
        """Add a state and start a new line.

        Args:
            state (SpacecraftState): The state to add.

        Returns:
            NadirTrace: This instance, for method chaining
        """
        pv = state.getPVCoordinates(self.__earth.getBodyFrame())

        return self.addPvAndNewline(pv, self.__earth.getBodyFrame(), state.getDate())

    def addPvAndNewline(self, pv: PVCoordinates, frame: Frame, date: AbsoluteDate):
        """Add a point and start a new line.

        Args:
            pv (PVCoordinates): The satellite position/velocity
            frame (Frame): The frame in which the position/velocity is defined
            date (AbsoluteDate): The date at the the position/velocity is defined
        """
        # project to ground
        nadir = self.__earth.projectToGround(
            pv.getPosition(), date, self.__earth.getFrame()
        )
        point = self.__earth.transform(nadir, self.__earth.getFrame(), date)

        (lat, lon) = self._asTuple(point)
        self.__line.addPointAndSplit(lat, lon)

    def _asTuple(self, point: GeodeticPoint) -> tuple[float, float]:
        """Convert a point to a tuple of [latitude, longitude] in degrees.

        Args:
            point (GeodeticPoint): The point to convert

        Returns:
            tuple[float,float]: A tuple of latitude, longitude, in degrees
        """
        return tuple(
            [
                FastMath.toDegrees(point.getLatitude()),
                FastMath.toDegrees(point.getLongitude()),
            ]
        )
