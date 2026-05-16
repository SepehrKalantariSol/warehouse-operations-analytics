"""
Delay Prediction Model — RandomForest Classifier

Uses only pre-order features (known before picking starts) to avoid
data leakage from picking_time / packing_time / total_time.

Usage:
    python src/ml_model.py          # trains, evaluates, saves
    from src.ml_model import load_model, predict_proba_single
"""

import json
import sqlite3
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "warehouse.db"
MODEL_PATH = ROOT / "models" / "delay_classifier.joblib"
METADATA_PATH = ROOT / "models" / "model_metadata.json"

# Features known before the order is processed — no leakage
PRE_ORDER_FEATURES = [
    "items_count",
    "picker_experience",
    "distance_travelled",
    "workload_index",
    "target_time",
    "is_experienced",
    "is_high_congestion",
    "equipment_penalty",
    "is_weekend",
    "order_month",
    "order_quarter",
    "order_day_of_week",
    "shift_encoded",
    "zone_encoded",
    "priority_encoded",
    "congestion_encoded",
]


# ── Data loading ───────────────────────────────────────────────────────────────

def load_features(db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.Series]:
    conn = sqlite3.connect(db_path)
    cols = ", ".join(PRE_ORDER_FEATURES + ["delayed"])
    df = pd.read_sql_query(f"SELECT {cols} FROM ml_features", conn)
    conn.close()
    return df[PRE_ORDER_FEATURES], df["delayed"]


# ── Training ───────────────────────────────────────────────────────────────────

def train(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate(
    model: RandomForestClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_train: int,
) -> dict:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    cm = confusion_matrix(y_test, y_pred).tolist()
    importance = dict(
        zip(PRE_ORDER_FEATURES, model.feature_importances_.round(4).tolist())
    )
    return {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred)), 4),
        "recall": round(float(recall_score(y_test, y_pred)), 4),
        "f1": round(float(f1_score(y_test, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "confusion_matrix": cm,
        "feature_importance": importance,
        "features": PRE_ORDER_FEATURES,
        "n_train": n_train,
        "n_test": len(X_test),
        "training_date": str(date.today()),
    }


# ── Persistence ────────────────────────────────────────────────────────────────

def save_model(
    model: RandomForestClassifier,
    metrics: dict,
    model_path: Path = MODEL_PATH,
    meta_path: Path = METADATA_PATH,
) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    with open(meta_path, "w") as f:
        json.dump(metrics, f, indent=2)


def load_model(
    model_path: Path = MODEL_PATH,
    meta_path: Path = METADATA_PATH,
) -> tuple[RandomForestClassifier, dict]:
    model = joblib.load(model_path)
    with open(meta_path) as f:
        metadata = json.load(f)
    return model, metadata


# ── Inference ──────────────────────────────────────────────────────────────────

def predict_proba_single(
    model: RandomForestClassifier,
    feature_values: list[float],
) -> float:
    """
    Returns delay probability (0–1) for one order.
    feature_values must be in PRE_ORDER_FEATURES order.
    """
    arr = np.array(feature_values, dtype=float).reshape(1, -1)
    return float(model.predict_proba(arr)[0, 1])


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading features...")
    X, y = load_features()
    print(f"  Samples: {len(X):,}  |  Delay rate: {y.mean():.1%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    print("Training RandomForest (200 trees)...")
    model = train(X_train, y_train)

    print("Evaluating...")
    metrics = evaluate(model, X_test, y_test, n_train=len(X_train))

    print(f"\n  Accuracy  : {metrics['accuracy']:.3f}")
    print(f"  Precision : {metrics['precision']:.3f}")
    print(f"  Recall    : {metrics['recall']:.3f}")
    print(f"  F1        : {metrics['f1']:.3f}")
    print(f"  ROC-AUC   : {metrics['roc_auc']:.3f}")

    cm = metrics["confusion_matrix"]
    print(f"\n  Confusion matrix (test set):")
    print(f"    True Negatives : {cm[0][0]}  |  False Positives: {cm[0][1]}")
    print(f"    False Negatives: {cm[1][0]}  |  True Positives : {cm[1][1]}")

    print(f"\n  Top 5 features by importance:")
    top5 = sorted(metrics["feature_importance"].items(), key=lambda x: -x[1])[:5]
    for feat, imp in top5:
        bar = "█" * int(imp * 200)
        print(f"    {feat:<30} {imp:.4f}  {bar}")

    print("\nSaving model and metadata...")
    save_model(model, metrics)
    print(f"  → {MODEL_PATH}")
    print(f"  → {METADATA_PATH}")


if __name__ == "__main__":
    main()
