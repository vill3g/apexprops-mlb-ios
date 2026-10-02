import logging

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBClassifier

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
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.LayerNorm(32),
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
        self.meta_learner = LogisticRegression(random_state=42, C=0.5)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.is_normalized = True
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
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)
        y_np = y.values if hasattr(y, 'values') else np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X_np)
        
        # Dynamic scale_pos_weight for XGBoost to prevent YES bias
        num_pos = int(np.sum(y_np == 1))
        num_neg = int(np.sum(y_np == 0))
        scale_pos = float(num_neg) / float(num_pos) if num_pos > 0 else 1.0
        self.xgb.set_params(scale_pos_weight=scale_pos)
        
        # 1. Generate Meta-Features via Out-of-Fold Cross-Validation to eliminate in-sample memorization
        from sklearn.model_selection import StratifiedKFold
        n_splits = min(5, min(num_pos, num_neg))
        meta_X = None

        if n_splits >= 2 and len(X_np) >= 20:
            skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
            oof_xgb = np.zeros(len(X_np))
            oof_rf = np.zeros(len(X_np))
            oof_dnn = np.zeros(len(X_np))

            for train_idx, val_idx in skf.split(X_np, y_np):
                X_tr, y_tr = X_np[train_idx], y_np[train_idx]
                X_val, _ = X_np[val_idx], y_np[val_idx]
                w_tr = sample_weight[train_idx] if sample_weight is not None else None

                # Fold Scaler
                fold_scaler = StandardScaler()
                X_tr_sc = fold_scaler.fit_transform(X_tr)
                X_val_sc = fold_scaler.transform(X_val)

                # Fold XGB
                f_xgb = XGBClassifier(
                    n_estimators=self.xgb.n_estimators,
                    max_depth=self.xgb.max_depth,
                    learning_rate=self.xgb.learning_rate,
                    scale_pos_weight=scale_pos,
                    objective='binary:logistic',
                    random_state=42,
                    n_jobs=-1
                )
                f_xgb.fit(X_tr, y_tr, sample_weight=w_tr)
                oof_xgb[val_idx] = f_xgb.predict_proba(X_val)[:, 1]

                # Fold RF
                f_rf = RandomForestClassifier(
                    n_estimators=self.rf.n_estimators,
                    max_depth=5,
                    random_state=42,
                    n_jobs=-1
                )
                f_rf.fit(X_tr, y_tr, sample_weight=w_tr)
                oof_rf[val_idx] = f_rf.predict_proba(X_val)[:, 1]

                # Fold DNN
                f_dnn = PyTorchDNN(input_dim=X_np.shape[1]).to(self.device)
                d_crit = nn.BCELoss()
                d_opt = optim.Adam(f_dnn.parameters(), lr=0.003)
                ds = TensorDataset(torch.FloatTensor(X_tr_sc).to(self.device), torch.FloatTensor(y_tr).unsqueeze(1).to(self.device))
                dl = DataLoader(ds, batch_size=32, shuffle=True)
                f_dnn.train()
                for _ in range(12):
                    for bx, by in dl:
                        d_opt.zero_grad()
                        loss = d_crit(f_dnn(bx), by)
                        loss.backward()
                        d_opt.step()
                f_dnn.eval()
                with torch.no_grad():
                    oof_dnn[val_idx] = f_dnn(torch.FloatTensor(X_val_sc).to(self.device)).cpu().numpy().flatten()

            meta_X = np.column_stack((oof_xgb, oof_rf, oof_dnn))

        # 2. Train Full Base Models
        self.xgb.fit(X_np, y_np, sample_weight=sample_weight)
        self.rf.fit(X_np, y_np, sample_weight=sample_weight)

        self.dnn = PyTorchLSTM(input_dim=X_np.shape[1], seq_len=5, seq_features=5).to(self.device)
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.dnn.parameters(), lr=0.003)

        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        y_tensor = torch.FloatTensor(y_np).unsqueeze(1).to(self.device)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        self.dnn.train()
        for epoch in range(15):
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = self.dnn(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        self.dnn.eval()

        # If CV was not feasible (e.g. tiny sample count), fallback to in-sample
        if meta_X is None:
            xgb_preds = self.xgb.predict_proba(X_np)[:, 1]
            rf_preds = self.rf.predict_proba(X_np)[:, 1]
            with torch.no_grad():
                dnn_preds = self.dnn(X_tensor).cpu().numpy().flatten()
            meta_X = np.column_stack((xgb_preds, rf_preds, dnn_preds))

        # 3. Train Meta-Learner with regularized C=0.5
        self.meta_learner = LogisticRegression(random_state=42, C=0.5)
        self.meta_learner.fit(meta_X, y_np, sample_weight=sample_weight)

        self.is_trained = True
        self.is_normalized = True
        logger.info("[GodTierEnsemble] Swarm successfully trained with OOF validation.")

    def predict_proba(self, X):
        if not self.is_trained or self.dnn is None:
            # Fallback
            return np.array([[0.5, 0.5]] * len(X))
            
        X_np = X.values if hasattr(X, 'values') else np.array(X)
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)
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
