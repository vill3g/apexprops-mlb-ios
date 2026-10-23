"""
ShadowTrader Native Sports AI Engine.
Provides in-process sports simulations, sharp devigging, EV/Kelly calculations,
and counterfactual factor explanations.
"""

from backend.sports_engine.native_client import (
    NativeSportsClient,
    get_native_sports_client
)
from backend.sports_engine.math.devig import (
    american_to_decimal,
    decimal_to_american,
    american_to_implied,
    calculate_ev,
    calculate_kelly_criterion,
    multiplicative_devig,
    power_devig,
    shin_devig
)
from backend.sports_engine.math.calibrator import (
    two_way_devig,
    three_way_devig,
    calibrate_probability,
    to_percentage
)
from backend.sports_engine.explainer import generate_pick_explanation
from backend.sports_engine.master_capper import MasterSportsCapper
from backend.sports_engine.situational import SituationalEngine
from backend.sports_engine.h2h_matrix import HeadToHeadEngine

__all__ = [
    "NativeSportsClient",
    "get_native_sports_client",
    "MasterSportsCapper",
    "SituationalEngine",
    "HeadToHeadEngine",
    "american_to_decimal",
    "decimal_to_american",
    "american_to_implied",
    "calculate_ev",
    "calculate_kelly_criterion",
    "multiplicative_devig",
    "power_devig",
    "shin_devig",
    "two_way_devig",
    "three_way_devig",
    "calibrate_probability",
    "to_percentage",
    "generate_pick_explanation",
]
