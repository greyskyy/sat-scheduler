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
    """The area of interest."""
    sat: SatelliteModel
    """The satellite model."""
    sensor: CameraSensorModel
    """The sensor model."""
    intervals: orekitfactory.time.DateIntervalList
    """Intervals when the satellite payload is in view of the aoi."""


@dataclasses.dataclass(frozen=True)
class PreprocessingResult:
    """Result of preprocessing a single satellite/sensor pair."""

    platform: Platform
    """The satellite platform."""
    aois: tuple[PreprocessedAoi]
    """The list of preprocessed aois."""
    interval: orekitfactory.time.DateInterval
    """The overall time interval."""

    @property
    def sat(self) -> SatelliteModel:
        """The satellite model."""
        return self.platform.model

    @property
    def ephemeris(self) -> BoundedPropagator:
        """The satellite ephemeris, defined as a pre-propagated `Ephemeris` instance."""
        return self.platform.ephemeris


@dataclasses.dataclass(frozen=True, kw_only=True)
class UnitOfWork:
    """A single pre-processing unit of work."""

    interval: orekitfactory.time.DateInterval
    """The propagation time interval."""
    sat: SatelliteModel
    """The satellite model."""
    aois: typing.Sequence[Aoi]
    """The aois defined on the ellispoid."""
    centralBody: ReferenceEllipsoid
    """The central body around which propagation occurs."""
    context: DataContext
    """Data context to use throughout execution."""
    step: dt.timedelta = dt.timedelta(minutes=10)
    """Time step to use during propagation."""
    test_mode: bool = False
    """Flag indicating whether to run in test mode."""
    sensor_ids: list[str] = dataclasses.field(default_factory=list)
    """The lsit of sensor ids to run during this unit of work."""


def aois_from_results(results: typing.Sequence[PreprocessingResult]) -> typing.Iterable[PreprocessedAoi]:
    """Iterate over the preprocessed aois in the provided result sequence.

    Args:
        results (Sequence[PreprocessingResult]): The iterable preprocessing results

    Yields:
        Iterator[PreprocessedAoi]: An iterator over all pre-processed AOIs in the result list.
    """
    for r in results:
        yield from r.aois
