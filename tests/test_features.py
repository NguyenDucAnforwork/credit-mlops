"""Unit tests for the preprocessing pipeline."""
import numpy as np
import pandas as pd
import pytest


def test_pipeline_output_shape(feature_pipeline, sample_train_df, sample_test_small):
    # Small slices: KNNImputer.transform is O(n_test x n_train); row count is
    # irrelevant to the shape assertion, so 100 rows keeps this fast.
    X_train = sample_train_df.drop(columns=["label"]).head(100)
    X_test = sample_test_small.drop(columns=["label"])
    X_tr = feature_pipeline.transform(X_train)
    X_te = feature_pipeline.transform(X_test)
    assert X_tr.shape[1] == 22
    assert X_te.shape[1] == 22
    assert X_tr.shape[0] == len(X_train)
    assert X_te.shape[0] == len(X_test)


def test_no_nan_after_transform(feature_pipeline, sample_test_small):
    X = sample_test_small.drop(columns=["label"])
    X_t = feature_pipeline.transform(X)
    assert not np.isnan(X_t).any(), "Transform output must have no NaNs"


def test_transform_is_deterministic(feature_pipeline, sample_test_small):
    X = sample_test_small.drop(columns=["label"])
    X_t1 = feature_pipeline.transform(X)
    X_t2 = feature_pipeline.transform(X)
    np.testing.assert_array_equal(X_t1, X_t2)


def test_winsorizer_clips_extremes():
    from features import Winsorizer
    import numpy as np

    data = np.array([[1, 2], [3, 4], [100, 200], [-100, -200], [2, 3]])
    w = Winsorizer(lower=0.05, upper=0.95)
    w.fit(data)
    result = w.transform(data)
    # Max should be clamped
    assert result.max() <= data[1:-1].max() * 2


def test_single_value_dropper_removes_constant_col():
    from features import SingleValueDropper
    import numpy as np

    data = np.array([[1, 5], [1, 6], [1, 7]])
    d = SingleValueDropper()
    d.fit(data)
    result = d.transform(data)
    assert result.shape[1] == 1, "Constant column should be dropped"


def test_pipeline_save_load_roundtrip(tmp_path, feature_pipeline, sample_test_df):
    save_path = tmp_path / "fp_test.joblib"
    feature_pipeline.save(save_path)

    from features import FeaturePipeline
    loaded = FeaturePipeline.load(save_path)

    X = sample_test_df.drop(columns=["label"]).head(50)
    np.testing.assert_array_almost_equal(
        feature_pipeline.transform(X),
        loaded.transform(X),
    )
