"""Admins must be able to pick any Gemini model name the app offers, including ones with dots (gemini-3.5-flash)."""
import pytest
from pydantic import ValidationError

from backend.auth.admin_routes import AdminConfigPayload

MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash",
          "gemini-flash-lite-latest", "RL_DQN", "ML_ENSEMBLE", "XGBOOST"]


@pytest.mark.parametrize("model", MODELS)
def test_admin_accepts_every_offered_model(model):
    assert AdminConfigPayload(model_choice=model).model_choice == model


@pytest.mark.parametrize("bad", ["gemini 3.5", "gemini;drop", "x" * 65, "../etc"])
def test_admin_still_rejects_malformed_model_names(bad):
    with pytest.raises(ValidationError):
        AdminConfigPayload(model_choice=bad)
