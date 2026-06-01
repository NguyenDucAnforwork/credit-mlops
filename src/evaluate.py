"""Evaluation metrics for binary credit-scoring models."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    auc,
    confusion_matrix,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def gini(y_true, y_prob) -> float:
    return 2 * roc_auc_score(y_true, y_prob) - 1


def ks_stat(y_true, y_prob) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return float(np.max(tpr - fpr))


def pr_auc(y_true, y_prob) -> float:
    p, r, _ = precision_recall_curve(y_true, y_prob)
    return float(auc(r, p))


def best_threshold(y_true, y_prob) -> float:
    """F1-maximising threshold."""
    p, r, thresholds = precision_recall_curve(y_true, y_prob)
    f1 = np.where((p + r) == 0, 0, 2 * p * r / (p + r))
    idx = np.argmax(f1[:-1])
    return float(thresholds[idx])


def compute_all(y_true, y_prob, threshold: float | None = None) -> dict:
    if threshold is None:
        threshold = best_threshold(y_true, y_prob)

    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    return {
        "auc": float(roc_auc_score(y_true, y_prob)),
        "gini": float(gini(y_true, y_prob)),
        "ks": float(ks_stat(y_true, y_prob)),
        "pr_auc": float(pr_auc(y_true, y_prob)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }
