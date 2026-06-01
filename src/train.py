"""
Step 3 of training pipeline: train models and log everything to MLflow.

Run 1 → Logistic Regression (baseline)
Run 2 → XGBoost (challenger / champion)
Run 3 → Scorecard (WOE + LogisticRegression)
"""
from __future__ import annotations

import os
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import mlflow.xgboost
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from evaluate import compute_all
from features import FeaturePipeline
from scorecard import ScorecardModel

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
EXPERIMENT_NAME = "credit_scoring"


def _setup_mlflow() -> None:
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment(EXPERIMENT_NAME)


def _load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, FeaturePipeline]:
    train_df = pd.read_csv(PROCESSED_DIR / "train_data.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "test_data.csv")

    X_train_raw = train_df.drop(columns=["label"])
    y_train = train_df["label"].values
    X_test_raw = test_df.drop(columns=["label"])
    y_test = test_df["label"].values

    fp = FeaturePipeline.load()
    X_train = fp.transform(X_train_raw)
    X_test = fp.transform(X_test_raw)
    return X_train, y_train, X_test, y_test, fp


def _log_common(
    fp: FeaturePipeline,
    data_version: str,
    metrics_train: dict,
    metrics_test: dict,
) -> None:
    mlflow.log_param("n_features", fp.n_features_out())
    mlflow.log_param("data_version", data_version)
    mlflow.log_param("threshold", metrics_test["threshold"])

    for k, v in metrics_train.items():
        mlflow.log_metric(f"train_{k}", v)
    for k, v in metrics_test.items():
        mlflow.log_metric(f"test_{k}", v)

    # Log feature pipeline artifact
    fp_path = ARTIFACTS_DIR / "feature_pipeline.joblib"
    mlflow.log_artifact(str(fp_path), artifact_path="pipeline")


def train_logistic_regression(data_version: str) -> str:
    _setup_mlflow()
    X_train, y_train, X_test, y_test, fp = _load_data()

    # SMOTE for class imbalance
    smote = SMOTE(random_state=42)
    X_res, y_res = smote.fit_resample(X_train, y_train)

    scaler = StandardScaler()
    X_res_scaled = scaler.fit_transform(X_res)
    X_test_scaled = scaler.transform(X_test)

    params = {
        "model_type": "logistic_regression",
        "C": 0.01,
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 5000,
        "smote": True,
    }
    model = LogisticRegression(
        C=params["C"], solver=params["solver"],
        class_weight=params["class_weight"], max_iter=params["max_iter"], random_state=42,
    )
    model.fit(X_res_scaled, y_res)

    y_prob_train = model.predict_proba(X_res_scaled)[:, 1]
    y_prob_test = model.predict_proba(X_test_scaled)[:, 1]
    metrics_train = compute_all(y_res, y_prob_train)
    metrics_test = compute_all(y_test, y_prob_test)

    with mlflow.start_run(run_name="logistic_regression_baseline") as run:
        mlflow.log_params(params)
        _log_common(fp, data_version, metrics_train, metrics_test)

        # Save scaler alongside model
        scaler_path = ARTIFACTS_DIR / "lr_scaler.joblib"
        joblib.dump(scaler, scaler_path)
        mlflow.log_artifact(str(scaler_path), artifact_path="pipeline")

        model_info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name="credit_score_model",
            input_example=X_test_scaled[:1],
        )
        run_id = run.info.run_id

    print(f"[train] LR  AUC={metrics_test['auc']:.4f}  Gini={metrics_test['gini']:.4f}  run={run_id}")
    return run_id


def train_xgboost(data_version: str) -> str:
    _setup_mlflow()
    X_train, y_train, X_test, y_test, fp = _load_data()

    scale_pos_weight = int((y_train == 0).sum() / (y_train == 1).sum())
    params = {
        "model_type": "xgboost",
        "n_estimators": 150,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 2,
        "scale_pos_weight": scale_pos_weight,
        "eval_metric": "auc",
        "random_state": 42,
    }
    model = XGBClassifier(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        learning_rate=params["learning_rate"],
        subsample=params["subsample"],
        colsample_bytree=params["colsample_bytree"],
        min_child_weight=params["min_child_weight"],
        scale_pos_weight=params["scale_pos_weight"],
        eval_metric=params["eval_metric"],
        random_state=params["random_state"],
        verbosity=0,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]
    metrics_train = compute_all(y_train, y_prob_train)
    metrics_test = compute_all(y_test, y_prob_test)

    with mlflow.start_run(run_name="xgboost_challenger") as run:
        mlflow.log_params(params)
        _log_common(fp, data_version, metrics_train, metrics_test)
        model_info = mlflow.xgboost.log_model(
            model,
            name="model",
            registered_model_name="credit_score_model",
            input_example=X_test[:1],
        )
        run_id = run.info.run_id

    print(f"[train] XGB AUC={metrics_test['auc']:.4f}  Gini={metrics_test['gini']:.4f}  run={run_id}")
    return run_id


def train_scorecard(data_version: str) -> str:
    _setup_mlflow()
    train_df = pd.read_csv(PROCESSED_DIR / "train_data.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "test_data.csv")
    X_train_raw = train_df.drop(columns=["label"])
    y_train = train_df["label"].values
    X_test_raw = test_df.drop(columns=["label"])
    y_test = test_df["label"].values

    fp = FeaturePipeline.load()

    model = ScorecardModel()
    model.fit(X_train_raw, y_train, fp)

    y_prob_train = model.predict_proba(X_train_raw)
    y_prob_test = model.predict_proba(X_test_raw)
    metrics_train = compute_all(y_train, y_prob_train)
    metrics_test = compute_all(y_test, y_prob_test)

    # Save scorecard artifact for fallback / API reference
    sc_path = ARTIFACTS_DIR / "scorecard_model.joblib"
    model.save(sc_path)

    params = {
        "model_type": "scorecard_woe_lr",
        "n_scorecard_features": len(model.binners_),
        "best_C": model.lr_.C,
        "best_penalty": model.lr_.penalty,
        "pdo": -50,
        "thres_score": 600,
    }

    with mlflow.start_run(run_name="scorecard_woe_lr") as run:
        mlflow.log_params(params)
        mlflow.log_param("data_version", data_version)
        for k, v in metrics_train.items():
            mlflow.log_metric(f"train_{k}", v)
        for k, v in metrics_test.items():
            mlflow.log_metric(f"test_{k}", v)

        # Log IV table as artifact
        iv_path = ARTIFACTS_DIR / "scorecard_iv_table.csv"
        model.iv_table_.to_csv(iv_path, index=False)
        mlflow.log_artifact(str(iv_path), artifact_path="scorecard")

        fp_path = ARTIFACTS_DIR / "feature_pipeline.joblib"
        mlflow.log_artifact(str(fp_path), artifact_path="pipeline")
        mlflow.log_artifact(str(sc_path), artifact_path="scorecard")

        model_info = mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name="credit_score_model",
            input_example=None,
        )
        run_id = run.info.run_id

    print(f"[train] SC  AUC={metrics_test['auc']:.4f}  Gini={metrics_test['gini']:.4f}  run={run_id}")
    return run_id


def run(data_version: str) -> tuple[str, str, str]:
    lr_run_id = train_logistic_regression(data_version)
    xgb_run_id = train_xgboost(data_version)
    sc_run_id = train_scorecard(data_version)
    return lr_run_id, xgb_run_id, sc_run_id
