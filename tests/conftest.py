"""Shared fixtures for all tests."""
import sys
from pathlib import Path

# Make src/ and api/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

import os
os.environ.setdefault("MLFLOW_TRACKING_URI", "http://localhost:5000")
os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "test")
os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("REDIS_URL", "")

import numpy as np
import pandas as pd
import pytest


PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"


@pytest.fixture(scope="session")
def sample_train_df():
    return pd.read_csv(PROCESSED_DIR / "train_data.csv")


@pytest.fixture(scope="session")
def sample_test_df():
    return pd.read_csv(PROCESSED_DIR / "test_data.csv")


@pytest.fixture(scope="session")
def sample_test_small(sample_test_df):
    """Small slice for transform-heavy tests. KNNImputer.transform is
    O(n_test x n_train), so a small n_test keeps assertions cheap (~2s vs ~77s)."""
    return sample_test_df.head(100).reset_index(drop=True)


@pytest.fixture(scope="session")
def feature_pipeline():
    from features import FeaturePipeline
    artifact = ARTIFACTS_DIR / "feature_pipeline.joblib"
    if not artifact.exists():
        pytest.skip(f"{artifact} missing — run `python src/save_pipeline.py` to create it")
    # Genuine load errors must FAIL the suite, not silently re-fit a different
    # pipeline (which would validate an artifact production never serves).
    return FeaturePipeline.load(artifact)


@pytest.fixture
def valid_predict_payload():
    """A minimal valid payload with all fields set to reasonable values."""
    return {
        "NUMBER_OF_LOANS": 3,
        "NUMBER_OF_CREDIT_CARDS": 2,
        "ENQUIRIES_3M": 5,
        "ENQUIRIES_6M": 7,
        "OUTSTANDING_BAL_LOAN_CURRENT": 1000000,
        "OUTSTANDING_BAL_ALL_CURRENT": 1000200,
        "NUM_NEW_LOAN_TAKEN_3M": 1,
        "NUM_NEW_LOAN_TAKEN_6M": 2,
        "NUMBER_OF_RELATIONSHIP_BANK": 3,
        "CREDIT_CARD_NUMBER_OF_LATE_PAYMENT": 0,
    }
