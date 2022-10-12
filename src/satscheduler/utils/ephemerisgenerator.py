import datetime as dt

from org.orekit.propagation import Propagator, SpacecraftState
from org.orekit.propagation.analytical import Ephemeris
from org.orekit.time import AbsoluteDate
from org.orekit.attitudes import InertialProvider
from java.util import ArrayList

from orekitfactory.time import DateInterval

ZERO_TIMEDELTA = dt.timedelta()
"""Zero seconds, as a timedelta object."""


def _as_timedelta(td: float | dt.timedelta) -> dt.timedelta:
    """Convert the parameter to a timedelta object.

    Args:
        td (float | dt.timedelta): the input object, either a timedelta or seconds.

    Returns:
        dt.timedelta: the time delta object
    """
    if isinstance(td, dt.timedelta):
        return td
    else:
        return dt.timedelta(seconds=td)


class EphemerisGenerator:
    def __init__(self, propagator: Propagator):
        """Class construtor.

        Args:
            propagator (Propagator): The orbit propagator
        """
        self.__states = ArrayList()
        self.__propagator = propagator

    def propagate(
        self,
        interval: DateInterval,
        step: float | dt.timedelta = dt.timedelta(minutes=1),
    ):
        """Propagate ephemeris and create a cached ephemeris.

        Args:
            interval (DateInterval): The date interval over which to generate ephemeris.
            step (float | dt.timedelta, optional): The ephemeris timestep. Defaults to dt.timedelta(minutes=1).
        """
        step = _as_timedelta(step)

        steps, part = divmod(interval.duration, step)

        if part > ZERO_TIMEDELTA:
            steps = steps + 1
        if steps == 0:
            steps = 1

        adjusted_step = (interval.duration / steps).total_seconds()

        t = interval.start
        while interval.contains(t, startInclusive=True, stopInclusive=True):
            self.__states.add(self.__propagator.propagate(t))
            t = t.shiftedBy(adjusted_step)

    def build(self) -> Ephemeris:
        for i in range(self.__states.size() - 1, 0, -1):
            j = i - 1
            if SpacecraftState.cast_(self.__states.get(i)).getDate().equals(SpacecraftState.cast_(self.__states.get(j)).getDate()):
                self.__states.remove(i)
        
        result = Ephemeris(
            self.__states,
            int(2),
            float(0.001),
            InertialProvider.of(self.__propagator.getFrame()),
        )
        self.__states = ArrayList()
        return result

    @staticmethod
    def generate(
        propagator: Propagator,
        interval: DateInterval,
        step: float | dt.timedelta = dt.timedelta(minutes=1),
    ) -> Ephemeris:
        """Generate an Ephemeris from the provided propagator.

        The generated ephemeris is gauranteed to cover the interval.

        Args:
            propagator (Propagator): The source propagator.
            interval (DateInterval): The desired timespan over which to propagate.
            step (float|timedelta, optional): The step size to take during propagation. Specified as a float number of seconds or a timedelta instance. Defaults to 1 minute.

        Returns:
            Ephemeris: The generated ephemeris
        """
        generator = EphemerisGenerator(propagator=propagator)
        generator.propagate(interval, step)
        return generator.build()

        step = _as_timedelta(step)

        steps, part = divmod(interval.duration, step)

        if part > ZERO_TIMEDELTA:
            steps = steps + 1

        adjusted_step = (step / steps).total_seconds()

        states = ArrayList(steps)

        t = interval.start
        while interval.contains(t, startInclusive=True, stopInclusive=True):
            states.add(propagator.propagate(t))
            t = t.shiftedBy(adjusted_step)

        return Ephemeris(
            states, int(2), float(0.001), InertialProvider.of(propagator.getFrame())
        )
