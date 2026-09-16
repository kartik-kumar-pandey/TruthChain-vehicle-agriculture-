# ==============================================================================
# 🚀 TRUTHCHAIN 2.0 — SENSOR TELEMATICS ML MODEL TRAINING SCRIPT (FOR GOOGLE COLAB)
# ==============================================================================
# Instructions:
# 1. Copy & paste this entire script into a single cell in Google Colab (colab.research.google.com).
# 2. Click "Run" (Shift + Enter).
# 3. The script will generate data, train a RandomForest Telematics Classifier,
#    evaluate metrics (Precision, Recall, F1, FPR), and automatically download 'sensor_model.pkl'.
# 4. Move the downloaded 'sensor_model.pkl' into your local project folder:
#    Kartik-finalyear/models/sensor_model.pkl
# ==============================================================================

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

try:
    from google.colab import files
    COLAB_ENV = True
except ImportError:
    COLAB_ENV = False

def generate_telematics_dataset(n_samples: int = 1500, random_seed: int = 42):
    """
    Generates realistic motor telematics samples with measurement noise & boundary overlap:
    - Legitimate crashes & braking: G-force ranges from 0.8G to 8.5G with proportional speed drop.
    - Anomalous telematics: Zero/low G-force reported during claimed impact, synthetic pulses, or high noise jitter.
    """
    np.random.seed(random_seed)
    
    n_normal = int(n_samples * 0.75)
    n_anomaly = n_samples - n_normal

    # Legitimate telematics (Hard braking + collision impacts)
    normal_peak_g = np.random.normal(loc=3.5, scale=1.4, size=n_normal)
    normal_peak_g = np.clip(normal_peak_g, 0.6, 8.5)
    
    normal_speed_drop = normal_peak_g * np.random.uniform(6.0, 14.0, n_normal) + np.random.normal(0, 3.0, n_normal)
    normal_speed_drop = np.clip(normal_speed_drop, 5.0, 110.0)
    
    normal_gps_speed = normal_speed_drop + np.random.uniform(0.0, 20.0, n_normal)
    normal_duration = np.random.normal(loc=180.0, scale=45.0, size=n_normal)
    normal_jitter = np.random.exponential(scale=0.06, size=n_normal)
    normal_labels = np.zeros(n_normal, dtype=int)

    # Anomalous telematics (Staged claims, fake logs, sensor noise)
    anomaly_peak_g = np.random.exponential(scale=0.5, size=n_anomaly)
    anomaly_peak_g = np.clip(anomaly_peak_g, 0.02, 2.2) # Overlaps slightly with low-speed braking
    
    anomaly_speed_drop = np.random.uniform(0.0, 12.0, n_anomaly) + np.random.normal(0, 2.0, n_anomaly)
    anomaly_speed_drop = np.clip(anomaly_speed_drop, 0.0, 25.0)
    
    anomaly_gps_speed = np.random.uniform(30.0, 95.0, n_anomaly)
    anomaly_duration = np.random.uniform(10.0, 90.0, n_anomaly)
    anomaly_jitter = np.random.uniform(0.18, 0.85, n_anomaly)
    anomaly_labels = np.ones(n_anomaly, dtype=int)

    X = np.vstack([
        np.column_stack([normal_peak_g, normal_speed_drop, normal_gps_speed, normal_duration, normal_jitter]),
        np.column_stack([anomaly_peak_g, anomaly_speed_drop, anomaly_gps_speed, anomaly_duration, anomaly_jitter])
    ])
    y = np.concatenate([normal_labels, anomaly_labels])

    # Inject 3.5% random label noise to simulate sensor calibration drift
    noise_mask = np.random.rand(n_samples) < 0.035
    y[noise_mask] = 1 - y[noise_mask]

    feature_names = [
        "acceleration_peak_g",
        "speed_drop_kph",
        "gps_speed_kph",
        "impact_duration_ms",
        "sensor_jitter_std"
    ]
    df = pd.DataFrame(X, columns=feature_names)
    df["is_anomaly"] = y

    # Shuffle
    df = df.sample(frac=1.0, random_state=random_seed).reset_index(drop=True)
    return df


def main():
    print("=" * 70)
    print("🤖 TruthChain 2.0 — Production Sensor ML Model Training (Google Colab)")
    print("=" * 70)

    df = generate_telematics_dataset(n_samples=1500, random_seed=42)
    feature_cols = [
        "acceleration_peak_g",
        "speed_drop_kph",
        "gps_speed_kph",
        "impact_duration_ms",
        "sensor_jitter_std"
    ]
    X = df[feature_cols].values
    y = df["is_anomaly"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    clf = RandomForestClassifier(n_estimators=120, max_depth=7, random_state=42)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    print("\n✅ Model Training Complete!")
    print(f"📊 Held-Out Test Set Evaluation Metrics (N = {len(y_test)}):")
    print(f"   • Precision:            {prec:.4f} ({prec * 100:.2f}%)")
    print(f"   • Recall:               {rec:.4f} ({rec * 100:.2f}%)")
    print(f"   • F1-Score:             {f1:.4f} ({f1 * 100:.2f}%)")
    print(f"   • False Positive Rate:  {fpr:.4f} ({fpr * 100:.2f}%)")
    print("-" * 70)

    output_filename = "sensor_model.pkl"
    model_payload = {
        "model": clf,
        "feature_names": feature_cols,
        "metrics": {
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1),
            "fpr": float(fpr)
        },
        "version": "sensor-rf-v1.0"
    }

    joblib.dump(model_payload, output_filename)
    print(f"💾 Saved '{output_filename}' ({os.path.getsize(output_filename)} bytes).")

    if COLAB_ENV:
        print("⬇️ Triggering automatic download in Google Colab...")
        files.download(output_filename)
    else:
        print(f"📁 Local file available at: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    main()
