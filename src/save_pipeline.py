"""
Re-saves the feature pipeline with the correct module path (features.FeaturePipeline,
not __main__.FeaturePipeline) so pytest and Docker can load it without errors.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from features import FeaturePipeline

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

train_df = pd.read_csv(PROCESSED_DIR / "train_data.csv")
X_train = train_df.drop(columns=["label"])
y_train = train_df["label"]

fp = FeaturePipeline()
fp.fit_transform(X_train, y_train)
fp.save()
print(f"[save_pipeline] Saved: {fp.n_features_out()} features out → artifacts/feature_pipeline.joblib")
