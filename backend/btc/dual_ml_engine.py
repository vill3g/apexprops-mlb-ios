import os
import json
import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.btc.ml_engine import MLEngine

logger = logging.getLogger(__name__)

class DualMLEngine:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.day_engine = MLEngine(data_dir)
        self.night_engine = MLEngine(data_dir)
        self._lock = threading.Lock()
        
    def _is_night_time(self):
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        return 0 <= ny_time.hour < 7

    @property
    def is_trained(self):
        # We consider the dual engine trained if either day or night engine is trained
        return self.day_engine.is_trained or self.night_engine.is_trained

    def train(self, force=False):
        # We need to pass the filter to MLEngine
        with self._lock:
            self.day_engine.train(force=force, time_filter="day")
            self.night_engine.train(force=force, time_filter="night")

    def self_train_on_historical_market(self, df_ind):
        with self._lock:
            if not self.day_engine.is_trained:
                self.day_engine.self_train_on_historical_market(df_ind, time_filter="day")
            if not self.night_engine.is_trained:
                self.night_engine.self_train_on_historical_market(df_ind, time_filter="night")

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
