"""A basic satellite scheduler for a pushbroom sensor."""

from dataclasses import dataclass
from satscheduler.preprocessor import PreprocessingResult
from typing import Iterable
from org.orekit.data import DataContext
from org.orekit.propagation import BoundedPropagator

import logging

from satscheduler.satellite.satellite import Satellite, Sensor


def schedule(preprocessed: Iterable[PreprocessingResult], context: DataContext = None):
    logger = logging.getLogger(__name__)

    if context is None:
        context = DataContext.getDefault()

    sensors = {}
    for p in preprocessed:

        for sensor in p.sat.sensors:
            pass
