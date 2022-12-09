"""Scheduler reporting classes and methods."""
import datetime as dt
import orekitfactory.time
import pandas as pd
import typing

from ..preprocessor import PreprocessedAoi

from .core import Result
from .score import ScoredAoi


def init_access_report(aois: typing.Sequence[PreprocessedAoi]) -> pd.DataFrame:
    """Initialize an access report dataframe.

    The report dataframe will be seeded with each aoi/interval with a `Result.NO_DATA` value.
    Args:
        aois (typing.Sequence[PreprocessedAoi]): The aoi sequence.

    Returns:
        pd.DataFrame: The report dataframe.
    """
    aoi_id = []
    satellite = []
    sensor = []
    continent = []
    country = []
    start = []
    stop = []
    result = []
    result_str = []
    priority = []

    for paoi in aois:
        if len(paoi.intervals) == 0:
            aoi_id.append(paoi.aoi.id)
            continent.append(paoi.aoi.continent)
            country.append(paoi.aoi.country)
            satellite.append(paoi.sat.id)
            sensor.append(paoi.sensor.id)
            start.append(None)
            stop.append(None)
            result.append(Result.NO_ACCESS)
            result_str.append(Result.NO_ACCESS.name.lower())
            priority.append(paoi.aoi.priority)
        else:
            for ivl in paoi.intervals:
                aoi_id.append(paoi.aoi.id)
                continent.append(paoi.aoi.continent)
                country.append(paoi.aoi.country)
                satellite.append(paoi.sat.id)
                sensor.append(paoi.sensor.id)
                start.append(ivl.start_dt)
                stop.append(ivl.stop_dt)
                result.append(Result.NO_DATA)
                result_str.append(Result.NO_DATA.name.lower())
                priority.append(paoi.aoi.priority)

    return pd.DataFrame(
        {
            "aoi_id": aoi_id,
            "satellite_id": satellite,
            "sensor_id": sensor,
            "continent": continent,
            "country": country,
            "priority": priority,
            "start": start,
            "stop": stop,
            "result": result,
            "result_str": result_str,
        }
    )


def record_score_and_order(report: pd.DataFrame, scored_aois: typing.Sequence[ScoredAoi]):
    """Record the score and order fo the aois in the report.

    Args:
        report (pd.DataFrame): The report in which to record score and order.
        scored_aois (typing.Sequence[ScoredAoi]): The ordered sequence of scored aois.
    """
    for index, sa in enumerate(scored_aois):
        mask = (
            (report["aoi_id"] == sa.aoi.aoi.id)
            & (report["satellite_id"] == sa.aoi.sat.id)
            & (report["sensor_id"] == sa.aoi.sensor.data.id)
        )

        report.loc[mask, "score"] = sa.score
        report.loc[mask, "order_index"] = index


def record_result(
    report: pd.DataFrame,
    aoi_id: str,
    result: Result,
    satellite_id: str = None,
    sensor_id: str = None,
    start: dt.datetime = None,
    stop: dt.datetime = None,
    ivl: orekitfactory.time.DateInterval = None,
    overwrite: bool = False,
    interval_overlap: bool = False,
):
    """Record the result given the provided criteria.

    Args:
        report (pd.DataFrame): The report dataframe.
        aoi_id (str): The aoi id.
        result (Result): The result to record.
        satellite_id (str, optional): The satellite id filter by, if specified. Defaults to None.
        sensor_id (str, optional): The payload id to filter by, if specified. Defaults to None.
        start (dt.datetime, optional): The interval start. Defaults to None.
        stop (dt.datetime, optional): The interval stop. Defaults to None.
        ivl (orekitfactory.time.DateInterval, optional): The interval specified as a single object. Defaults to None.
        overwrite (bool, optional): Whether to force the overwrite of a more specific result value. Defaults to False.
        interval_overlap (bool, optional): Flag indicating whether the interval/[start,stop] should be considered for
        overlap or exact matches. Defaults to False.
    """
    mask = report["aoi_id"] == aoi_id

    if not overwrite:
        mask = mask & (report["result"] > result)

    if satellite_id:
        mask = mask & (report["satellite_id"] == satellite_id)

    if sensor_id:
        mask = mask & (report["sensor_id"] == sensor_id)

    if start:
        mask = mask & (report["start"] == start)

    if stop:
        mask = mask & (report["stop"] == stop)

    if ivl:
        if interval_overlap:
            mask = mask & (report["start"] <= ivl.stop_dt) & (report["stop"] >= ivl.start_dt)
        else:
            mask = mask & (report["start"] == ivl.start_dt) & (report["stop"] == ivl.stop_dt)

    report.loc[mask, "result"] = result
    report.loc[mask, "result_str"] = result.name.lower()


def record_bonusing(
    report: pd.DataFrame,
    satellite_id: str,
    payload_intervals: orekitfactory.time.DateIntervalList,
    sensor_id: str = None,
):
    """Record bonusing, or collection already covered by existing scheduled payload activities.

    Args:
        report (pd.DataFrame): The report dataframe.
        satellite_id (str): The satellite id
        payload_intervals (orekitfactory.time.DateIntervalList): The payload intervals.
        sensor_id (str, optional): The payload id. Defaults to None.
    """
    result = Result.ALREADY_SCHEDULED
    mask = (report["satellite_id"] == satellite_id) & (report["result"] > result)

    if sensor_id:
        mask = mask & (report["sensor_id"] == sensor_id)

    for ivl in payload_intervals:
        ivl_mask = mask & (report["start"] <= ivl.stop_dt) & (ivl.start_dt <= report["stop"])
        report.loc[ivl_mask, "result"] = result
        report.loc[ivl_mask, "result_str"] = result.name.lower()
