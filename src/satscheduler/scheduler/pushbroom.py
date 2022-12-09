"""Pushbroom scheduler.

A pushbroom scheduler maintains a constant payload pointing without articulating
during collection. It is the satellite motion which moves the payload across the
AOIs.
"""
import argparse
import datetime as dt
import logging
import json
import math
import orekitfactory.time
import typing

from .core import Platform, Platforms, filter_aois_no_access, SatPayloadId
from .reporting import init_access_report, record_result, Result, record_score_and_order, record_bonusing
from .schedule import Schedule, ScheduleActivity, ScheduleEncoder
from .scheduler import add_aois_to_solvers, solve
from .score import score_and_sort_aois, ScoredAoi
from .solver import (
    create_solver,
    SolverAoi,
    add_non_overlapping_constraints,
    result_is_successful,
)
from ..configuration import get_config, Configuration
from ..preprocessor import create_uows, run_units_of_work, PreprocessingResult, PreprocessedAoi, aois_from_results
from ..utils import positive_int, DefaultFactoryDict

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

    parser.add_argument(
        "--batch-size",
        help="The maximum number of aois to run per batch when scheduling. If specified, must be greater "
        "than zero, Defaults to MAX_INT.",
        nargs=1,
        metavar="N",
        type=positive_int,
        default=None,
    )

    solver_group = parser.add_mutually_exclusive_group()
    solver_group.add_argument(
        "--solver-report",
        help="Filename where to specify a solver output report. Use '{sat}', '{sensor}', and '{batch}' for the"
        " satellite id, sensor id, and batch index respectively. Defaults to 'pushbroom_solver_{sat}_{sensor}.csv'",
        dest="solver_report",
        type=str,
        nargs="?",
        metavar="FILENAME",
        default="pushbroom_solver_{sat}_{sensor}_{batch}.csv",
        const="pushbroom_solver_{sat}_{sensor}_{batch}.csv",
    )
    solver_group.add_argument(
        "--no-solver-report",
        dest="solver_report",
        action="store_const",
        const=None,
        help="Suppress the solver report generation.",
    )

    report_group = parser.add_mutually_exclusive_group()
    report_group.add_argument(
        "--report",
        help="Filename where to specify the result report. Defaults to 'pushbroom_results.csv'",
        dest="report",
        type=str,
        nargs="?",
        metavar="FILENAME",
        default="pushbroom_results.csv",
        const="pushbroom_results.csv",
    )
    report_group.add_argument(
        "--no-report",
        dest="report",
        action="store_const",
        const=None,
        help="Suppress the result report generation.",
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
    logger.info("Initializing reports.")
    platforms = Platforms([Platform(model=r.sat, ephemeris=r.ephemeris) for r in results])
    report = init_access_report(aois_from_results(results))

    # sort the aois into priority order
    logger.info("Scoring AOIs.")
    report["score"] = 0
    report["order_index"] = -1
    scored_aois = score_and_sort_aois(filter_aois_no_access(aois_from_results(results)))
    record_score_and_order(report, scored_aois)

    if args.batch_size:
        batch_size = args.batch_size
    elif config.extensions and "pushbroom" in config.extensions and "batch_size" in config.extensions["pushbroom"]:
        batch_size = config.extensions["pushbroom"]["batch_size"]
    else:
        batch_size = len(scored_aois)

    # Initialize variables to hold across batches
    keys = list(platforms.generate_ids())
    payload_intervals = {k: orekitfactory.time.DateIntervalList() for k in keys}
    duration_limit = {k: 0.25 * (config.run.stop - config.run.start).total_seconds() for k in keys}

    # Schedule in batches
    for batch_start in range(0, len(scored_aois), batch_size):
        batch_stop = batch_start + batch_size

        logger.info(
            "Processing batch %d/%d", 1 + int(batch_start / batch_size), math.ceil(len(scored_aois) / batch_size)
        )

        # build the solvers
        logger.info("Adding aois to solvers.")
        batch_data = BatchData(config, payload_intervals, duration_limit)

        schedule_batch(
            args, batch_data, scored_aois[batch_start:batch_stop], report, 1 + int(batch_start / batch_size)
        )

    # generate schedules and record bonusing
    schedules = {}
    for k in keys:
        record_bonusing(report, satellite_id=k.sat_id, sensor_id=k.payload_id, payload_intervals=payload_intervals[k])
        schedules[k] = Schedule(
            id=f"{k.sat_id}_{k.payload_id}",
            intervals=payload_intervals[k],
            activities=[
                ScheduleActivity(interval=ivl, sat_id=k.sat_id, payload_id=k.payload_id)
                for ivl in payload_intervals[k]
            ],
        )

    # write the report
    if args.report:
        report.to_csv(args.report)

    # save each schedule
    for k, v in schedules.items():
        with open(f"pushbroom_{k.sat_id}_{k.payload_id}.json", "w") as f:
            json.dump(v, f, cls=ScheduleEncoder, indent=2)

        # save schedule czml


class BatchData:
    """Data package for a batch run."""

    solvers: DefaultFactoryDict = None
    """Solver for this batch, indexed by key."""
    solver_aois = DefaultFactoryDict(lambda x: [])
    """List of solver aois for this batch, indexed by key."""
    scores = DefaultFactoryDict(lambda x: [])
    """List of score total solver variables, indexed by key."""
    durations = DefaultFactoryDict(lambda x: [])
    """Lists of duration solver variables, indexed by key. """
    payload_intervals: dict[SatPayloadId, orekitfactory.time.DateIntervalList] = None
    """Lists of payload activity intervals, indexed by key."""
    duration_limit: dict[SatPayloadId, float] = None
    """Total payload time interval limits for this batch, indexed by key."""

    def __init__(
        self,
        config: Configuration,
        payload_intervals: dict[SatPayloadId, orekitfactory.time.DateIntervalList],
        duration_limit: dict[SatPayloadId, float],
    ):
        """Class constructor.

        Args:
            config (Configuration): Configuration object.
            payload_intervals (dict[SatPayloadId, orekitfactory.time.DateIntervalList]): List of payload intervals.
            duration_limit (dict[SatPayloadId, float]): Duration limit for this batch.
        """
        self.solvers = DefaultFactoryDict(lambda x: create_solver(config=config.optimizer))
        self.payload_intervals = payload_intervals
        self.duration_limit = duration_limit

    def paoi_modifer(self, paoi: PreprocessedAoi, key: SatPayloadId) -> PreprocessedAoi:
        """If the schedule already has intervals from a previous batch, remove those intervals from the AOI.

        Args:
            paoi (PreprocessedAoi): The preprocessed aoi.
            key (SatPayloadId): The key.

        Returns:
            PreprocessedAoi: The modified aoi.
        """
        if len(self.payload_intervals[key]):
            return PreprocessedAoi(
                aoi=paoi.aoi, sat=paoi.sat, sensor=paoi.sensor, intervals=paoi.intervals - self.payload_intervals[key]
            )
        else:
            return paoi

    def each_aoi(self, key: SatPayloadId, score: float, solver_aoi: SolverAoi):
        """Add the solver aoi to the batch.

        Args:
            key (SatPayloadId): The key to use.
            score (float): The aoi score.
            solver_aoi (SolverAoi): The api to add.
        """
        # aoi to their respective solvers
        self.solver_aois[key].append(solver_aoi)

        # add aoi to cumulative summation constraints
        dur = self.solvers[key].Sum(map(lambda ivl: ivl.stop - ivl.start, solver_aoi.intervals))
        self.scores[key].append(score * dur)
        self.durations[key].append(dur)

    def cleanup(self, report=None):
        """Cleanup the batch, removing unnecessary solvers / aois.

        Args:
            report (pandas.DataFrame, optional): The report dataframe. Defaults to None.
        """
        keys = list(self.solvers.keys())

        for k in keys:
            if self.duration_limit[k] <= 0:
                for solver_aoi in self.solver_aois[k]:
                    if report is not None:
                        paoi: PreprocessedAoi = solver_aoi.paoi
                        for ivl in solver_aoi.intervals:
                            record_result(
                                report,
                                aoi_id=paoi.aoi.id,
                                result=Result.EXCEEDED_PAYLOAD_DUTY_CYCLE,
                                satellite_id=paoi.sat.id,
                                sensor_id=paoi.sensor.data.id,
                                ivl=ivl.original,
                            )

                del self.solver_aois[k]
                del self.scores[k]
                del self.durations[k]
                del self.solvers[k]


def add_final_constraints(batch_data: BatchData):
    """Add final constraint and objective function to the batch.

    Args:
        batch_data (BatchData): The batch data.
    """
    for k, solver in batch_data.solvers.items():
        solver = batch_data.solvers[k]

        # ensure all activities are non-overlapping
        add_non_overlapping_constraints(solver, batch_data.solver_aois[k])

        # add total duration constraint
        solver.Add(solver.Sum(batch_data.durations[k]) <= batch_data.duration_limit[k])

        # maximize the total score
        solver.Maximize(solver.Sum(batch_data.scores[k]))


def schedule_batch(args, batch_data: BatchData, scored_aois: typing.Sequence[ScoredAoi], report, batch_number: int):
    """Schedule a single batch.

    Args:
        args (argparse.Namespace): Command line arguments.
        batch_data (BatchData): The batch data.
        scored_aois (typing.Sequence[ScoredAoi]): Sequence of aois in this batch.
        report (pandas.DataFrame): Reporting dataframe.
        batch_number (int): The batch index, used for logging.
    """
    logger = logging.getLogger(__name__)

    # add AOIs to the solvers, accumulate the score and durations
    add_aois_to_solvers(
        scored_aois, batch_data.solvers, paoi_modifier=batch_data.paoi_modifer, callback=batch_data.each_aoi
    )

    # remove unecessary solvers
    batch_data.cleanup(report=report)

    # add final constraints and objective functions
    add_final_constraints(batch_data)

    logger.debug("Created %d solvers", len(batch_data.solvers))

    # solve every one
    for k, solver in batch_data.solvers.items():
        logger.info("Solving for %s", str(k))

        sat_id = k.sat_id
        sensor_id = k.payload_id

        result, intervals = solve(
            solver,
            report=report,
            solver_aois=batch_data.solver_aois[k],
            solver_report=args.solver_report,
            solver_report_path=args.solver_report.format(sat=sat_id, sensor=sensor_id, batch=batch_number),
        )
        if result_is_successful(result):
            total = sum(map(lambda i: i.duration_secs, intervals), 0)
            logger.info(
                "Scheduled %s new payload activity time (%f secs) (%s duty cycle remaining).",
                str(dt.timedelta(seconds=total)),
                total,
                str(dt.timedelta(seconds=batch_data.duration_limit[k] - total)),
            )
            batch_data.duration_limit[k] = batch_data.duration_limit[k] - total
            batch_data.payload_intervals[k] = batch_data.payload_intervals[k] + intervals
