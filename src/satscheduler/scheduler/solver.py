"""Utilities for working with solvers."""
import dataclasses
import datetime as dt
import orekitfactory.time
import ortools.linear_solver.pywraplp as pywraplp
import typing

from ..configuration import OptimizerConfiguration, get_config
from ..preprocessor import PreprocessedAoi


_EPOCH = dt.datetime(1970, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
"""Unix time epoch."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class SolverInterval:
    start: pywraplp.Solver.NumVar
    stop: pywraplp.Solver.NumVar
    
    original: orekitfactory.time.DateInterval

    def get_solution(self) -> tuple[bool, orekitfactory.time.DateInterval]:
        t0 = _EPOCH + dt.timedelta(seconds=self.start.solution_value())
        t1 = _EPOCH + dt.timedelta(seconds=self.stop.solution_value())

        if t0 == t1:
            return False, None
        else:
            return True, orekitfactory.time.DateInterval(t0, t1)

    @staticmethod
    def create(solver: pywraplp.Solver, ivl: orekitfactory.time.DateInterval, id: str = ""):
        t0 = (_offset_aware(ivl.start_dt) - _EPOCH).total_seconds()
        t1 = (_offset_aware(ivl.stop_dt) - _EPOCH).total_seconds()

        var0 = solver.NumVar(t0, t1, f"{id or 'interval'}-start")
        var1 = solver.NumVar(t0, t1, f"{id or 'interval'}-stop")

        solver.Add(var0 <= var1)

        return SolverInterval(start=var0, stop=var1, original=ivl)


@dataclasses.dataclass
class SolverAoi:
    paoi: PreprocessedAoi
    intervals: list[SolverInterval]


def constrain_non_overlapping(solver: pywraplp.Solver, aoi1: SolverAoi, aoi2: SolverAoi):
    intersection = orekitfactory.time.list_intersection(aoi1.paoi.intervals, aoi2.paoi.intervals)
    
    if len(intersection):
        for inter in intersection:
            ivls1 = [ivl for ivl in aoi1.intervals if ivl.original.overlaps(inter, startInclusive=True, stopInclusive=True)]
            ivls2 = [ivl for ivl in aoi2.intervals if ivl.original.overlaps(inter, startInclusive=True, stopInclusive=True)]
            
            for i1 in ivls1:
                for i2 in ivls2:
                    #solver.Add(not (i1.start < i2.stop and i2.start < i1.stop))
                    solver.Add(i1.start >= i2.stop and i2.start >= i1.stop)


def _offset_aware(d: dt.datetime) -> dt.datetime:
    if d.tzinfo:
        return d
    else:
        return d.replace(tzinfo=dt.timezone.utc)


def create_solver(config: OptimizerConfiguration = None) -> pywraplp.Solver:
    """Create the solver from the configuration

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
        bounds (orekitfactory.time.DateInterval, optional): Bounding interval, only intervals within the bounding interval will be added. Defaults to None.

    Returns:
        SolverAoi: A SolverAoi instance, holding solver paramerers for this pre-processed aoi.
    """
    intervals = orekitfactory.time.list_intersection(bounds, paoi.intervals) if bounds is not None else paoi.intervals

    return SolverAoi(
        paoi=paoi,
        intervals=[SolverInterval.create(solver, ivl, f"{paoi.aoi.id}-{i}") for i, ivl in enumerate(intervals)],
    )


def result_to_string(result: int) -> str:
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
