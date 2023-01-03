"""Event detectors and handlers."""
import orekitfactory.time

from org.hipparchus.geometry.euclidean.threed import Line, Vector3D
from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath

from org.orekit.bodies import OneAxisEllipsoid
from org.orekit.frames import TopocentricFrame, Transform, StaticTransform
from org.orekit.propagation import SpacecraftState
from org.orekit.propagation.events import EventDetector, PythonAbstractDetector, PythonEnablingPredicate
from org.orekit.propagation.events.handlers import EventHandler, PythonEventHandler, ContinueOnEvent
from org.orekit.utils import PVCoordinatesProvider


class BoresightSunElevationDetector(PythonAbstractDetector):
    """Event detector for determining sun elevation at the payload boresight."""

    def __init__(
        self,
        boresight_in_sat: Vector3D,
        body: OneAxisEllipsoid,
        sun: PVCoordinatesProvider,
        min_elevation: float,
        max_check: float = 600.0,
        threshold: float = 1.0e-6,
        max_iter: int = 100,
        handler: EventDetector = None,
    ):
        """Class constructor.

        Args:
            boresight_in_sat (Vector3D): Boresight vector, defined in the satellite's frame.
            body (OneAxisEllipsoid): The central body onto which the boresight vector will be projected.
            sun (PVCoordinatesProvider): The sun position.
            min_elevation (float): The minimum sun elevation value, in radians.
            max_check (float, optional): Maximal time interval (s) between switching function checks. Defaults to 600.
            threshold (float, optional): Maximal time interval (s) between switching function checks.
            Defaults to 1.0e-6.
            max_iter (int, optional): maximal number of iterations in the event time search. Defaults to 100.
            handler (EventDetector, optional): Default event handler to trigger when events are encountered. If
            unspecified the events will be ignored. Defaults to None.
        """
        super().__init__(max_check, threshold, max_iter, handler or ContinueOnEvent())
        self.__boresight_in_sat = boresight_in_sat.normalize()
        self.__body = body
        self.__sun = sun
        self.__min_elevation = min_elevation

    def g(self, s: SpacecraftState) -> float:
        """Compute the value of the switching function.

        This function must be continuous (at least in its roots neighborhood),
        as the integrator will need to find its roots to locate the events.

        Args:
            s (SpacecraftState): The current state information: date, kinematics, attitude.

        Returns:
            float: Value of the switching function.
        """
        frame = self.__body.getBodyFrame()
        inertialToBody_tx = s.getFrame().getTransformTo(frame, s.getDate())
        sat_to_body_tx = Transform(s.getDate(), s.toTransform().getInverse(), inertialToBody_tx)
        boresight = StaticTransform.cast_(sat_to_body_tx).transformVector(self.__boresight_in_sat)

        pv = s.getPVCoordinates(frame)
        pos = pv.getPosition()
        pos_boresight = pos.add(boresight)

        los = Line(pos, pos_boresight, 1.0e-3)
        point = self.__body.getIntersectionPoint(los, pos, frame, None)

        if point:
            # Intersection found
            topo = TopocentricFrame(self.__body, point, "boresight_frame")
            true_elevation = topo.getElevation(
                PVCoordinatesProvider.cast_(self.__sun).getPVCoordinates(s.getDate(), frame).getPosition(),
                frame,
                s.getDate(),
            )
            return true_elevation - self.__min_elevation
        else:
            # no intersection
            return -FastMath.PI

    def create(self, newMaxCheck: float, newThreshold: float, newMaxIter: int, newHandler: EventHandler):
        """Create a new instance.

        Args:
            newMaxCheck (float): New max check value.
            newThreshold (float): New threshold value.
            newMaxIter (int): New max-iter value.
            newHandler (EventHandler): New event handler.

        Returns:
            BoresightSunElevationDetector: A new boresight sun elevation detector instance.
        """
        return BoresightSunElevationDetector(
            body=self.__body,
            boresight_in_sat=self.__boresight_in_sat,
            sun=self.__sun,
            min_elevation=self.__min_elevation,
            max_check=newMaxCheck,
            threshold=newThreshold,
            max_iter=newMaxIter,
            handler=newHandler,
        )


class IntervalBuilderEventHandler(PythonEventHandler):
    """Event hander for orbital events."""

    def __init__(self):
        """Class constructor."""
        super().__init__()
        self.__starts = []
        self.__stops = []

    def get_results(self, run_interval: orekitfactory.time.DateInterval):
        """Retrive the event list results after propagation.

        Returns:
            list[OrbitEvent]: The event list.
        """
        if self.__starts and self.__stops:
            if self.__starts[0].isAfter(self.__stops[0]):
                self.__starts.insert(0, run_interval.start)
            if self.__starts[-1].isAfter(self.__stops[-1]):
                self.__stops.append(run_interval.stop)
            return orekitfactory.time.as_dateintervallist([(a, b) for a, b in zip(self.__starts, self.__stops)])
        elif self.__starts:
            return orekitfactory.time.as_dateintervallist([self.__starts[0], run_interval.stop])
        elif self.__stops:
            return orekitfactory.time.as_dateintervallist([run_interval.start, self.__stops[-1]])
        else:
            return orekitfactory.time.as_dateintervallist(run_interval)

    def init(self, initialstate, target, detector):
        """Initialize the handler.

        Args:
            initialstate (SpacecraftState): The spacecraft state.
            target (Any): The target.
            detector (Any): The detector.
        """
        pass

    def resetState(self, detector, oldState):
        """Reset the state.

        Args:
            detector (Any): The detector.
            oldState (Any): The old state.
        """
        return oldState

    def eventOccurred(self, s, detector, increasing):
        """Process an event.

        Args:
            s (SpacecraftState): The spacecraft state at time of event.
            detector (EventDetector): The detector triggering the event.
            increasing (bool): Whether the value is increasing or decreasing.

        Returns:
            Action: The continuation action.
        """
        if increasing:
            self.__starts.append(s.getDate())
        else:
            self.__stops.append(s.getDate())
        return Action.CONTINUE


class EnablingPredicateFilter(PythonEnablingPredicate):
    """Predicate using an event detector as the decision point."""

    def __init__(self, detector: EventDetector):
        """Class constructor.

        Args:
            detector (EventDetector): The base detector.
        """
        super().__init__()
        self.__base_detector = detector

    def eventIsEnabled(self, state: SpacecraftState, eventDetector: EventDetector, g: float) -> bool:
        """Compute an event enabling function of state.

        Args:
            state (SpacecraftState): Current state.
            eventDetector (EventDetector): Underlying detector.
            g (float): Value of the underlying detector for the current state.

        Returns:
            bool: True if the event is enabled (i.e. it can be triggered), False if it should be ignored.
        """
        result = self.__base_detector.g(SpacecraftState.cast_(state))
        return bool(result >= 0.0)
