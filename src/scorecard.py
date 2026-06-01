"""
Scorecard model: WOE binning + LogisticRegression credit scoring.

Replicates the notebook (A_K_A_Code_Round04.ipynb, cells 73-92):
  - Equal-frequency binning for {NUMBER_OF_LOANS, NUM_NEW_LOAN_TAKEN_PCA_1/2,
    NUMBER_OF_RELATIONSHIP_BANK}
  - Decision-tree binning for all other features
  - GridSearchCV over C / penalty to find best LR
  - Credit score formula: score = (beta*woe + alpha/n)*factor + offset/n

Key difference from the notebook: INCREASING_BAL_3M_CC is part of the
OUTSTANDING_BAL PCA group in the MLOps pipeline, so it is excluded from the
scorecard features. We use 18 features (notebook used 19).
"""
from __future__ import annotations

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import make_scorer, roc_auc_score
from sklearn.model_selection import GridSearchCV
from sklearn.tree import DecisionTreeClassifier

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"

# 18 scorecard features after PCA (INCREASING_BAL_3M_CC excluded — it's in PCA group)
SCORECARD_NBINS: dict[str, int] = {
    "NUMBER_OF_LOANS": 5,
    "NUMBER_OF_CREDIT_CARDS": 5,
    "SHORT_TERM_COUNT_BANK": 2,
    "SHORT_TERM_COUNT_NON_BANK": 2,
    "NUMBER_OF_RELATIONSHIP_BANK": 4,
    "NUMBER_OF_RELATIONSHIP_NON_BANK": 4,
    "NUM_NEW_LOAN_TAKEN_PCA_1": 20,
    "NUM_NEW_LOAN_TAKEN_PCA_2": 20,
    "OUTSTANDING_BAL_PCA_2": 20,
    "OUTSTANDING_BAL_PCA_3": 30,
    "OUTSTANDING_BAL_PCA_5": 50,
    "NUMBER_OF_LOANS_NON_BANK": 2,
    "ENQUIRIES_PCA_4": 10,
    "ENQUIRIES_PCA_3": 10,
    "ENQUIRIES_PCA_1": 10,
    "ENQUIRIES_PCA_2": 10,
    "ENQUIRIES_PCA_5": 10,
    "NUMBER_OF_CREDIT_CARDS_BANK": 2,
}

# Features using equal-frequency binning (rest use decision-tree)
EQUAL_FREQ_COLS = {
    "NUMBER_OF_LOANS",
    "NUM_NEW_LOAN_TAKEN_PCA_1",
    "NUM_NEW_LOAN_TAKEN_PCA_2",
    "NUMBER_OF_RELATIONSHIP_BANK",
}

# Scorecard scaling constants
PDO = -50
ODDS = 1 / 4
THRES_SCORE = 600
N_FEATURES = len(SCORECARD_NBINS)  # 18


# ── Intermediate PCA feature extraction ──────────────────────────────────────

def get_pca_feature_df(X: pd.DataFrame, feature_pipeline) -> pd.DataFrame:
    """
    Apply impute → winsorize → GroupPCA (skip RFE/single_drop) and return
    a named DataFrame whose columns match SCORECARD_NBINS keys.
    """
    from features import PCA_N_COMPONENTS

    base_pipe = feature_pipeline.pipeline_
    # Steps: imputer(0), winsorizer(1), group_pca(2), single_drop(3)
    # Apply only the first three (index slice [:3] = steps 0,1,2)
    pca_out = base_pipe[:3].transform(X.values)

    group_pca = base_pipe.named_steps["group_pca"]
    feature_names = list(X.columns)

    # Build column names in the same order GroupPCATransformer outputs parts
    col_names: list[str] = []
    pca_name_map = {
        "outstanding_bal": "OUTSTANDING_BAL_PCA",
        "num_new_loan":    "NUM_NEW_LOAN_TAKEN_PCA",
        "enquiries":       "ENQUIRIES_PCA",
    }
    for grp_name, pca in group_pca.pcas_.items():
        prefix = pca_name_map[grp_name]
        col_names += [f"{prefix}_{i+1}" for i in range(pca.n_components_)]

    remaining_names = [feature_names[i] for i in group_pca.remaining_idx_]
    col_names += remaining_names

    return pd.DataFrame(pca_out, columns=col_names, index=X.index)


# ── WOE binning ───────────────────────────────────────────────────────────────

def _decision_tree_thresholds(X: np.ndarray, y: np.ndarray, n_bins: int) -> np.ndarray:
    tree = DecisionTreeClassifier(
        criterion="entropy", max_leaf_nodes=max(2, n_bins), random_state=42
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree.fit(X.reshape(-1, 1), y)
    thres = np.sort(tree.tree_.threshold[tree.tree_.feature == 0])
    return np.concatenate(([-np.inf], thres, [np.inf]))


def _equal_freq_thresholds(
    X: np.ndarray, n_bins: int, min_obs: int = 100
) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, thres = pd.qcut(X, q=n_bins, retbins=True, duplicates="drop")
    thres[0] = -np.inf
    thres[-1] = np.inf
    # Drop bins smaller than min_obs
    counts, _ = np.histogram(X, bins=thres)
    keep = np.where(counts >= min_obs)[0]
    if len(keep) < len(counts):
        thres = np.concatenate(([-np.inf], thres[keep + 1], [np.inf]))
        thres = np.unique(thres)
    return thres


def _woe_from_thresholds(
    col: np.ndarray, y: np.ndarray, thres: np.ndarray
) -> tuple[pd.DataFrame, np.ndarray]:
    bins = pd.cut(col, bins=thres, labels=False, include_lowest=True)
    df = pd.DataFrame({"bin": bins, "y": y})
    agg = df.groupby("bin")["y"].agg(["size", "sum"]).rename(
        columns={"size": "#Obs", "sum": "#Bad"}
    )
    agg["#Good"] = agg["#Obs"] - agg["#Bad"]
    agg["#Bad"] = agg["#Bad"].replace(0, 1)  # avoid log(0)
    total_good = agg["#Good"].sum() or 1
    total_bad = agg["#Bad"].sum() or 1
    agg["%Good"] = agg["#Good"] / total_good
    agg["%Bad"] = agg["#Bad"] / total_bad
    agg["WOE"] = np.log(agg["%Good"] / agg["%Bad"]).replace(
        {np.inf: 0, -np.inf: 0}
    )
    agg["IV"] = (agg["%Good"] - agg["%Bad"]) * agg["WOE"]
    return agg, thres


class WOEBinner:
    """Learns and applies WOE encoding for one feature column."""

    def __init__(self, n_bins: int, equal_freq: bool = False):
        self.n_bins = n_bins
        self.equal_freq = equal_freq
        self.thres_: np.ndarray | None = None
        self.woe_table_: pd.DataFrame | None = None
        self.iv_: float = 0.0

    def fit(self, col: np.ndarray, y: np.ndarray) -> "WOEBinner":
        col = col.astype(float)
        valid = ~np.isnan(col)
        col_v, y_v = col[valid], y[valid]
        if self.equal_freq:
            thres = _equal_freq_thresholds(col_v, self.n_bins)
        else:
            thres = _decision_tree_thresholds(col_v, y_v, self.n_bins)
        self.woe_table_, self.thres_ = _woe_from_thresholds(col_v, y_v, thres)
        self.iv_ = float(self.woe_table_["IV"].sum())
        return self

    def transform(self, col: np.ndarray) -> np.ndarray:
        col = col.astype(float)
        bins = pd.cut(col, bins=self.thres_, labels=False, include_lowest=True)
        woe_map = self.woe_table_["WOE"].to_dict()
        return np.array([woe_map.get(b, 0.0) for b in bins], dtype=float)


# ── Credit score formula ──────────────────────────────────────────────────────

def _credit_score_formula(
    beta: float, alpha: float, woe: float,
    n: int = N_FEATURES, pdo: float = PDO,
    odds: float = ODDS, thres_score: float = THRES_SCORE,
) -> float:
    factor = pdo / np.log(2)
    offset = thres_score - factor * np.log(odds)
    return float((beta * woe + alpha / n) * factor + offset / n)


# ── ScorecardModel ────────────────────────────────────────────────────────────

class ScorecardModel:
    """
    End-to-end scorecard model.  Accepts raw DataFrame (122 features),
    applies the FeaturePipeline's base steps (impute/winsorise/PCA),
    WOE-encodes 18 selected features, then fits LogisticRegression.

    Implements predict_proba() for compatibility with the existing API.
    Also exposes predict_credit_score() for the WOE-based score.
    """

    def __init__(self) -> None:
        self.binners_: dict[str, WOEBinner] = {}
        self.lr_: LogisticRegression | None = None
        self.feature_pipeline_ = None  # FeaturePipeline instance
        self.iv_table_: pd.DataFrame | None = None

    # ── Fit ──────────────────────────────────────────────────────────────────

    def fit(self, X_raw: pd.DataFrame, y: np.ndarray, feature_pipeline) -> "ScorecardModel":
        self.feature_pipeline_ = feature_pipeline

        df = get_pca_feature_df(X_raw, feature_pipeline)
        df["__y__"] = y

        # Fit WOE binners
        available = [c for c in SCORECARD_NBINS if c in df.columns]
        print(f"[scorecard] fitting WOE on {len(available)} features")
        for col in available:
            binner = WOEBinner(
                n_bins=SCORECARD_NBINS[col],
                equal_freq=(col in EQUAL_FREQ_COLS),
            )
            binner.fit(df[col].values, df["__y__"].values)
            self.binners_[col] = binner

        # Build IV table
        self.iv_table_ = pd.DataFrame(
            {"feature": list(self.binners_), "IV": [b.iv_ for b in self.binners_.values()]}
        ).sort_values("IV", ascending=False)

        # WOE-encode training data
        X_woe = self._woe_encode(df)

        # GridSearchCV
        def gini_scorer(y_true, y_prob):
            return 2 * roc_auc_score(y_true, y_prob) - 1

        scorer = make_scorer(gini_scorer, needs_proba=True)
        param_grid = {
            "C": [0.01, 0.1, 1, 10],
            "penalty": ["l1", "l2"],
            "solver": ["saga"],
        }
        gs = GridSearchCV(
            LogisticRegression(max_iter=1000),
            param_grid, cv=5, scoring=scorer, n_jobs=-1,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gs.fit(X_woe, y)

        self.lr_ = gs.best_estimator_
        print(f"[scorecard] best params: {gs.best_params_}")
        return self

    # ── Predict ──────────────────────────────────────────────────────────────

    def _woe_encode(self, df: pd.DataFrame) -> np.ndarray:
        cols = list(self.binners_)
        return np.column_stack([
            self.binners_[c].transform(df[c].values) for c in cols
        ])

    def _get_df(self, X_raw) -> pd.DataFrame:
        if isinstance(X_raw, pd.DataFrame):
            return get_pca_feature_df(X_raw, self.feature_pipeline_)
        return get_pca_feature_df(pd.DataFrame([X_raw]), self.feature_pipeline_)

    def predict_proba(self, X_raw) -> np.ndarray:
        df = self._get_df(X_raw)
        X_woe = self._woe_encode(df)
        return self.lr_.predict_proba(X_woe)[:, 1]

    def predict_credit_score(self, X_raw) -> np.ndarray:
        """Return per-row WOE-based credit scores (typically 300-850 range)."""
        df = self._get_df(X_raw)
        betas = dict(zip(list(self.binners_), self.lr_.coef_[0]))
        alpha = float(self.lr_.intercept_[0])
        n = len(self.binners_)

        scores = np.zeros(len(df))
        for col, binner in self.binners_.items():
            woe_vals = binner.transform(df[col].values)
            scores += np.array([
                _credit_score_formula(betas[col], alpha, w, n=n) for w in woe_vals
            ])
        return scores

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, path: Path = ARTIFACTS_DIR / "scorecard_model.joblib") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: Path = ARTIFACTS_DIR / "scorecard_model.joblib") -> "ScorecardModel":
        return joblib.load(path)
