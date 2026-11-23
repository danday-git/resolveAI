from time import monotonic

from app.api.auth import _attempts, _check_login_limit


def test_login_limit_prunes_stale_attempt_keys():
    stale_stamp = monotonic() - 61
    _attempts.update({f"stale-{index}": [stale_stamp] for index in range(10_001)})

    _check_login_limit("current")

    assert "stale-0" not in _attempts
    assert set(_attempts) == {"current"}
