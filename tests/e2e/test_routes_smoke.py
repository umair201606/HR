"""Every GET route must render for an admin — no 5xx, ever.

Uses Flask's test client rather than the live-server fixtures in conftest:
this needs no port, runs in seconds, and is the harness that catches a
url_for() left pointing at a deleted endpoint after a refactor.
"""
import os
import re
import tempfile

import pytest

# Point at a throwaway DB before app import — importing app builds the engine.
_TMP_DB = os.path.join(tempfile.gettempdir(), "erp_routes_smoke.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = "sqlite:///" + _TMP_DB.replace("\\", "/")

from app import app as flask_app  # noqa: E402

# Arg name -> value used when filling a parameterised rule.
SAMPLE_ARGS = {"year": 2026, "month": 7}
DEFAULT_ARG = 1


def _fill(rule):
    path = str(rule)
    for arg in rule.arguments:
        val = SAMPLE_ARGS.get(arg, DEFAULT_ARG)
        path = re.sub(r"<[^<>]*" + re.escape(arg) + r">", str(val), path)
    return path


def _get_rules():
    return [r for r in flask_app.url_map.iter_rules()
            if "GET" in r.methods and r.endpoint != "static"]


@pytest.fixture(scope="module")
def admin_client():
    with flask_app.test_client() as c:
        c.get("/")  # triggers lazy create_all + migrate + seed
        from hr_app.models.user import User
        with flask_app.app_context():
            user = (User.query.filter(User.email.ilike("admin%")).first()
                    or User.query.first())
            assert user is not None, "seed produced no users"
            uid = user.id
        with c.session_transaction() as sess:
            sess["_user_id"] = str(uid)
            sess["_fresh"] = True
        yield c


@pytest.mark.parametrize("rule", _get_rules(), ids=lambda r: str(r))
def test_get_route_does_not_error(admin_client, rule):
    path = _fill(rule)
    assert "<" not in path, f"unresolved argument in {path}"
    resp = admin_client.get(path)
    assert resp.status_code < 500, (
        f"{path} returned {resp.status_code}\n"
        f"{resp.get_data(as_text=True)[:800]}"
    )


def test_no_route_references_deleted_settings_endpoints(admin_client):
    """The old settings blueprints are gone; nothing may still point at them."""
    dead = {"admin_settings.users", "admin_settings.user_rights",
            "admin_settings.account", "admin_settings.reset_rights",
            "inv_settings.settings_page", "finance_settings.index",
            "finance_settings.save_company", "finance_settings.save_report_settings",
            "finance_settings.add_period", "finance_settings.close_period",
            "finance_settings.reopen_period", "finance_settings.seed_periods",
            "finance_settings.update_user_access", "finance_settings.deactivate_user",
            "finance_settings.update_permissions"}
    live = {r.endpoint for r in flask_app.url_map.iter_rules()}
    assert not (dead & live), f"deleted endpoints still registered: {dead & live}"
