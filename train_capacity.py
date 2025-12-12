# train_capacity.py
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from joblib import dump

os.makedirs("models", exist_ok=True)

# Try to load historical flight data (if user exported CSV). Otherwise synthesize demo data.
if os.path.exists("historical_flights.csv"):
    df = pd.read_csv("historical_flights.csv")
else:
    # synthesize small demo dataset
    rng = np.random.RandomState(42)
    rows = []
    routes = [("DEL","DXB"),("DEL","LHR"),("JFK","LHR"),("AMS","JFK"),("FRA","JFK")]
    for i in range(800):
        origin, dest = routes[rng.randint(0,len(routes))]
        month = rng.randint(1,13)
        cargo_type = rng.choice(["General","Pharma","Perishables","DG"])
        base = 3000 + 1000 * routes.index((origin,dest))
        cap = int(base * (0.6 + 0.8 * rng.rand()) * (1 + 0.1*np.sin(month)))
        rows.append({"origin":origin,"destination":dest,"month":month,"cargo_type":cargo_type,"capacity":cap})
    df = pd.DataFrame(rows)

# Feature engineering
df["route"] = df["origin"].str.upper() + "-" + df["destination"].str.upper()
route_dummies = pd.get_dummies(df["route"], prefix="route")
cargo_dummies = pd.get_dummies(df["cargo_type"], prefix="cargo")
X = pd.concat([df[["month"]], route_dummies, cargo_dummies], axis=1)
y = df["capacity"]

# train
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print("Train R2:", model.score(X_train, y_train))
print("Test R2:", model.score(X_test, y_test))

# save model + example feature columns
dump({"model": model, "columns": X.columns.tolist()}, "models/capacity_model.joblib")
print("Saved: models/capacity_model.joblib")
