"""Compute priority and score values for aois."""
import collections
import typing

from ..aoi import Aoi
from ..configuration import StandardScoreData, get_config
from ..preprocessor import PreprocessedAoi


ScoredAoi = collections.namedtuple("ScoredAoi", field_names=("score", "aoi"))
"""Tuple of aoi and score."""


def score_and_sort_aois(
    aois: typing.Sequence[Aoi | PreprocessedAoi], score_func: typing.Callable[[Aoi | PreprocessedAoi], float] = None
) -> list[ScoredAoi]:
    """Compute the score for the set of AOIs, then sort them in descending score order.

    Args:
        aois (typing.Sequence[Aoi  |  PreprocessedAoi]): The list of aois
        score_func (typing.Callable[[Aoi  |  PreprocessedAoi], float], optional): The score function.. Defaults to None.

    Returns:
        list[ScoredAoi]: The ordered list of scored aois.
    """
    scored_aois: list[ScoredAoi] = []
    for value in score_aois(aois, score_func=score_func):
        if value.score > 0:
            scored_aois.append(value)

    scored_aois.sort(key=lambda x: (-x.score, x.aoi.aoi.id if isinstance(x.aoi, PreprocessedAoi) else x.aoi.id))

    return scored_aois


def score_aois(
    aois: typing.Sequence[Aoi | PreprocessedAoi],
    score_func: typing.Callable[[Aoi | PreprocessedAoi], float] = None,
) -> typing.Iterable[ScoredAoi]:
    """Score a collection of AOIs.

    The provided core function must accept the same type as the collection provided.

    If no score function is provided, a constant score will be computed.

    Args:
        aois (typing.Sequence[Aoi | PreprocessedAoi]): The sequence of AOIs to score.
        score_func (typing.Callable[[Aoi | PreprocessedAoi], int], optional): The function which computes
        the score. Defaults to None.

    Yields:
        Iterator[typing.Iterable[ScoredAoi]]: The scored aoi.
    """
    if score_func is None:
        score_func = construct_standard_score_func()

    for aoi in aois:
        score = score_func(aoi)
        yield ScoredAoi(score=score, aoi=aoi)


def standard_score(aoi: Aoi, config: StandardScoreData) -> float:
    """Compute score using the standard scoring equation.

    Args:
        aoi (Aoi): The aoi for which score will be computed.
        config (StandardScoreData): The score configuration data.

    Returns:
        float: The score.
    """
    country_factor = 1
    if config.country:
        country_factor = config.country.get(aoi.country, 1.0)

    continent_factor = 1
    if config.continent:
        continent_factor = config.continent.get(aoi.continent, 1.0)

    region_factor = 1.0
    if config.regions:
        for r in config.regions:
            if r.contains and r.region.contains(aoi.polygon):
                region_factor *= r.multiplier
            elif (not r.contains) and r.region.overlaps(aoi.polygon):
                region_factor *= r.multiplier

    return (aoi.priority**config.priority_exp) * country_factor * continent_factor * region_factor


def construct_standard_score_func(
    config: StandardScoreData = None,
) -> typing.Callable[[Aoi | PreprocessedAoi], float]:
    """Construct a standard score equation, loading the config if necessary.

    Args:
        config (StandardScoreData, optional): The configuration. Defaults to None.

    Returns:
        typing.Callable[[Aoi|PreprocessedAoi], float]: The score function.
    """
    if config is None:
        config = get_config().score or StandardScoreData()

    def score_func(aoi: Aoi | PreprocessedAoi) -> float:
        if isinstance(aoi, PreprocessedAoi):
            return standard_score(aoi.aoi, config)
        elif isinstance(aoi, Aoi):
            return standard_score(aoi, config)
        else:
            return 1

    return score_func
