"""Common scheduling functions and utilities."""
import czml3.properties
import czml3.types
import logging
import orekitfactory.time
import typing

from ..aoi.czml import aoi_czml
from ..configuration import get_config, Configuration
from ..preprocessor import PreprocessedAoi
from ..models import SatPayloadId, Platform, SensorModel
from ..models.czml import platform_czml, sensor_czml
from ..utils.czml import write_czml

from .core import Schedule, Result

from .score import ScoredAoi
from .solver import (
    SolverAoi,
    add_to_solver,
    result_to_string,
    result_is_successful,
    generate_solver_report,
)
from .reporting import record_result


def add_aois_to_solvers(
    scored_aois: typing.Sequence[ScoredAoi],
    solvers: dict[SatPayloadId, typing.Any],
    key_type: typing.Callable[[str, str], SatPayloadId] = SatPayloadId,
    paoi_modifier: typing.Callable[[PreprocessedAoi], PreprocessedAoi] = None,
    callback: typing.Callable[[SatPayloadId, float, SolverAoi], None] = None,
):
    """Add the provided aois to the solvers.

    Args:
        scored_aois (typing.Sequence[ScoredAoi]): Sequence of aois to add the the solvers.
        solvers (dict[SatPayloadId, typing.Any]): Dictionary of solvers, indexed by the key.
        key_type (typing.Callable[[str, str], SatPayloadId]): Function to create the key from the provided satellite
        id, sensor id
        parameters. Defaults to `SatPayloadId`.
        paoi_modifier (typing.Callable[[PreprocessedAoi], PreprocessedAoi], optional): Modifier function to mutate the
        preprocessed
        aoi, prior to adding to the solver. Defaults to None.
        callback (typing.Callable[[SatPayloadId, float, SolverAoi], None], optional): Callback triggered after
        each aoi is added to the solver. Used to perform additional configuration or add additional
        constraints. Defaults to None.
    """
    for score, paoi in scored_aois:
        sat_model = paoi.sat
        sensor_model = paoi.sensor

        key = key_type(sat_model.id, sensor_model.id)

        # apply a filter if needed
        if paoi_modifier:
            paoi = paoi_modifier(paoi, key)

        solver = solvers[key]
        solver_aoi = add_to_solver(solver, paoi)

        if callback:
            callback(key, score, solver_aoi)


def record_all(report, solver_aois: typing.Sequence[SolverAoi], result: Result):
    """Record all the solver aois with same result.

    Args:
        report (pd.DataFrame): The report DataFrame.
        solver_aois (typing.Sequence[SolverAoi]): Sequence of solver aois to record.
        result (Result): The result.
    """
    for solver_aoi in solver_aois:
        for ivl in solver_aoi.intervals:
            record_result(
                report,
                solver_aoi.paoi.aoi.id,
                result,
                satellite_id=solver_aoi.paoi.sat.id,
                sensor_id=solver_aoi.paoi.sensor.id,
                ivl=ivl.original,
                interval_overlap=True,  # just check for overlap here, because the AOI intervals are adjusted
            )


def record_and_consolidate_intervals(
    solver_aois: typing.Sequence[SolverAoi], report
) -> orekitfactory.time.DateIntervalList:
    """Record results in the report and convert solver_aoi output to a dateinterval list.

    Args:
        solver_aois (typing.Sequence[SolverAoi]): The sequence of solver aois.
        report (pd.DataFrame): The report dataframe.

    Returns:
        orekitfactory.time.DateIntervalList: The resulting list of valid interals.
    """
    intervals = []
    for solver_aoi in solver_aois:
        for ivl in solver_aoi.intervals:
            valid, solution = ivl.get_solution()

            if valid:
                intervals.append(solution)
                record_result(
                    report,
                    solver_aoi.paoi.aoi.id,
                    Result.SCHEDULED,
                    satellite_id=solver_aoi.paoi.sat.id,
                    sensor_id=solver_aoi.paoi.sensor.id,
                    ivl=ivl.original,
                    interval_overlap=True,  # just check for overlap here, because the AOI intervals are adjusted
                )
            else:
                # if not scheduled, it's because we hit a duty cycle limit
                record_result(
                    report,
                    solver_aoi.paoi.aoi.id,
                    Result.EXCEEDED_PAYLOAD_DUTY_CYCLE,
                    satellite_id=solver_aoi.paoi.sat.id,
                    sensor_id=solver_aoi.paoi.sensor.id,
                    ivl=ivl.original,
                    interval_overlap=True,  # just check for overlap here, because the AOI intervals are adjusted
                )

    return orekitfactory.time.as_dateintervallist(intervals)


def solve(
    solver,
    report,
    solver_aois: typing.Sequence[SolverAoi],
    solver_report: bool = True,
    solver_report_path="solver_report.csv",
) -> tuple[int, orekitfactory.time.DateIntervalList]:
    """Solve the scheduler problem by calling `solver.Solve()` and process the results.

    In the case of a solver failure, the report will be updated assigning a reason of
    `Result.SOLVER_INFEASIBLE_SOLUTION` to each aoi.

    Args:
        solver (Solver): The solver.
        report (pandas.DataFrame): The report dataframe, where output will be recorded if a solver failure occurs.
        solver_aois (typing.Sequence[SolverAoi]): The list of solver aois solved by the solver.
        solver_report (bool, optional): Whether or not to output the solver report. Defaults to True.
        solver_report_path (str, optional): Path of the output solver report, if enabled. Defaults to
        "solver_report.csv".

    Returns:
        tuple[int, orekitfactory.time.DateIntervalList]: _description_
    """
    logger = logging.getLogger(__name__)

    result = solver.Solve()
    logger.debug("Solver result=%s", result_to_string(result))

    if solver_report:
        generate_solver_report(
            solver,
            output_path=solver_report_path,
        )
    if result_is_successful(result):
        intervals = record_and_consolidate_intervals(solver_aois=solver_aois, report=report)
        return result, intervals
    else:
        logger.error(
            "Solver failed to produce a solution: result=%s",
            result_to_string(result),
            exc_info=0,
            stack_info=0,
        )
        record_all(report, solver_aois=solver_aois, result=Result.SOLVER_INFEASIBLE_SOLUTION)
        return result, orekitfactory.time.DateIntervalList()


def write_schedule_czml(
    platform: Platform,
    fname: str,
    schedule: Schedule,
    name: str = None,
    sensor: SensorModel = None,
    config: Configuration = None,
    aois: typing.Sequence[PreprocessedAoi] = None,
):
    """Write a schedule to CZML.

    Args:
        platform (Platform): The schedule's platform.
        fname (str): The filename.
        schedule (Schedule): The schedule.
        name (str, optional): The czml document name, if `None` the fname's basename will be used.. Defaults to None.
        sensor (SensorModel, optional): The sensor model relevant for the schedule. Defaults to None.
        config (Configuration, optional): The application configuration. Defaults to None.
        aois (typing.Sequence[PreprocessedAoi], optional): The set of aois to display during the schedule. Defaults
        to None.
    """
    if config is None:
        config = get_config()

    if name is None:
        name = f"schedule/{platform.id}/{sensor.id}" if sensor else f"schedule/{platform.id}"

    # build the AOI packets
    aoi_czml_packets = []
    for paoi in aois:
        valid_ivls = orekitfactory.time.list_intersection(schedule.intervals, paoi.intervals)
        if len(valid_ivls):
            aoi_czml_packets.append(
                aoi_czml(paoi.aoi, config=config.aois, zones=True, show=True, fill_show=valid_ivls)
            )

    # build the sensor packets
    sensor_packets = (
        sensor_czml(
            platform=platform,
            sensor=sensor,
            show=schedule.intervals.span,
            fill_show=schedule.intervals,
        )
        if sensor
        else []
    )

    # save schedule czml
    write_czml(
        fname=fname,
        name=name,
        clock=czml3.types.IntervalValue(
            start=config.run.start,
            end=config.run.stop,
            value=czml3.properties.Clock(currentTime=config.run.start, multiplier=10),
        ),
        packets=[
            platform_czml(platform),
            *sensor_packets,
            *aoi_czml_packets,
        ],
    )
