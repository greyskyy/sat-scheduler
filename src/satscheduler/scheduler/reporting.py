"""Scheduler reporting classes and methods."""
import datetime as dt
import orekitfactory.time
import pandas as pd
import typing

from ..preprocessor import PreprocessedAoi

from .core import Result


def init_access_report(aois: typing.Sequence[PreprocessedAoi]) -> pd.DataFrame:
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


def record_result(
    report: pd.DataFrame,
    aoi_id: str,
    result: Result,
    satellite_id: str = None,
    sensor_id: str = None,
    start: dt.datetime = None,
    stop: dt.datetime = None,
    ivl: orekitfactory.time.DateInterval = None,
):
    mask = report["aoi_id"] == aoi_id

    if satellite_id:
        mask = mask & (report["satellite_id"] == satellite_id)

    if sensor_id:
        mask = mask & (report["sensor_id"] == sensor_id)

    if start:
        mask = mask & (report["start"] == start)

    if stop:
        mask = mask & (report["stop"] == stop)

    if ivl:
        mask = mask & (report["start"] == ivl.start_dt) & (report["stop"] == ivl.stop_dt)

    report.loc[mask, "result"] = result
    report.loc[mask, "result_str"] = result.name.lower()
