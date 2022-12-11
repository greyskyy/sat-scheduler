"""Core data structures."""
import dataclasses
import datetime as dt
import orekitfactory.time
import typing

from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import BoundedPropagator

from ..aoi import Aoi
from ..models import SatelliteModel, CameraSensorModel, Platform


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

    platform: Platform
    aois: tuple[PreprocessedAoi]
    interval: orekitfactory.time.DateInterval

    @property
    def sat(self) -> SatelliteModel:
        return self.platform.model

    @property
    def ephemeris(self) -> BoundedPropagator:
        return self.platform.ephemeris


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


def aois_from_results(results: typing.Sequence[PreprocessingResult]) -> typing.Iterable[PreprocessedAoi]:
    """Iterate over the preprocessed aois in the provided result sequence.

    Args:
        results (Sequence[PreprocessingResult]): The iterable preprocessing results

    Yields:
        Iterator[PreprocessedAoi]: An iterator over all pre-processed AOIs in the result list.
    """
    for r in results:
        yield from r.aois
