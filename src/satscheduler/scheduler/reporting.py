"""Scheduler reporting classes and methods."""
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
        }
    )
