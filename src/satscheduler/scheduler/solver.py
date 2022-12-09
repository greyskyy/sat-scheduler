"""Utilities for working with solvers."""
import dataclasses
import datetime as dt
import itertools
import logging
import orekitfactory.time
import ortools.linear_solver.pywraplp as pywraplp
import typing

from ..configuration import OptimizerConfiguration
from ..preprocessor import PreprocessedAoi


_EPOCH = dt.datetime(1970, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
"""Unix time epoch."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class SolverInterval:
    """Interval of time, represented as solver variables."""

    start: pywraplp.Solver.NumVar
    """The interval start, as a solver variable."""
    stop: pywraplp.Solver.NumVar
    """The interval stop, as a solver variable."""
    original: orekitfactory.time.DateInterval
    """The original interval."""

    def get_solution(self) -> tuple[bool, orekitfactory.time.DateInterval]:
        """Get the solution as a `DateInterval`.

        Returns:
            tuple[bool, orekitfactory.time.DateInterval]: The result as a tuple. The bool represents success. When
            `True`, the second value holds the solved interval.
        """
        t0 = _EPOCH + dt.timedelta(seconds=self.start.solution_value())
        t1 = _EPOCH + dt.timedelta(seconds=self.stop.solution_value())

        if t0 == t1:
            return False, None
        else:
            return True, orekitfactory.time.DateInterval(t0, t1)

    @staticmethod
    def create(solver: pywraplp.Solver, ivl: orekitfactory.time.DateInterval, id: str = ""):
        """Create the interval from the solver in initial interval.

        Args:
            solver (pywraplp.Solver): The solver.
            ivl (orekitfactory.time.DateInterval): The original interval.
            id (str, optional): The interval id. Defaults to "".

        Returns:
            SolverInterval: The resulting interval.
        """
        t0 = (_offset_aware(ivl.start_dt) - _EPOCH).total_seconds()
        t1 = (_offset_aware(ivl.stop_dt) - _EPOCH).total_seconds()

        var0 = solver.NumVar(t0, t1, f"{id or 'interval'}-start")
        var1 = solver.NumVar(t0, t1, f"{id or 'interval'}-stop")

        solver.Add(var0 <= var1)

        return SolverInterval(start=var0, stop=var1, original=ivl)


@dataclasses.dataclass
class SolverAoi:
    """An AOI added to the solver."""

    paoi: PreprocessedAoi
    """The original, preprocessed aoi."""
    intervals: list[SolverInterval]
    """The list of intervals, as they were added to the solver."""


def add_non_overlapping_constraints(solver: pywraplp.Solver, aois: typing.Sequence[SolverAoi]):
    """Add non-overlapping constraints between the provided aois.

    Args:
        solver (pywraplp.Solver): The solver.
        aois (typing.Sequence[SolverAoi]): The aois to add non-overlapping sequences.
    """
    for i, j in itertools.pairwise(range(0, len(aois))):
        aoi_i = aois[i]
        for k in range(j, len(aois)):
            constrain_non_overlapping(solver, aoi_i, aois[k])


def constrain_non_overlapping(solver: pywraplp.Solver, aoi1: SolverAoi, aoi2: SolverAoi):
    """Constraint 2 aois to be non-overlapping.

    Args:
        solver (pywraplp.Solver): The solver.
        aoi1 (SolverAoi): The first aoi which must not overlap the second.
        aoi2 (SolverAoi): The second aoi which must not overlap the first.
    """
    intersection = orekitfactory.time.list_intersection(aoi1.paoi.intervals, aoi2.paoi.intervals)

    if len(intersection):
        for inter in intersection:
            ivls1 = [
                ivl for ivl in aoi1.intervals if ivl.original.overlaps(inter, startInclusive=True, stopInclusive=True)
            ]
            ivls2 = [
                ivl for ivl in aoi2.intervals if ivl.original.overlaps(inter, startInclusive=True, stopInclusive=True)
            ]

            for i1 in ivls1:
                for i2 in ivls2:
                    # ensure the intervals don't overlap only if both intervals are non-zero (scheduled)
                    solver.Add(
                        i1.start == i1.stop or i2.start == i2.stop or i1.start >= i2.stop or i2.start >= i1.stop
                    )


def _offset_aware(d: dt.datetime) -> dt.datetime:
    """Ensure the datetime is offset-aware.

    Args:
        d (dt.datetime): The datetime object.

    Returns:
        dt.datetime: The offset-aware datetime object.
    """
    if d.tzinfo:
        return d
    else:
        return d.replace(tzinfo=dt.timezone.utc)


def create_solver(config: OptimizerConfiguration = None) -> pywraplp.Solver:
    """Create the solver from the configuration.

    Args:
        config (OptimizerConfiguration, optional): The optimizer configuration. Defaults to None.

    Returns:
        pywraplp.Solver: The solver instance.
    """
    if config is None:
        config = OptimizerConfiguration()

    return pywraplp.Solver.CreateSolver(config.solver)


def add_to_solver(
    solver: pywraplp.Solver, paoi: PreprocessedAoi, bounds: orekitfactory.time.DateInterval = None
) -> SolverAoi:
    """Add intervals to the solver.

    Args:
        solver (pywraplp.Solver): The solver when the intervals will be add.
        paoi (PreprocessedAoi): The aoi to add the intervals.
        bounds (orekitfactory.time.DateInterval, optional): Bounding interval, only intervals within the bounding
        interval will be added. Defaults to None.

    Returns:
        SolverAoi: A SolverAoi instance, holding solver paramerers for this pre-processed aoi.
    """
    intervals = orekitfactory.time.list_intersection(bounds, paoi.intervals) if bounds is not None else paoi.intervals

    return SolverAoi(
        paoi=paoi,
        intervals=[SolverInterval.create(solver, ivl, f"{paoi.aoi.id}-{i}") for i, ivl in enumerate(intervals)],
    )


def result_is_successful(result: int) -> bool:
    """Transform the solver result into a boolean.

    Args:
        result (int): The solver result.

    Returns:
        bool: `True` if the result indicated success, `False` otherwise.
    """
    if result == pywraplp.Solver.OPTIMAL:
        return True
    elif result == pywraplp.Solver.FEASIBLE:
        logging.getLogger(__name__).warning("Solver found multiple results, picking a feasible one.")
        return True
    else:
        return False


def result_to_string(result: int) -> str:
    """Convert a result into a string.

    Args:
        result (int): The solver result.

    Returns:
        str: The string representation of that result.
    """
    if result == pywraplp.Solver.OPTIMAL:
        return "OPTIMAL"
    elif result == pywraplp.Solver.FEASIBLE:
        return "FEASIBLE"
    elif result == pywraplp.Solver.ABNORMAL:
        return "ABNORMAL"
    elif result == pywraplp.Solver.INFEASIBLE:
        return "INFEASIBLE"
    elif result == pywraplp.Solver.UNBOUNDED:
        return "UNBOUNDED"
    elif result == pywraplp.Solver.MODEL_INVALID:
        return "MODEL_INVALID"
    elif result == pywraplp.Solver.NOT_SOLVED:
        return "NOT_SOLVED"
    else:
        return "UNKNOWN_RESULT"


def generate_solver_report(solver: pywraplp.Solver, output_path: str = "solver_report.csv"):
    """Generate the solver report.

    Args:
        solver (pywraplp.Solver): The solver.
        output_path (str, optional): The output path. Defaults to "solver_report.csv".
    """
    pass
