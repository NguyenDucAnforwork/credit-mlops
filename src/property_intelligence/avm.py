from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
    models = {
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


def make_tabular_hgb_pipeline(random_state: int = 42) -> Pipeline:
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


def _best_metric(metrics: list[AvmMetrics], split_name: str, field: str) -> AvmMetrics:
    candidates = [metric for metric in metrics if metric.split_name == split_name]
    return min(candidates, key=lambda metric: getattr(metric, field))
