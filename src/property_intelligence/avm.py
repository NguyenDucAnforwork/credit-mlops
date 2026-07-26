from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_log_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


NUMERIC_FEATURES = [
    "area_m2",
    "floor_count",
    "frontage_width",
    "house_depth",
    "road_width",
    "bedroom_count",
    "bathroom_count",
    "published_month",
    "published_quarter",
]

CATEGORICAL_FEATURES = [
    "province",
    "district",
    "ward",
    "property_type",
    "house_direction",
    "balcony_direction",
]


@dataclass(frozen=True)
class AvmMetrics:
    model_name: str
    split_name: str
    rows: int
    mae_vnd: float
    median_absolute_error_vnd: float
    mdape: float
    rmsle: float
    r2: float
    within_10pct: float
    within_20pct: float


class PricePerM2Model(Protocol):
    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        ...


@dataclass
class TabularHgbQuantileArtifact:
    point_model: Pipeline
    lower_model: Pipeline
    upper_model: Pipeline
    metadata: dict

    def predict_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        features = _ensure_feature_columns(frame)
        point_log_ppm = self.point_model.predict(features)
        lower_log_ppm = self.lower_model.predict(features)
        upper_log_ppm = self.upper_model.predict(features)
        lower_log_ppm, upper_log_ppm = np.minimum(lower_log_ppm, upper_log_ppm), np.maximum(
            lower_log_ppm,
            upper_log_ppm,
        )
        area = features["area_m2"].to_numpy(dtype=float)
        point = np.exp(point_log_ppm) * area
        lower = np.exp(lower_log_ppm) * area
        upper = np.exp(upper_log_ppm) * area
        width_ratio = (upper - lower) / np.maximum(point, 1.0)
        confidence = np.where(width_ratio <= 0.5, "high", np.where(width_ratio <= 0.8, "medium", "low"))
        return pd.DataFrame(
            {
                "estimated_price_per_m2": np.exp(point_log_ppm),
                "estimated_value_vnd": point,
                "lower_value_vnd": lower,
                "upper_value_vnd": upper,
                "interval_width_ratio": width_ratio,
                "confidence": confidence,
            },
            index=frame.index,
        )

    def predict_one(self, features: dict) -> dict:
        row = self.predict_frame(pd.DataFrame([features])).iloc[0]
        return {
            "estimated_price_per_m2": float(row["estimated_price_per_m2"]),
            "estimated_value_vnd": float(row["estimated_value_vnd"]),
            "lower_value_vnd": float(row["lower_value_vnd"]),
            "upper_value_vnd": float(row["upper_value_vnd"]),
            "interval_width_ratio": float(row["interval_width_ratio"]),
            "confidence": str(row["confidence"]),
        }

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: Path) -> "TabularHgbQuantileArtifact":
        artifact = joblib.load(path)
        if not isinstance(artifact, TabularHgbQuantileArtifact):
            raise TypeError(f"Unexpected AVM artifact type: {type(artifact)!r}")
        return artifact


def temporal_split(
    df: pd.DataFrame,
    train_end: str = "2025-11-01",
    valid_start: str = "2025-11-01",
    test_start: str = "2025-12-01",
) -> dict[str, pd.DataFrame]:
    published = pd.to_datetime(df["published_at"], utc=True)
    train_end_ts = pd.Timestamp(train_end, tz="UTC")
    valid_start_ts = pd.Timestamp(valid_start, tz="UTC")
    test_start_ts = pd.Timestamp(test_start, tz="UTC")
    return {
        "train": df.loc[published < train_end_ts].copy(),
        "validation": df.loc[(published >= valid_start_ts) & (published < test_start_ts)].copy(),
        "test": df.loc[published >= test_start_ts].copy(),
    }


def evaluate_price_per_m2_baselines(gold: pd.DataFrame) -> dict:
    clean = gold.loc[
        (gold["price_vnd"] > 0)
        & (gold["area_m2"] > 0)
        & gold["price_per_m2"].notna()
        & gold["published_at"].notna()
    ].copy()
    splits = temporal_split(clean)
    train = splits["train"]
    models: dict[str, PricePerM2Model] = {
        "global_median_price_per_m2": GlobalMedianPricePerM2().fit(train),
        "district_median_price_per_m2": GroupMedianPricePerM2(["province", "district"]).fit(train),
        "district_property_type_median_price_per_m2": GroupMedianPricePerM2(
            ["province", "district", "property_type"]
        ).fit(train),
    }
    metrics: list[AvmMetrics] = []
    for split_name in ("validation", "test"):
        frame = splits[split_name]
        for model_name, model in models.items():
            predictions = model.predict(frame)
            metrics.append(compute_avm_metrics(model_name, split_name, frame["price_vnd"], predictions))
    return {
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "metrics": [metric.__dict__ for metric in metrics],
        "best_test_by_mdape": _best_metric(metrics, "test", "mdape").__dict__,
    }


def evaluate_tabular_hgb_avm(gold: pd.DataFrame, random_state: int = 42) -> dict:
    clean = _clean_gold(gold)
    splits = temporal_split(clean)
    train = splits["train"]
    model = make_tabular_hgb_pipeline(random_state=random_state)
    model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], np.log(train["price_per_m2"]))
    metrics: list[AvmMetrics] = []
    for split_name in ("validation", "test"):
        frame = splits[split_name]
        predicted_log_ppm = model.predict(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        predicted_price = np.exp(predicted_log_ppm) * frame["area_m2"].to_numpy(dtype=float)
        metrics.append(compute_avm_metrics("hist_gradient_boosting_log_price_per_m2", split_name, frame["price_vnd"], predicted_price))
    return {
        "model": "hist_gradient_boosting_log_price_per_m2",
        "target": "log(price_per_m2)",
        "features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
        "random_state": random_state,
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "metrics": [metric.__dict__ for metric in metrics],
        "best_test_by_mdape": _best_metric(metrics, "test", "mdape").__dict__,
    }


def evaluate_tabular_hgb_intervals(gold: pd.DataFrame, random_state: int = 42) -> dict:
    clean = _clean_gold(gold)
    splits = temporal_split(clean)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    model = make_tabular_hgb_pipeline(random_state=random_state)
    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    model.fit(train[feature_columns], np.log(train["price_per_m2"]))

    validation_pred_log_ppm = model.predict(validation[feature_columns])
    validation_residuals = np.log(validation["price_per_m2"].to_numpy(dtype=float)) - validation_pred_log_ppm
    lower_residual = float(np.quantile(validation_residuals, 0.10))
    upper_residual = float(np.quantile(validation_residuals, 0.90))

    test_pred_log_ppm = model.predict(test[feature_columns])
    point = np.exp(test_pred_log_ppm) * test["area_m2"].to_numpy(dtype=float)
    lower = np.exp(test_pred_log_ppm + lower_residual) * test["area_m2"].to_numpy(dtype=float)
    upper = np.exp(test_pred_log_ppm + upper_residual) * test["area_m2"].to_numpy(dtype=float)
    actual = test["price_vnd"].to_numpy(dtype=float)
    coverage = np.mean((actual >= lower) & (actual <= upper))
    width_ratio = (upper - lower) / point
    interval_width_ratio_median = float(np.median(width_ratio))
    interval_width_ratio_p90 = float(np.quantile(width_ratio, 0.90))
    confidence = np.where(width_ratio <= 0.5, "high", np.where(width_ratio <= 0.8, "medium", "low"))
    return {
        "model": "hist_gradient_boosting_log_price_per_m2",
        "interval": "validation_log_residual_q10_q90",
        "target_coverage": 0.80,
        "random_state": random_state,
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "residual_quantiles": {"q10": lower_residual, "q90": upper_residual},
        "point_metrics": compute_avm_metrics(
            "hist_gradient_boosting_log_price_per_m2",
            "test",
            test["price_vnd"],
            point,
        ).__dict__,
        "interval_metrics": {
            "coverage": float(coverage),
            "median_interval_width_ratio": interval_width_ratio_median,
            "p90_interval_width_ratio": interval_width_ratio_p90,
            "high_confidence_share": float(np.mean(confidence == "high")),
            "medium_confidence_share": float(np.mean(confidence == "medium")),
            "low_confidence_share": float(np.mean(confidence == "low")),
        },
    }


def evaluate_tabular_hgb_cohort_intervals(
    gold: pd.DataFrame,
    cohort_columns: tuple[str, ...] = ("province", "property_type"),
    min_cohort_rows: int = 500,
    random_state: int = 42,
) -> dict:
    clean = _clean_gold(gold)
    splits = temporal_split(clean)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    model = make_tabular_hgb_pipeline(random_state=random_state)
    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    model.fit(train[feature_columns], np.log(train["price_per_m2"]))

    validation_pred_log_ppm = model.predict(validation[feature_columns])
    validation_residuals = np.log(validation["price_per_m2"].to_numpy(dtype=float)) - validation_pred_log_ppm
    global_quantiles = _residual_quantiles(validation_residuals)
    cohort_quantiles = _cohort_residual_quantiles(
        validation,
        validation_residuals,
        cohort_columns=cohort_columns,
        min_cohort_rows=min_cohort_rows,
    )

    test_pred_log_ppm = model.predict(test[feature_columns])
    cohort_lower, cohort_upper, used_cohort = _assign_cohort_residuals(
        test,
        cohort_quantiles,
        cohort_columns=cohort_columns,
        fallback=global_quantiles,
    )
    area = test["area_m2"].to_numpy(dtype=float)
    point = np.exp(test_pred_log_ppm) * area
    lower = np.exp(test_pred_log_ppm + cohort_lower) * area
    upper = np.exp(test_pred_log_ppm + cohort_upper) * area
    actual = test["price_vnd"].to_numpy(dtype=float)
    coverage = np.mean((actual >= lower) & (actual <= upper))
    width_ratio = (upper - lower) / point
    confidence = np.where(width_ratio <= 0.5, "high", np.where(width_ratio <= 0.8, "medium", "low"))

    return {
        "model": "hist_gradient_boosting_log_price_per_m2",
        "interval": "validation_log_residual_q10_q90_by_cohort",
        "target_coverage": 0.80,
        "random_state": random_state,
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "cohort_config": {
            "columns": list(cohort_columns),
            "min_validation_rows": min_cohort_rows,
            "qualified_cohorts": len(cohort_quantiles),
            "test_rows_using_cohort": int(used_cohort.sum()),
            "test_rows_using_global_fallback": int((~used_cohort).sum()),
            "test_global_fallback_share": float(np.mean(~used_cohort)),
        },
        "global_residual_quantiles": {
            "q10": global_quantiles[0],
            "q90": global_quantiles[1],
        },
        "point_metrics": compute_avm_metrics(
            "hist_gradient_boosting_log_price_per_m2",
            "test",
            test["price_vnd"],
            point,
        ).__dict__,
        "interval_metrics": {
            "coverage": float(coverage),
            "median_interval_width_ratio": float(np.median(width_ratio)),
            "p90_interval_width_ratio": float(np.quantile(width_ratio, 0.90)),
            "high_confidence_share": float(np.mean(confidence == "high")),
            "medium_confidence_share": float(np.mean(confidence == "medium")),
            "low_confidence_share": float(np.mean(confidence == "low")),
        },
    }


def evaluate_tabular_hgb_quantile_intervals(gold: pd.DataFrame, random_state: int = 42) -> dict:
    clean = _clean_gold(gold)
    splits = temporal_split(clean)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    target = np.log(train["price_per_m2"])

    point_model = make_tabular_hgb_pipeline(random_state=random_state)
    lower_model = make_tabular_hgb_pipeline(random_state=random_state, loss="quantile", quantile=0.10)
    upper_model = make_tabular_hgb_pipeline(random_state=random_state, loss="quantile", quantile=0.90)
    point_model.fit(train[feature_columns], target)
    lower_model.fit(train[feature_columns], target)
    upper_model.fit(train[feature_columns], target)

    validation_interval_metrics = _predict_interval_metrics(
        validation,
        point_model,
        lower_model,
        upper_model,
        feature_columns,
    )
    test_interval_metrics = _predict_interval_metrics(
        test,
        point_model,
        lower_model,
        upper_model,
        feature_columns,
    )
    return {
        "model": "hist_gradient_boosting_log_price_per_m2",
        "interval": "hist_gradient_boosting_quantile_log_price_per_m2_q10_q90",
        "target_coverage": 0.80,
        "random_state": random_state,
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "point_metrics": compute_avm_metrics(
            "hist_gradient_boosting_log_price_per_m2",
            "test",
            test["price_vnd"],
            test_interval_metrics["point"],
        ).__dict__,
        "validation_interval_metrics": validation_interval_metrics["summary"],
        "interval_metrics": test_interval_metrics["summary"],
    }


def fit_tabular_hgb_quantile_artifact(
    gold: pd.DataFrame,
    random_state: int = 42,
    snapshot_id: str = "unknown",
) -> tuple[TabularHgbQuantileArtifact, dict]:
    clean = _clean_gold(gold)
    splits = temporal_split(clean)
    train = splits["train"]
    test = splits["test"]
    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    target = np.log(train["price_per_m2"])

    point_model = make_tabular_hgb_pipeline(random_state=random_state)
    lower_model = make_tabular_hgb_pipeline(random_state=random_state, loss="quantile", quantile=0.10)
    upper_model = make_tabular_hgb_pipeline(random_state=random_state, loss="quantile", quantile=0.90)
    point_model.fit(train[feature_columns], target)
    lower_model.fit(train[feature_columns], target)
    upper_model.fit(train[feature_columns], target)

    artifact = TabularHgbQuantileArtifact(
        point_model=point_model,
        lower_model=lower_model,
        upper_model=upper_model,
        metadata={
            "model_version": "avm_hgb_quantile_experimental_20260726",
            "model": "hist_gradient_boosting_log_price_per_m2",
            "interval": "hist_gradient_boosting_quantile_log_price_per_m2_q10_q90",
            "target": "log(price_per_m2)",
            "random_state": random_state,
            "snapshot_id": snapshot_id,
            "feature_columns": feature_columns,
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
        },
    )
    predictions = artifact.predict_frame(test)
    return artifact, {
        "model": artifact.metadata["model"],
        "model_version": artifact.metadata["model_version"],
        "target": artifact.metadata["target"],
        "interval": artifact.metadata["interval"],
        "random_state": random_state,
        "split_rows": {name: len(frame) for name, frame in splits.items()},
        "point_metrics": compute_avm_metrics(
            artifact.metadata["model"],
            "test",
            test["price_vnd"],
            predictions["estimated_value_vnd"].to_numpy(dtype=float),
        ).__dict__,
        "interval_metrics": _interval_summary(
            test["price_vnd"].to_numpy(dtype=float),
            predictions["estimated_value_vnd"].to_numpy(dtype=float),
            predictions["lower_value_vnd"].to_numpy(dtype=float),
            predictions["upper_value_vnd"].to_numpy(dtype=float),
        ),
    }


def make_tabular_hgb_pipeline(
    random_state: int = 42,
    loss: str = "squared_error",
    quantile: float | None = None,
) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
                        (
                            "encoder",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                encoded_missing_value=-1,
                            ),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        verbose_feature_names_out=False,
    )
    return Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "model",
                HistGradientBoostingRegressor(
                    loss=loss,
                    quantile=quantile,
                    learning_rate=0.06,
                    max_iter=220,
                    max_leaf_nodes=31,
                    l2_regularization=0.05,
                    random_state=random_state,
                ),
            ),
        ]
    )


class GlobalMedianPricePerM2:
    def __init__(self) -> None:
        self.median_: float | None = None

    def fit(self, train: pd.DataFrame) -> GlobalMedianPricePerM2:
        self.median_ = float(train["price_per_m2"].median())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.median_ is None:
            raise RuntimeError("Model is not fitted")
        return frame["area_m2"].to_numpy(dtype=float) * self.median_


class GroupMedianPricePerM2:
    def __init__(self, group_columns: list[str]) -> None:
        self.group_columns = group_columns
        self.global_median_: float | None = None
        self.medians_: pd.Series | None = None

    def fit(self, train: pd.DataFrame) -> GroupMedianPricePerM2:
        self.global_median_ = float(train["price_per_m2"].median())
        self.medians_ = train.groupby(self.group_columns, dropna=False)["price_per_m2"].median()
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.global_median_ is None or self.medians_ is None:
            raise RuntimeError("Model is not fitted")
        keys = pd.MultiIndex.from_frame(frame[self.group_columns])
        medians = self.medians_.reindex(keys).to_numpy()
        filled = np.where(pd.isna(medians), self.global_median_, medians).astype(float)
        return frame["area_m2"].to_numpy(dtype=float) * filled


def compute_avm_metrics(
    model_name: str,
    split_name: str,
    actual: pd.Series,
    predicted: np.ndarray,
) -> AvmMetrics:
    actual_arr = actual.to_numpy(dtype=float)
    predicted_arr = np.maximum(predicted.astype(float), 1.0)
    abs_err = np.abs(predicted_arr - actual_arr)
    ape = abs_err / actual_arr
    return AvmMetrics(
        model_name=model_name,
        split_name=split_name,
        rows=len(actual_arr),
        mae_vnd=float(mean_absolute_error(actual_arr, predicted_arr)),
        median_absolute_error_vnd=float(np.median(abs_err)),
        mdape=float(np.median(ape)),
        rmsle=float(np.sqrt(mean_squared_log_error(actual_arr, predicted_arr))),
        r2=float(r2_score(actual_arr, predicted_arr)),
        within_10pct=float(np.mean(ape <= 0.10)),
        within_20pct=float(np.mean(ape <= 0.20)),
    )


def write_avm_report(report: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _clean_gold(gold: pd.DataFrame) -> pd.DataFrame:
    clean = gold.loc[
        (gold["price_vnd"] > 0)
        & (gold["area_m2"] > 0)
        & gold["price_per_m2"].notna()
        & gold["published_at"].notna()
    ].copy()
    for column in NUMERIC_FEATURES:
        if column not in clean.columns:
            clean[column] = np.nan
    for column in CATEGORICAL_FEATURES:
        if column not in clean.columns:
            clean[column] = "missing"
    return clean


def _ensure_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame.copy()
    for column in NUMERIC_FEATURES:
        if column not in features.columns:
            features[column] = np.nan
    for column in CATEGORICAL_FEATURES:
        if column not in features.columns:
            features[column] = "missing"
    return features[NUMERIC_FEATURES + CATEGORICAL_FEATURES]


def _residual_quantiles(residuals: np.ndarray) -> tuple[float, float]:
    return float(np.quantile(residuals, 0.10)), float(np.quantile(residuals, 0.90))


def _cohort_residual_quantiles(
    validation: pd.DataFrame,
    residuals: np.ndarray,
    cohort_columns: tuple[str, ...],
    min_cohort_rows: int,
) -> dict[tuple[object, ...], tuple[float, float]]:
    residual_frame = validation.loc[:, list(cohort_columns)].copy()
    residual_frame["_residual"] = residuals
    quantiles: dict[tuple[object, ...], tuple[float, float]] = {}
    for key, group in residual_frame.groupby(list(cohort_columns), dropna=False):
        if len(group) < min_cohort_rows:
            continue
        normalized_key = key if isinstance(key, tuple) else (key,)
        quantiles[normalized_key] = _residual_quantiles(group["_residual"].to_numpy(dtype=float))
    return quantiles


def _assign_cohort_residuals(
    frame: pd.DataFrame,
    cohort_quantiles: dict[tuple[object, ...], tuple[float, float]],
    cohort_columns: tuple[str, ...],
    fallback: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lower = np.full(len(frame), fallback[0], dtype=float)
    upper = np.full(len(frame), fallback[1], dtype=float)
    used_cohort = np.zeros(len(frame), dtype=bool)
    for position, key in enumerate(frame.loc[:, list(cohort_columns)].itertuples(index=False, name=None)):
        quantiles = cohort_quantiles.get(key)
        if quantiles is None:
            continue
        lower[position], upper[position] = quantiles
        used_cohort[position] = True
    return lower, upper, used_cohort


def _predict_interval_metrics(
    frame: pd.DataFrame,
    point_model: Pipeline,
    lower_model: Pipeline,
    upper_model: Pipeline,
    feature_columns: list[str],
) -> dict:
    features = frame[feature_columns]
    point_log_ppm = point_model.predict(features)
    lower_log_ppm = lower_model.predict(features)
    upper_log_ppm = upper_model.predict(features)
    lower_log_ppm, upper_log_ppm = np.minimum(lower_log_ppm, upper_log_ppm), np.maximum(
        lower_log_ppm,
        upper_log_ppm,
    )
    area = frame["area_m2"].to_numpy(dtype=float)
    point = np.exp(point_log_ppm) * area
    lower = np.exp(lower_log_ppm) * area
    upper = np.exp(upper_log_ppm) * area
    actual = frame["price_vnd"].to_numpy(dtype=float)
    coverage = np.mean((actual >= lower) & (actual <= upper))
    width_ratio = (upper - lower) / np.maximum(point, 1.0)
    confidence = np.where(width_ratio <= 0.5, "high", np.where(width_ratio <= 0.8, "medium", "low"))
    return {
        "point": point,
        "summary": {
            "coverage": float(coverage),
            "median_interval_width_ratio": float(np.median(width_ratio)),
            "p90_interval_width_ratio": float(np.quantile(width_ratio, 0.90)),
            "high_confidence_share": float(np.mean(confidence == "high")),
            "medium_confidence_share": float(np.mean(confidence == "medium")),
            "low_confidence_share": float(np.mean(confidence == "low")),
        },
    }


def _interval_summary(actual: np.ndarray, point: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict:
    coverage = np.mean((actual >= lower) & (actual <= upper))
    width_ratio = (upper - lower) / np.maximum(point, 1.0)
    confidence = np.where(width_ratio <= 0.5, "high", np.where(width_ratio <= 0.8, "medium", "low"))
    return {
        "coverage": float(coverage),
        "median_interval_width_ratio": float(np.median(width_ratio)),
        "p90_interval_width_ratio": float(np.quantile(width_ratio, 0.90)),
        "high_confidence_share": float(np.mean(confidence == "high")),
        "medium_confidence_share": float(np.mean(confidence == "medium")),
        "low_confidence_share": float(np.mean(confidence == "low")),
    }


def _best_metric(metrics: list[AvmMetrics], split_name: str, field: str) -> AvmMetrics:
    candidates = [metric for metric in metrics if metric.split_name == split_name]
    return min(candidates, key=lambda metric: getattr(metric, field))
