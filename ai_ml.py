# ai_ml.py
import os
import pandas as pd
import numpy as np
from joblib import load

MODEL_PATH = os.path.join("models","capacity_model.joblib")
_model_data = None

def load_model():
    global _model_data
    if _model_data is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError("Capacity model not found. Run train_capacity.py first.")
        _model_data = load(MODEL_PATH)
    return _model_data

def predict_capacity_ml(origin, destination, date_str=None, cargo_type="General"):
    # load model and columns
    md = load_model()
    model = md["model"]
    columns = md["columns"]

    # extract month from date if provided
    month = 1
    if date_str:
        try:
            month = int(date_str.split("-")[1])
        except Exception:
            month = 1

    route = f"{origin.upper()}-{destination.upper()}"
    # build dataframe with same columns
    row = {"month": month}
    for c in columns:
        if c.startswith("route_"):
            row[c] = 1 if c == f"route_{route}" else 0
        elif c.startswith("cargo_"):
            row[c] = 1 if c == f"cargo_{cargo_type}" else 0
        else:
            if c not in row:
                row[c] = 0
    X = pd.DataFrame([row], columns=columns).fillna(0)
    pred = int(model.predict(X)[0])
    return {"predicted_capacity": pred, "route": f"{origin.upper()}->{destination.upper()}", "month":month}
