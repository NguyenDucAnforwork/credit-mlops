"""Unit tests for evaluation metrics."""
import numpy as np
import pytest
from evaluate import compute_all, gini, ks_stat, pr_auc, best_threshold


def _make_data(n=200, seed=0):
    rng = np.random.RandomState(seed)
    y_true = rng.randint(0, 2, n)
    y_prob = np.clip(y_true * 0.6 + rng.rand(n) * 0.4, 0, 1)
    return y_true, y_prob


def test_gini_range():
    y_true, y_prob = _make_data()
    g = gini(y_true, y_prob)
    assert -1.0 <= g <= 1.0


def test_ks_range():
    y_true, y_prob = _make_data()
    ks = ks_stat(y_true, y_prob)
    assert 0.0 <= ks <= 1.0


def test_pr_auc_range():
    y_true, y_prob = _make_data()
    pa = pr_auc(y_true, y_prob)
    assert 0.0 <= pa <= 1.0


def test_compute_all_keys():
    y_true, y_prob = _make_data()
    result = compute_all(y_true, y_prob)
    for key in ["auc", "gini", "ks", "pr_auc", "precision", "recall", "threshold", "tp", "tn", "fp", "fn"]:
        assert key in result


def test_compute_all_confusion_matrix_sum():
    y_true, y_prob = _make_data()
    r = compute_all(y_true, y_prob)
    assert r["tp"] + r["tn"] + r["fp"] + r["fn"] == len(y_true)


def test_perfect_classifier():
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    r = compute_all(y_true, y_prob)
    assert r["auc"] == pytest.approx(1.0)
