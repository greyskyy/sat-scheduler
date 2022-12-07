"""Pushbroom scheduler.

A pushbroom scheduler maintains a constant payload pointing without articulating 
during collection. It is the satellite motion which moves the payload across the
AOIs.
"""
import argparse
import logging
import itertools
import orekitfactory.time

from .core import Platform, Platforms
from .reporting import init_access_report, record_result, Result
from .schedule import Schedule, ScheduleActivity
from .score import score_aois, ScoredAoi
from .solver import create_solver, add_to_solver, result_to_string, SolverAoi, SolverInterval, constrain_non_overlapping
from ..configuration import get_config, Configuration
from ..preprocessor import create_uows, run_units_of_work, PreprocessingResult, PreprocessedAoi, aois_from_results

SUBCOMMAND = "pushbroom"
ALIASES = ["pb", "schedule", "sched"]
LOGGER_NAME = "satscheduler"


def config_args(parser):
    """Add command line arguments to the provided parser.

    Args:
        parser (argparse.ArgumentParser): The parser to which arguments will be added.
    """
    parser.add_argument(
        "--multi-threading",
        action=argparse.BooleanOptionalAction,
        dest="threading",
        help="Run with multi-threading. Overrides the value set in the config.",
    )
    parser.add_argument(
        "--test",
        help="Run in test-mode.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )


def execute(args=None) -> int:
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.

    Returns:
        int: The return code to provide back to the OS.
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    # Execute preprocessing
    logger.info("Starting preprocessor tool.")
    uows = create_uows(args, config=config)
    results: list[PreprocessingResult] = run_units_of_work(uows=uows, args=args, config=config)
    logger.info("Preprocessing complete.")

    # process results into scheduler data structures
    platforms = Platforms([Platform(model=r.sat, ephemeris=r.ephemeris) for r in results])
    report = init_access_report(aois_from_results(results))

    # sort the aois into priority order
    report["score"] = 0
    scored_aois: list[ScoredAoi] = []
    for value in score_aois(aois_from_results(results)):
        report.loc[
            report["aoi_id"] == value.aoi.aoi.id, "score"
        ] = value.score  #  x.aoi is known to be PreprocessedAoi

        if value.score > 0:
            scored_aois.append(value)

    scored_aois.sort(key=lambda x: (x.score, x.aoi.aoi.id))  #  x.aoi is known to be PreprocessedAoi
    report["order_index"] = -1

    for index, sa in enumerate(scored_aois):
        report.loc[report["aoi_id"] == sa.aoi.aoi.id, "order_index"] = index  #  x.aoi is known to be PreprocessedAoi

    solvers = {}

    solver_aois: list[SolverAoi] = []
    scores = []
    durations = []
    # now, for the scheduling
    for item in scored_aois:
        score: float = item.score
        paoi: PreprocessedAoi = item.aoi

        sat_model = paoi.sat
        sensor_model = paoi.sensor

        key = (sat_model.id, sensor_model.id)
        solver = solvers.get(key, None)

        if not solver:
            solver = create_solver(config.optimizer)
            solvers[key] = solver

        solver_aoi = add_to_solver(solver, paoi)
        solver_aois.append(solver_aoi)

        dur = solver.Sum(map(lambda ivl: ivl.stop - ivl.start, solver_aoi.intervals))
        scores.append(score * dur)
        durations.append(dur)
    
    for i,j in itertools.pairwise(range(0, len(solver_aois))):
        aoi_i = solver_aois[i]
        for k in range(j, len(solver_aois)):
            constrain_non_overlapping(solver, aoi_i, solver_aois[k])

    solver.Add(solver.Sum(durations) <= 0.25 * (config.run.stop - config.run.start).total_seconds())
    solver.Maximize(solver.Sum(scores))

    result = solver.Solve()

    print(result_to_string(result))
    
    for solver_aoi in solver_aois:
        print(solver_aoi.paoi.aoi.id + ":")
        for ivl in solver_aoi.intervals:
            valid, solution = ivl.get_solution()
            if valid:
                print(f"  {solution.start_dt} - {solution.stop_dt} : {solution.duration}")
        
        print()
    
    activities = []
    for solver_aoi in solver_aois:
        for ivl in solver_aoi.intervals:
            valid, solution = ivl.get_solution()
            
            if valid:
                activities.append(ScheduleActivity(
                    interval=solution,
                    sat_id=solver_aoi.paoi.sat.id,
                    payload_id=solver_aoi.paoi.sensor.id,
                    properties={
                        "aoi_id": solver_aoi.paoi.aoi.id
                    }))
                record_result(report, solver_aoi.paoi.aoi.id, Result.SCHEDULED,
                              satellite_id=solver_aoi.paoi.sat.id,
                              sensor_id=solver_aoi.paoi.sensor.id,
                              ivl=ivl.original
                              )

    activities.sort(key=lambda x: x.interval)
    
    for i, a in enumerate(activities):
        print(f"{i} - {a}")
        
    print(report)


def try_to_add(
    sched: Schedule, paoi: PreprocessedAoi, ivl: orekitfactory.time.DateInterval
) -> tuple[Result, Schedule]:
    intervals = orekitfactory.time.list_union(sched.intervals, ivl)

    return Result.SCHEDULED, sched.with_intervals(intervals)
