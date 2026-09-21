import os
import json
import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.btc.ml_engine import MLEngine

logger = logging.getLogger(__name__)

class DualMLEngine:
    def __init__(self, data_dir, trading_style="SNIPER", asset="BTC"):
        self.data_dir = data_dir
        self.trading_style = trading_style
        self.asset = asset
        self.day_engine = MLEngine(data_dir, trading_style=trading_style, asset=asset)
        self.night_engine = MLEngine(data_dir, trading_style=trading_style, asset=asset)
        self._lock = threading.Lock()
        
    def _is_night_time(self):
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        return 0 <= ny_time.hour < 7

    @property
    def is_trained(self):
        if not getattr(self, "_auto_train_attempted", False):
            return False
        if self._is_night_time():
            return self.night_engine.is_trained or self.day_engine.is_trained
        return self.day_engine.is_trained

    @property
    def feature_keys(self):
        return self.day_engine.feature_keys

    @property
    def last_train_sample_count(self):
        if self._is_night_time() and self.night_engine.is_trained:
            return self.night_engine.last_train_sample_count
        return self.day_engine.last_train_sample_count

    def get_ml_confidence_weight(self, base_weight: float, full_sample_threshold: int = 300) -> float:
        if self._is_night_time() and self.night_engine.is_trained:
            return self.night_engine.get_ml_confidence_weight(base_weight, full_sample_threshold)
        return self.day_engine.get_ml_confidence_weight(base_weight, full_sample_threshold)

    def train(self, force=False):
        # We need to pass the filter to MLEngine
        with self._lock:
            self.day_engine.train(force=force, time_filter="day")
            self.night_engine.train(force=force, time_filter="night")

    def self_train_on_historical_market(self, df_ind):
        with self._lock:
            self._auto_train_attempted = True
            n_day = 0
            n_night = 0
            if not self.day_engine.is_trained:
                n_day = self.day_engine.self_train_on_historical_market(df_ind, time_filter="day")
            if not self.night_engine.is_trained:
                n_night = self.night_engine.self_train_on_historical_market(df_ind, time_filter="night")
            return (n_day or 0) + (n_night or 0)


    def predict_with_reasoning(self, raw_features):
        with self._lock:
            if self._is_night_time():
                if self.night_engine.is_trained:
                    return self.night_engine.predict_with_reasoning(raw_features)
                else:
                    return self.day_engine.predict_with_reasoning(raw_features)
            else:
                return self.day_engine.predict_with_reasoning(raw_features)

    def predict_probability(self, raw_features):
        with self._lock:
            if self._is_night_time():
                if self.night_engine.is_trained:
                    return self.night_engine.predict_probability(raw_features)
                else:
                    logger.warning("[DualMLEngine] Night model not trained, falling back to day model.")
                    return self.day_engine.predict_probability(raw_features)
            else:
                return self.day_engine.predict_probability(raw_features)
                
    def apply_settings(self, settings: dict):
        self.day_engine.apply_settings(settings)
        self.night_engine.apply_settings(settings)
