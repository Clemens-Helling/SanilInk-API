from app.main import app


def test_intake_routes_are_registered():
    paths = {route.path for route in app.routes}

    assert "/intake/{intake_key_id}/submit" in paths
    assert "/intake/keys" in paths
    assert "/intake/pending" in paths
