import pytest
from backend.database.models import update_user_config, get_user_by_username, create_user

def test_user_config_kwarg_mapping():
    # Make a dummy user
    try:
        create_user("testuser_config", "password")
    except:
        pass
        
    u = get_user_by_username("testuser_config")
    if not u:
        return
        
    uid = u["id"]
    
    # Use kwargs
    update_user_config(
        user_id=uid,
        trade_size_dollars=99.0,
        paper_trade_size_dollars=101.0,
        stop_loss_pct=15.0,
        one_click_trade=True,
        auto_force_trade=False,
        trading_style="SNIPER",
        signal_source="XGB",
        take_profit_pct=30.0,
        max_daily_trades=5,
        max_daily_risk=100.0,
        trailing_stop_enabled=True,
        trailing_stop_activation_pct=20.0,
        trailing_stop_distance_pct=5.0,
        second_entry_enabled=True,
        second_entry_max_ask=0.8,
        model_choice="RL_DQN",
        train_window=2000,
        regularization_c=0.1,
        class_weight="balanced",
        xgb_estimators=100,
        xgb_max_depth=3,
        xgb_learning_rate=0.05,
        ignore_pass_technical=True,
        one_shot_ai=True
    )
    
    u_updated = get_user_by_username("testuser_config")
    assert u_updated["trade_size_dollars"] == 99.0
    assert u_updated["paper_trade_size_dollars"] == 101.0
    assert u_updated["stop_loss_pct"] == 15.0
    assert u_updated["one_click_trade"] == 1
    assert u_updated["trading_style"] == "SNIPER"
