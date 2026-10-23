import unittest
from backend.btc.time_phase_engine import classify_15m_time_phase

class TestTimePhaseEngine(unittest.TestCase):
    def test_phase_1_opening_breakout(self):
        # 12 minutes remaining = 720s
        res = classify_15m_time_phase(sec_left=720, spot_price=90000, strike_price=90000, asset="BTC")
        self.assertEqual(res["phase"], "OPENING_BREAKOUT")
        self.assertEqual(res["phase_num"], 1)
        self.assertFalse(res["is_pin_risk"])
        self.assertFalse(res["is_delta_locked"])
        self.assertEqual(res["recommended_focus"], "MOMENTUM_BREAKOUT")

        # Boundary at exactly 600s
        res_boundary = classify_15m_time_phase(sec_left=600, spot_price=90000, strike_price=90000, asset="BTC")
        self.assertEqual(res_boundary["phase"], "OPENING_BREAKOUT")
        self.assertEqual(res_boundary["phase_num"], 1)

    def test_phase_2_mid_consolidation(self):
        # 7 minutes remaining = 420s
        res = classify_15m_time_phase(sec_left=420, spot_price=90000, strike_price=90000, asset="BTC")
        self.assertEqual(res["phase"], "MID_CONSOLIDATION")
        self.assertEqual(res["phase_num"], 2)
        self.assertFalse(res["is_pin_risk"])
        self.assertFalse(res["is_delta_locked"])
        self.assertEqual(res["recommended_focus"], "MEAN_REVERSION_MAKER")

        # Boundary at exactly 240s
        res_boundary = classify_15m_time_phase(sec_left=240, spot_price=90000, strike_price=90000, asset="BTC")
        self.assertEqual(res_boundary["phase"], "MID_CONSOLIDATION")
        self.assertEqual(res_boundary["phase_num"], 2)

    def test_phase_3_pin_risk(self):
        # 2 minutes remaining = 120s, spot within $10 of strike (buffer is $30 for BTC)
        res = classify_15m_time_phase(sec_left=120, spot_price=90010, strike_price=90000, asset="BTC", atr=50)
        self.assertEqual(res["phase"], "EXPIRY_PIN")
        self.assertEqual(res["phase_num"], 3)
        self.assertTrue(res["is_pin_risk"])
        self.assertFalse(res["is_delta_locked"])
        self.assertEqual(res["recommended_focus"], "PIN_RISK_VETO")
        self.assertEqual(res["delta_to_strike"], 10.0)

    def test_phase_3_delta_locked(self):
        # 2 minutes remaining = 120s, spot $50 away from strike (buffer is $30 for BTC)
        res = classify_15m_time_phase(sec_left=120, spot_price=90050, strike_price=90000, asset="BTC", atr=50)
        self.assertEqual(res["phase"], "EXPIRY_PIN")
        self.assertEqual(res["phase_num"], 3)
        self.assertFalse(res["is_pin_risk"])
        self.assertTrue(res["is_delta_locked"])
        self.assertEqual(res["recommended_focus"], "DELTA_LOCK_IN")
        self.assertEqual(res["delta_to_strike"], 50.0)

    def test_phase_3_atr_scaling(self):
        # If ATR is high (e.g. $200), threshold becomes 0.35 * 200 = $70
        # Delta of $50 should now trigger pin risk veto
        res = classify_15m_time_phase(sec_left=120, spot_price=90050, strike_price=90000, asset="BTC", atr=200)
        self.assertTrue(res["is_pin_risk"])
        self.assertFalse(res["is_delta_locked"])

    def test_asset_specific_buffers(self):
        # ETH buffer is $2.50
        eth_pin = classify_15m_time_phase(sec_left=100, spot_price=2501.0, strike_price=2500.0, asset="ETH", atr=2.0)
        self.assertTrue(eth_pin["is_pin_risk"])

        eth_lock = classify_15m_time_phase(sec_left=100, spot_price=2505.0, strike_price=2500.0, asset="ETH", atr=2.0)
        self.assertTrue(eth_lock["is_delta_locked"])

    def test_zero_or_negative_inputs(self):
        # When spot or strike is unknown / zero
        res = classify_15m_time_phase(sec_left=60, spot_price=0, strike_price=0, asset="BTC")
        self.assertEqual(res["phase"], "EXPIRY_PIN")
        self.assertFalse(res["is_pin_risk"])
        self.assertFalse(res["is_delta_locked"])
        self.assertEqual(res["recommended_focus"], "EXPIRY_GENERAL")

if __name__ == "__main__":
    unittest.main()
