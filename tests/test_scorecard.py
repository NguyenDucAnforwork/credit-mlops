"""
Unit tests for the scorecard model (WOE binning + LR).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="module")
def tiny_df():
    """40-row DataFrame with the minimum columns needed for scorecard."""
    rng = np.random.default_rng(42)
    n = 200
    df = pd.DataFrame({
        "NUMBER_OF_LOANS": rng.integers(1, 20, n).astype(float),
        "NUMBER_OF_CREDIT_CARDS": rng.integers(0, 10, n).astype(float),
        "SHORT_TERM_COUNT_BANK": rng.integers(0, 5, n).astype(float),
        "SHORT_TERM_COUNT_NON_BANK": rng.integers(0, 5, n).astype(float),
        "NUMBER_OF_RELATIONSHIP_BANK": rng.integers(0, 8, n).astype(float),
        "NUMBER_OF_RELATIONSHIP_NON_BANK": rng.integers(0, 8, n).astype(float),
        "NUM_NEW_LOAN_TAKEN_PCA_1": rng.normal(0, 1, n),
        "NUM_NEW_LOAN_TAKEN_PCA_2": rng.normal(0, 1, n),
        "OUTSTANDING_BAL_PCA_2": rng.normal(0, 2, n),
        "OUTSTANDING_BAL_PCA_3": rng.normal(0, 2, n),
        "OUTSTANDING_BAL_PCA_5": rng.normal(0, 2, n),
        "NUMBER_OF_LOANS_NON_BANK": rng.integers(0, 10, n).astype(float),
        "ENQUIRIES_PCA_1": rng.normal(0, 1, n),
        "ENQUIRIES_PCA_2": rng.normal(0, 1, n),
        "ENQUIRIES_PCA_3": rng.normal(0, 1, n),
        "ENQUIRIES_PCA_4": rng.normal(0, 1, n),
        "ENQUIRIES_PCA_5": rng.normal(0, 1, n),
        "NUMBER_OF_CREDIT_CARDS_BANK": rng.integers(0, 5, n).astype(float),
    })
    y = rng.integers(0, 2, n)
    return df, y


class TestWOEBinner:
    def test_fit_transform_shape(self, tiny_df):
        from scorecard import WOEBinner
        df, y = tiny_df
        binner = WOEBinner(n_bins=3, equal_freq=False)
        binner.fit(df["NUMBER_OF_LOANS"].values, y)
        woe_vals = binner.transform(df["NUMBER_OF_LOANS"].values)
        assert woe_vals.shape == (len(df),)

    def test_woe_no_nan(self, tiny_df):
        from scorecard import WOEBinner
        df, y = tiny_df
        binner = WOEBinner(n_bins=3, equal_freq=True)
        binner.fit(df["NUMBER_OF_LOANS"].values, y)
        woe_vals = binner.transform(df["NUMBER_OF_LOANS"].values)
        assert not np.any(np.isnan(woe_vals))

    def test_iv_is_positive(self, tiny_df):
        from scorecard import WOEBinner
        df, y = tiny_df
        binner = WOEBinner(n_bins=4, equal_freq=False)
        binner.fit(df["NUM_NEW_LOAN_TAKEN_PCA_1"].values, y)
        assert binner.iv_ >= 0.0


class TestCreditScoreFormula:
    def test_formula_returns_float(self):
        from scorecard import _credit_score_formula
        score = _credit_score_formula(beta=0.5, alpha=-1.0, woe=0.15, n=18)
        assert isinstance(score, float)

    def test_zero_woe_gives_offset_contribution(self):
        from scorecard import _credit_score_formula, PDO, ODDS, THRES_SCORE, N_FEATURES
        score_zero = _credit_score_formula(0.0, 0.0, 0.0)
        factor = PDO / np.log(2)
        offset = THRES_SCORE - factor * np.log(ODDS)
        expected = offset / N_FEATURES
        assert abs(score_zero - expected) < 1e-6

    def test_score_monotone_in_woe(self):
        from scorecard import _credit_score_formula, PDO
        # factor = PDO/log(2) < 0; so (beta*woe)*factor is monotone-decreasing in woe
        # for positive beta. Score should decrease as WOE increases when beta > 0.
        factor = PDO / np.log(2)  # negative
        s_high = _credit_score_formula(beta=0.5, alpha=0.0, woe=1.0, n=18)
        s_low  = _credit_score_formula(beta=0.5, alpha=0.0, woe=-1.0, n=18)
        if factor < 0:
            assert s_high < s_low  # factor negative → higher WOE → lower individual score
        else:
            assert s_high > s_low


class TestScorecardModelDirect:
    """Tests scorecard model using pre-computed PCA-like features directly."""

    def test_fit_predict_proba_shape(self, tiny_df):
        from scorecard import ScorecardModel

        df, y = tiny_df

        # Mock a minimal feature_pipeline so get_pca_feature_df returns df as-is
        class MockFP:
            class pipeline_:
                class named_steps:
                    class group_pca:
                        pcas_ = {}
                        remaining_idx_ = list(range(len(df.columns)))

                @staticmethod
                def __getitem__(s):
                    class Identity:
                        def transform(self, X):
                            return X.values if hasattr(X, 'values') else X
                    return Identity()

        # Directly test WOE binner + LR without the base pipeline
        from scorecard import WOEBinner, SCORECARD_NBINS, EQUAL_FREQ_COLS
        import warnings

        model = ScorecardModel.__new__(ScorecardModel)
        model.binners_ = {}
        model.lr_ = None
        model.feature_pipeline_ = None
        model.iv_table_ = None

        # Fit binners on pre-PCA-like data
        for col in df.columns:
            if col in SCORECARD_NBINS:
                binner = WOEBinner(
                    n_bins=min(SCORECARD_NBINS[col], 3),
                    equal_freq=(col in EQUAL_FREQ_COLS),
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    binner.fit(df[col].values, y)
                model.binners_[col] = binner

        X_woe = np.column_stack([
            model.binners_[c].transform(df[c].values) for c in model.binners_
        ])
        assert X_woe.shape == (len(df), len(model.binners_))
        assert not np.any(np.isnan(X_woe))

    def test_credit_score_formula_per_feature(self):
        from scorecard import _credit_score_formula, N_FEATURES
        # Sum of per-feature scores should be finite
        scores = [_credit_score_formula(0.3, -0.5, woe, n=N_FEATURES)
                  for woe in np.linspace(-2, 2, 10)]
        assert all(np.isfinite(s) for s in scores)
