"""Core data structures."""
import dataclasses
import datetime as dt
import orekitfactory.time
import typing

from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import BoundedPropagator

from ..aoi import Aoi
from ..models import SatelliteModel, CameraSensorModel


@dataclasses.dataclass(frozen=True)
class PreprocessedAoi:
    """Preprocessing result for a single AOI."""

    aoi: Aoi
    sat: SatelliteModel
    sensor: CameraSensorModel
    intervals: orekitfactory.time.DateIntervalList


@dataclasses.dataclass(frozen=True)
class PreprocessingResult:
    """Result of preprocessing a single satellite/sensor pair."""

    sat: SatelliteModel
    ephemeris: BoundedPropagator
    aois: tuple[PreprocessedAoi]
    interval: orekitfactory.time.DateInterval


@dataclasses.dataclass(frozen=True, kw_only=True)
class UnitOfWork:
    """A single pre-processing unit of work."""

    interval: orekitfactory.time.DateInterval
    sat: SatelliteModel
    aois: typing.Sequence[Aoi]
    centralBody: ReferenceEllipsoid
    context: DataContext
    step: dt.timedelta = dt.timedelta(minutes=10)
    test_mode: bool = False
    sensor_ids: list[str] = dataclasses.field(default_factory=list)
