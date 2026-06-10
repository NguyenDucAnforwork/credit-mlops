"""
Step 2 of training pipeline: sklearn preprocessing pipeline.
Mirrors the notebook exactly:
  KNNImputer → Winsorizer → SingleValueDropper → GroupPCA → RFESelector
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.feature_selection import RFE, mutual_info_classif
from sklearn.impute import KNNImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"

# Feature groups with high intra-group correlation (from notebook EDA)
OUTSTANDING_BAL_COLS = [
    "OUTSTANDING_BAL_LOAN_CURRENT", "OUTSTANDING_BAL_LOAN_3M", "OUTSTANDING_BAL_LOAN_6M",
    "OUTSTANDING_BAL_LOAN_9M", "OUTSTANDING_BAL_LOAN_12M", "OUTSTANDING_BAL_CC_3M",
    "OUTSTANDING_BAL_CC_6M", "OUTSTANDING_BAL_CC_9M", "OUTSTANDING_BAL_CC_12M",
    "OUTSTANDING_BAL_ALL_3M", "OUTSTANDING_BAL_ALL_6M", "OUTSTANDING_BAL_ALL_9M",
    "OUTSTANDING_BAL_ALL_12M", "OUTSTANDING_BAL_LOAN_3M_6M", "OUTSTANDING_BAL_LOAN_6M_9M",
    "OUTSTANDING_BAL_LOAN_9M_12M", "OUTSTANDING_BAL_LOAN_6M_12M", "OUTSTANDING_BAL_LOAN_3M_12M",
    "OUTSTANDING_BAL_CC_3M_6M", "OUTSTANDING_BAL_CC_6M_9M", "OUTSTANDING_BAL_CC_9M_12M",
    "OUTSTANDING_BAL_CC_6M_12M", "OUTSTANDING_BAL_CC_3M_12M", "OUTSTANDING_BAL_ALL_3M_6M",
    "OUTSTANDING_BAL_ALL_6M_9M", "OUTSTANDING_BAL_ALL_9M_12M", "OUTSTANDING_BAL_ALL_6M_12M",
    "OUTSTANDING_BAL_ALL_3M_12M", "OUTSTANDING_BAL_CC_CURRENT", "OUTSTANDING_BAL_ALL_CURRENT",
    "INCREASING_BAL_3M_LOAN", "INCREASING_BAL_6M_LOAN", "INCREASING_BAL_3M_CC",
    "INCREASING_BAL_6M_CC", "INCREASING_BAL_3M_ALL", "INCREASING_BAL_6M_ALL",
]

NUM_NEW_LOAN_COLS = [
    "NUM_NEW_LOAN_TAKEN_3M", "NUM_NEW_LOAN_TAKEN_6M", "NUM_NEW_LOAN_TAKEN_9M",
    "NUM_NEW_LOAN_TAKEN_12M", "NUM_NEW_LOAN_TAKEN_BANK_3M", "NUM_NEW_LOAN_TAKEN_BANK_6M",
    "NUM_NEW_LOAN_TAKEN_BANK_9M", "NUM_NEW_LOAN_TAKEN_BANK_12M",
    "NUM_NEW_LOAN_TAKEN_NON_BANK_3M", "NUM_NEW_LOAN_TAKEN_NON_BANK_6M",
    "NUM_NEW_LOAN_TAKEN_NON_BANK_9M", "NUM_NEW_LOAN_TAKEN_NON_BANK_12M",
]

ENQUIRIES_COLS = [
    "ENQUIRIES_3M", "ENQUIRIES_6M", "ENQUIRIES_9M", "ENQUIRIES_12M",
    "ENQUIRIES_FROM_BANK_3M", "ENQUIRIES_FROM_NON_BANK_3M", "ENQUIRIES_FOR_LOAN_3M",
    "ENQUIRIES_FOR_CC_3M", "ENQUIRIES_FROM_BANK_FOR_LOAN_3M", "ENQUIRIES_FROM_NON_BANK_FOR_LOAN_3M",
    "ENQUIRIES_FROM_BANK_FOR_CC_3M", "ENQUIRIES_FROM_NON_BANK_FOR_CC_3M",
    "ENQUIRIES_FROM_BANK_6M", "ENQUIRIES_FROM_NON_BANK_6M", "ENQUIRIES_FOR_LOAN_6M",
    "ENQUIRIES_FOR_CC_6M", "ENQUIRIES_FROM_BANK_FOR_LOAN_6M", "ENQUIRIES_FROM_NON_BANK_FOR_LOAN_6M",
    "ENQUIRIES_FROM_BANK_FOR_CC_6M", "ENQUIRIES_FROM_NON_BANK_FOR_CC_6M",
    "ENQUIRIES_FROM_BANK_9M", "ENQUIRIES_FROM_NON_BANK_9M", "ENQUIRIES_FOR_LOAN_9M",
    "ENQUIRIES_FOR_CC_9M", "ENQUIRIES_FROM_BANK_FOR_LOAN_9M", "ENQUIRIES_FROM_NON_BANK_FOR_LOAN_9M",
    "ENQUIRIES_FROM_BANK_FOR_CC_9M", "ENQUIRIES_FROM_NON_BANK_FOR_CC_9M",
    "ENQUIRIES_FROM_BANK_12M", "ENQUIRIES_FROM_NON_BANK_12M", "ENQUIRIES_FOR_LOAN_12M",
    "ENQUIRIES_FOR_CC_12M", "ENQUIRIES_FROM_BANK_FOR_LOAN_12M",
    "ENQUIRIES_FROM_NON_BANK_FOR_LOAN_12M", "ENQUIRIES_FROM_BANK_FOR_CC_12M",
    "ENQUIRIES_FROM_NON_BANK_FOR_CC_12M", "ENQUIRIES_3M_6M", "ENQUIRIES_6M_9M",
    "ENQUIRIES_9M_12M", "ENQUIRIES_6M_12M", "ENQUIRIES_3M_12M", "ENQUIRIES_FROM_BANK_3M_6M",
    "ENQUIRIES_FROM_BANK_6M_9M", "ENQUIRIES_FROM_BANK_9M_12M", "ENQUIRIES_FROM_BANK_6M_12M",
    "ENQUIRIES_FROM_BANK_3M_12M", "ENQUIRIES_FROM_NON_BANK_3M_6M",
    "ENQUIRIES_FROM_NON_BANK_6M_9M", "ENQUIRIES_FROM_NON_BANK_9M_12M",
    "ENQUIRIES_FROM_NON_BANK_6M_12M", "ENQUIRIES_FROM_NON_BANK_3M_12M",
]

PCA_N_COMPONENTS = {"outstanding_bal": 5, "num_new_loan": 3, "enquiries": 5}
N_FEATURES_RFE = 22


class Winsorizer(BaseEstimator, TransformerMixin):
    def __init__(self, lower: float = 0.05, upper: float = 0.95):
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None):
        df = pd.DataFrame(X)
        self.lower_bounds_ = df.quantile(self.lower)
        self.upper_bounds_ = df.quantile(self.upper)
        return self

    def transform(self, X, y=None):
        df = pd.DataFrame(X).copy()
        for col in df.columns:
            df[col] = df[col].clip(
                lower=self.lower_bounds_[col],
                upper=self.upper_bounds_[col],
            )
        return df.values


class SingleValueDropper(BaseEstimator, TransformerMixin):
    """Remove columns that have only one unique value (learned on fit data)."""

    def fit(self, X, y=None):
        df = pd.DataFrame(X)
        self.cols_to_keep_ = [c for c in df.columns if df[c].nunique() > 1]
        return self

    def transform(self, X, y=None):
        df = pd.DataFrame(X)
        keep = [c for c in self.cols_to_keep_ if c in df.columns]
        return df[keep].values

    def get_feature_names_out(self, input_features=None):
        return np.array(self.cols_to_keep_)


class GroupPCATransformer(BaseEstimator, TransformerMixin):
    """
    Apply separate PCAs to pre-defined correlated feature groups,
    then concatenate PCA components with the remaining features.
    """

    def __init__(self, feature_names: list[str]):
        self.feature_names = feature_names

    def _resolve_group(self, group_cols: list[str]) -> list[int]:
        return [i for i, n in enumerate(self.feature_names) if n in group_cols]

    def fit(self, X, y=None):
        self.pcas_: dict = {}
        self.group_indices_: dict = {}
        groups = {
            "outstanding_bal": (OUTSTANDING_BAL_COLS, PCA_N_COMPONENTS["outstanding_bal"]),
            "num_new_loan": (NUM_NEW_LOAN_COLS, PCA_N_COMPONENTS["num_new_loan"]),
            "enquiries": (ENQUIRIES_COLS, PCA_N_COMPONENTS["enquiries"]),
        }
        for name, (cols, n) in groups.items():
            idx = self._resolve_group(cols)
            if len(idx) < n:
                n = max(1, len(idx))
            if idx:
                pca = PCA(n_components=n)
                pca.fit(X[:, idx])
                self.pcas_[name] = pca
                self.group_indices_[name] = idx

        all_group_idx = set(i for idxs in self.group_indices_.values() for i in idxs)
        self.remaining_idx_ = [i for i in range(X.shape[1]) if i not in all_group_idx]
        return self

    def transform(self, X, y=None):
        parts = []
        for name, pca in self.pcas_.items():
            idx = self.group_indices_[name]
            parts.append(pca.transform(X[:, idx]))
        if self.remaining_idx_:
            parts.append(X[:, self.remaining_idx_])
        return np.hstack(parts) if parts else X


def build_pipeline(feature_names: list[str]) -> Pipeline:
    # SingleValueDropper runs AFTER GroupPCA so PCA group indices stay valid
    return Pipeline([
        ("imputer", KNNImputer(n_neighbors=20)),
        ("winsorizer", Winsorizer(lower=0.05, upper=0.95)),
        ("group_pca", GroupPCATransformer(feature_names=feature_names)),
        ("single_drop", SingleValueDropper()),
    ])


class FeaturePipeline:
    """
    Wraps the sklearn Pipeline + RFE selector so both can be saved/loaded together.
    fit() → transform() → get_feature_names()
    """

    def __init__(self, n_rfe_features: int = N_FEATURES_RFE):
        self.n_rfe_features = n_rfe_features
        self.pipeline_: Pipeline | None = None
        self.rfe_: RFE | None = None
        self.selected_features_: list[int] | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FeaturePipeline":
        from sklearn.preprocessing import StandardScaler

        feature_names = list(X.columns)
        self.pipeline_ = build_pipeline(feature_names)
        X_transformed = self.pipeline_.fit_transform(X.values)

        # Scale before RFE so LR converges reliably
        self.scaler_ = StandardScaler()
        X_scaled = self.scaler_.fit_transform(X_transformed)

        lr = LogisticRegression(
            max_iter=5000, random_state=42, class_weight="balanced", solver="saga"
        )
        n = min(self.n_rfe_features, X_scaled.shape[1])
        self.rfe_ = RFE(estimator=lr, n_features_to_select=n)
        self.rfe_.fit(X_scaled, y)
        self.selected_features_ = list(np.where(self.rfe_.support_)[0])
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        X_t = self.pipeline_.transform(X.values)
        X_scaled = self.scaler_.transform(X_t)
        return X_scaled[:, self.selected_features_]

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def n_features_out(self) -> int:
        return len(self.selected_features_) if self.selected_features_ else 0

    def save(self, path: Path = ARTIFACTS_DIR / "feature_pipeline.joblib") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: Path = ARTIFACTS_DIR / "feature_pipeline.joblib") -> "FeaturePipeline":
        """Load the artifact portably, regardless of caller cwd / sys.path.

        The pipeline classes are pickled under the bare module name ``features``
        (and historically could be ``__main__``). This loader guarantees the
        unpickling context: it ensures ``src/`` is importable and registers
        module aliases so artifacts referencing ``features``, ``src.features``,
        or ``__main__`` all resolve to this module.
        """
        import sys
        import importlib

        src_dir = str(Path(__file__).resolve().parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        this_mod = importlib.import_module("features")
        # Bare/package module names: setdefault fills them if absent.
        sys.modules.setdefault("features", this_mod)
        sys.modules.setdefault("src.features", this_mod)
        # Legacy artifacts pickled from a script reference __main__.<Class>.
        # __main__ always exists, so a module alias is a no-op; instead copy
        # this module's pipeline classes onto the live __main__ where missing.
        main_mod = sys.modules.get("__main__")
        if main_mod is not None:
            for name in dir(this_mod):
                obj = getattr(this_mod, name)
                if (isinstance(obj, type)
                        and getattr(obj, "__module__", "") == "features"
                        and not hasattr(main_mod, name)):
                    setattr(main_mod, name, obj)
        return joblib.load(path)


if __name__ == "__main__":
    # Use save_pipeline.py instead — running features.py directly saves the class
    # as __main__.FeaturePipeline which breaks joblib loading in other contexts.
    raise SystemExit("Run src/save_pipeline.py instead of features.py directly.")
