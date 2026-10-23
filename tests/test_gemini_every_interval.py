import pytest
from backend.btc.gemini_15m_gate import _call_gemini_master_decision

def test_gemini_every_interval_forced_decision_no_pass():
    # Build a balanced synthetic dossier
    synthetic_dossier = {
        "contract": {
            "asset": "BTC",
            "ticker": "KXBTC15M-26OCT211100-00",
            "strike_price": 68000.0,
            "current_spot_price": 68005.0,
            "seconds_elapsed_in_15m_candle": 65,
            "is_outside_deadzone": True
        },
        "kalshi_orderbook": {
            "yes_bid": 0.49,
            "yes_ask": 0.51,
            "no_bid": 0.49,
            "no_ask": 0.51
        },
        "price_action_and_indicators": {
            "indicators": {
                "rsi": 52.0,
                "adx": 22.0,
                "bb_pct_b": 0.51
            }
        },
        "local_ai_models": {
            "ml_ensemble_prob_above_strike_pct": 53.5
        }
    }

    # When allow_pass is False, decision MUST be YES or NO, never PASS
    dec = _call_gemini_master_decision(synthetic_dossier, allow_pass=False)
    assert dec is not None
    assert dec["direction"] in ("YES", "NO")
    assert dec["direction"] != "PASS"
    assert dec["confidence"] >= 50.0


def test_gemini_every_interval_prompt_contains_no_pass():
    from backend.btc.gemini_15m_gate import _call_gemini_master_decision
    import unittest.mock as mock

    synthetic_dossier = {
        "contract": {
            "asset": "BTC",
            "ticker": "KXBTC15M-26OCT211100-00",
            "strike_price": 68000.0,
            "current_spot_price": 68005.0,
            "seconds_elapsed_in_15m_candle": 65,
            "is_outside_deadzone": True,
        },
        "kalshi_orderbook": {"yes_bid": 0.49, "yes_ask": 0.51, "no_bid": 0.49, "no_ask": 0.51},
        "price_action_and_indicators": {"indicators": {"rsi": 52.0, "adx": 22.0, "bb_pct_b": 0.51}},
        "local_ai_models": {"ml_ensemble_prob_above_strike_pct": 53.5},
    }

    captured_prompt = None
    def mock_post(url, json=None, timeout=None):
        nonlocal captured_prompt
        captured_prompt = json["contents"][0]["parts"][0]["text"]
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"direction": "PASS", "confidence": 70, "reason": "test"}'}]}}]
        }
        return mock_resp

    with mock.patch("requests.post", side_effect=mock_post):
        # 1. When allow_pass=False, prompt must not have "PASS" in schema or options
        res = _call_gemini_master_decision(synthetic_dossier, allow_pass=False)
        assert captured_prompt is not None
        assert '"YES" or "NO" or "PASS"' not in captured_prompt
        assert '"direction": "YES" or "NO"' in captured_prompt
        assert 'OR PASS DECISION' not in captured_prompt
        assert 'Choose PASS' not in captured_prompt
        # Even though LLM returned "PASS", parser must strictly convert to YES or NO
        assert res["direction"] in ("YES", "NO")
        assert res["direction"] != "PASS"

    with mock.patch("requests.post", side_effect=mock_post):
        # 2. When allow_pass=True, PASS is allowed and preserved
        res_pass = _call_gemini_master_decision(synthetic_dossier, allow_pass=True)
        assert res_pass["direction"] == "PASS"


def test_dual_model_debate_every_interval_no_pass():
    from backend.btc.dual_model_debate import run_dual_model_debate
    import unittest.mock as mock

    synthetic_dossier = {
        "contract": {
            "asset": "BTC",
            "ticker": "KXBTC15M-26OCT211100-00",
            "strike_price": 68000.0,
            "current_spot_price": 68005.0,
            "seconds_elapsed_in_15m_candle": 65,
        },
        "market_snapshot": {"raw_features": {}},
        "local_ai_models": {"ml_ensemble_prob_above_strike_pct": 60.0},
    }

    captured_prompt = None
    def mock_post(url, json=None, timeout=None):
        nonlocal captured_prompt
        captured_prompt = json["contents"][0]["parts"][0]["text"]
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"direction": "PASS", "confidence": 75, "reason": "chop"}'}]}}]
        }
        return mock_resp

    with mock.patch("requests.post", side_effect=mock_post):
        # When allow_pass=False
        res = run_dual_model_debate(synthetic_dossier, api_key="dummy_key", allow_pass=False)
        assert captured_prompt is not None
        assert '"YES" or "NO" or "PASS"' not in captured_prompt
        assert '"direction": "YES" or "NO"' in captured_prompt
        assert 'In tight 50/50 deadzones, PASS.' not in captured_prompt
        # Parser must convert PASS into YES/NO
        assert res["consensus_direction"] in ("YES", "NO")
        assert res["consensus_direction"] != "PASS"

    with mock.patch("requests.post", side_effect=mock_post):
        # When allow_pass=True
        res_pass = run_dual_model_debate(synthetic_dossier, api_key="dummy_key", allow_pass=True)
        assert res_pass["consensus_direction"] == "PASS"

