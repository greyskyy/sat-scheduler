import orekit
from datetime import datetime as dt, timedelta
from orekit.pyhelpers import setup_orekit_curdir, datetime_to_absolutedate

import pytest


@pytest.fixture(scope="session", autouse=True)
def vm():
    vm = orekit.initVM()
    setup_orekit_curdir(".data/orekit-data-master.zip")

    return vm


def test_duration_props():
    from satscheduler import utils

    dt1 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:00:00"))
    dt2 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:05:00"))
    dt3 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:10:00"))
    dt4 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T12:15:00"))

    dt5 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:00:00"))
    dt6 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:05:00"))
    dt7 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:10:00"))
    dt8 = datetime_to_absolutedate(dt.fromisoformat("2022-08-05T13:15:00"))

    ivl1 = utils.DateInterval(dt1, dt2)
    ivl2 = utils.DateInterval(dt3, dt4)
    ivl3 = utils.DateInterval(dt1, dt3)

    ivl4 = utils.DateInterval(dt5, dt7)
    ivl5 = utils.DateInterval(dt6, dt8)

    assert dt1.equals(ivl1.start)
    assert dt2.equals(ivl1.stop)

    assert 300.0 == ivl1.duration_secs
    assert timedelta(minutes=5.0) == ivl1.duration

    assert not ivl1.overlaps(ivl2)
    assert ivl1.overlaps(ivl3)

    # verify stop inclusivity
    assert not ivl3.overlaps(ivl2)
    assert ivl3.overlaps(ivl2, stopInclusive=True)
