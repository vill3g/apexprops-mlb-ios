"""The trailing-stop settings saved from the dashboard must be what the settler reads back."""
import uuid

import backend.database.models as models
from backend.database.models import get_all_active_users, get_user_by_id, update_user_config


def _save(user_id, enabled, activation, distance):
    update_user_config(
        user_id=user_id, trade_size_dollars=10.0, paper_trade_size_dollars=10.0,
        stop_loss_pct=50.0, take_profit_pct=50.0, trailing_stop_enabled=enabled,
        trailing_stop_activation_pct=activation, trailing_stop_distance_pct=distance,
    )


def test_trailing_settings_round_trip_to_the_settler():
    uid = models.create_user(f"trail_rt_{uuid.uuid4().hex[:6]}", "pw-hash")
    _save(uid, enabled=True, activation=40.0, distance=8.0)

    stored = get_user_by_id(uid)
    assert bool(stored["trailing_stop_enabled"]) is True
    assert float(stored["trailing_stop_activation_pct"]) == 40.0
    assert float(stored["trailing_stop_distance_pct"]) == 8.0

    # The settler reads the user from get_all_active_users(), so the saved values must show up there too.
    active = {u["id"]: u for u in get_all_active_users()}
    assert uid in active
    assert bool(active[uid]["trailing_stop_enabled"]) is True
    assert float(active[uid]["trailing_stop_activation_pct"]) == 40.0

    _save(uid, enabled=False, activation=40.0, distance=8.0)
    assert bool(get_user_by_id(uid)["trailing_stop_enabled"]) is False
