"""Unit tests for utils/czml.py."""
import pytest
import orekit


@pytest.fixture(scope="module", autouse=True)
def init_orekit():
    """Initialize orekit for each test."""
    orekit.initVM()


def test_polygon():
    """Verify the Polygon class."""
    import satscheduler.utils.czml

    p = satscheduler.utils.czml.Polygon(
        positions=[],
        fill="fill",
        outline="outline",
        outlineColor="color",
        outlineWidth=5,
    )

    assert "color" == p.outlineColor
    assert 5 == p.outlineWidth
