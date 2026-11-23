from app.api import auth


def test_login_limit_prunes_stale_attempt_keys(monkeypatch):
    auth._attempts.clear()
    monkeypatch.setattr(auth, "monotonic", lambda: 100.0)
    monkeypatch.setattr(auth, "_last_prune", None)
    auth._attempts.update({f"stale-{index}": [39.0] for index in range(10_001)})

    auth._check_login_limit("current")

    assert "stale-0" not in auth._attempts
    assert set(auth._attempts) == {"current"}
    assert auth._last_prune == 100.0


def test_login_limit_throttles_full_prunes_to_once_per_minute(monkeypatch):
    auth._attempts.clear()
    now = [130.0]
    monkeypatch.setattr(auth, "monotonic", lambda: now[0])
    monkeypatch.setattr(auth, "_last_prune", 100.0)
    auth._attempts.update({f"stale-{index}": [0.0] for index in range(10_001)})

    auth._check_login_limit("first")
    assert "stale-0" in auth._attempts

    now[0] = 159.9
    auth._check_login_limit("second")
    assert "stale-0" in auth._attempts

    now[0] = 160.0
    auth._check_login_limit("third")
    assert "stale-0" not in auth._attempts
    assert auth._last_prune == 160.0
