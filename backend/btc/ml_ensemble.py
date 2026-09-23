import os
import time
import math
import logging
import numpy as np
import pandas as pd

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import optuna

logger = logging.getLogger(__name__)

class PyTorchLSTM(nn.Module):
    def __init__(self, input_dim, seq_len=5, seq_features=5):
        super(PyTorchLSTM, self).__init__()
        self.seq_len = seq_len
        self.seq_features = seq_features
        # We split the tabular input: 
        # Flat features: input_dim - (seq_len * seq_features)
        self.flat_dim = input_dim - (seq_len * seq_features)
        
        self.lstm = nn.LSTM(input_size=seq_features, hidden_size=32, num_layers=1, batch_first=True)
        
        # Dense branch for the flat tabular features
        self.tabular_fc = nn.Sequential(
            nn.Linear(self.flat_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Merge layer
        self.fc_merged = nn.Sequential(
            nn.Linear(32 + 64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        # x is shape (Batch, input_dim)
        x_flat = x[:, :self.flat_dim]
        x_seq_flat = x[:, self.flat_dim:]
        
        # Reshape sequence: (Batch, seq_len, seq_features)
        x_seq = x_seq_flat.view(-1, self.seq_len, self.seq_features)
        
        lstm_out, (hn, cn) = self.lstm(x_seq)
        # Get the last timestep's output
        lstm_feat = lstm_out[:, -1, :]  # shape: (Batch, 32)
        
        tab_feat = self.tabular_fc(x_flat)
        
        merged = torch.cat((tab_feat, lstm_feat), dim=1)
        return self.fc_merged(merged)

class PyTorchDNN(nn.Module):
    def __init__(self, input_dim):
        super(PyTorchDNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        return self.net(x)

class GodTierEnsemble:
    """
    Advanced Ensemble Swarm combining:
    1. PyTorch Deep Neural Network
    2. XGBoost
    3. Random Forest
    Meta-Learner: Logistic Regression strictly forcing UP/DOWN
    """
    def __init__(self, xgb_estimators=150, xgb_max_depth=4, xgb_lr=0.05, rf_estimators=150):
        self.xgb = XGBClassifier(
            n_estimators=xgb_estimators,
            max_depth=xgb_max_depth,
            learning_rate=xgb_lr,
            objective='binary:logistic',
            random_state=42,
            n_jobs=-1
        )
        self.rf = RandomForestClassifier(
            n_estimators=rf_estimators,
            max_depth=5,
            random_state=42,
            n_jobs=-1
        )
        self.dnn = None
        self.meta_learner = LogisticRegression(random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def update_params(self, class_weight="balanced", reg_c=0.7, xgb_estimators=None, xgb_max_depth=None, xgb_lr=None):
        """Allow live hyperparameter updates from config"""
        self.meta_learner.set_params(C=reg_c, class_weight=class_weight)
        
        if xgb_estimators is not None:
            self.xgb.set_params(n_estimators=xgb_estimators)
        if xgb_max_depth is not None:
            self.xgb.set_params(max_depth=xgb_max_depth)
        if xgb_lr is not None:
            self.xgb.set_params(learning_rate=xgb_lr)
        
    def fit(self, X, y, sample_weight=None):
        if len(X) < 10 or len(np.unique(y)) < 2:
            logger.warning("[GodTierEnsemble] Not enough data or classes to train.")
            return

        X_np = X.values if hasattr(X, 'values') else np.array(X)
        y_np = y.values if hasattr(y, 'values') else np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X_np)
        
        # Dynamic scale_pos_weight for XGBoost to prevent YES bias
        num_pos = np.sum(y_np == 1)
        num_neg = np.sum(y_np == 0)
        scale_pos = float(num_neg) / float(num_pos) if num_pos > 0 else 1.0
        self.xgb.set_params(scale_pos_weight=scale_pos)
        
        # 1. Train XGBoost
        self.xgb.fit(X_np, y_np, sample_weight=sample_weight)
        
        # 2. Train Random Forest
        self.rf.fit(X_np, y_np, sample_weight=sample_weight)
        
        # 3. Train PyTorch DNN
        self.dnn = PyTorchDNN(input_dim=X_np.shape[1]).to(self.device)
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.dnn.parameters(), lr=0.005)
        
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        y_tensor = torch.FloatTensor(y_np).unsqueeze(1).to(self.device)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        self.dnn.train()
        for epoch in range(15): # Fast training for 15m intervals
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = self.dnn(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
        self.dnn.eval()
        
        # 4. Generate Meta-Features
        xgb_preds = self.xgb.predict_proba(X_np)[:, 1]
        rf_preds = self.rf.predict_proba(X_np)[:, 1]
        
        with torch.no_grad():
            dnn_preds = self.dnn(X_tensor).cpu().numpy().flatten()
            
        meta_X = np.column_stack((xgb_preds, rf_preds, dnn_preds))
        
        # 5. Train Meta-Learner
        self.meta_learner.fit(meta_X, y_np, sample_weight=sample_weight)
        
        self.is_trained = True
        logger.info("[GodTierEnsemble] Swarm successfully trained.")

    def predict_proba(self, X):
        if not self.is_trained:
            # Fallback
            return np.array([[0.5, 0.5]] * len(X))
            
        X_np = X.values if hasattr(X, 'values') else np.array(X)
        X_scaled = self.scaler.transform(X_np)
        
        xgb_preds = self.xgb.predict_proba(X_np)[:, 1]
        rf_preds = self.rf.predict_proba(X_np)[:, 1]
        
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_scaled).to(self.device)
            dnn_preds = self.dnn(X_tensor).cpu().numpy().flatten()
            
        meta_X = np.column_stack((xgb_preds, rf_preds, dnn_preds))
        meta_preds = self.meta_learner.predict_proba(meta_X)
        
        return meta_preds

    def predict_proba_calibrated(self, X):
        preds = self.predict_proba(X)
        raw_p = preds[:, 1] if len(preds.shape) > 1 else preds
        return raw_p

    def fit_calibration(self, X_holdout, y_holdout):
        # Meta-learner (LogisticRegression) is already natively calibrated.
        # Secondary Platt scaling on small temporal holdouts causes severe directional bias.
        self.calibrator = None
        return
