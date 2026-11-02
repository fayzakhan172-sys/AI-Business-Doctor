import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = ["lag_1", "lag_2", "lag_3", "lag_12", "roll_3", "month"]


def _monthly_series(df):
    """Monthly total sales as a Series with a month-start DatetimeIndex."""
    return df.set_index("Date")["Sales"].resample("MS").sum()


def _make_features(sales):
    data = sales.to_frame("Sales")
    data["lag_1"] = data["Sales"].shift(1)
    data["lag_2"] = data["Sales"].shift(2)
    data["lag_3"] = data["Sales"].shift(3)
    data["lag_12"] = data["Sales"].shift(12)
    data["roll_3"] = data["Sales"].shift(1).rolling(3).mean()
    data["month"] = data.index.month
    return data


def _metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


def forecast_sales(df, horizon=6, test_size=6):
    """
    Train on history, compare with a baseline on the last `test_size` months,
    then forecast `horizon` future months.
    Returns a dict, or None if there is not enough data.
    """
    sales = _monthly_series(df)

    # lag_12 needs 12 months, plus we need train + test rows
    if len(sales) < 12 + test_size + 12:
        return None

    data = _make_features(sales).dropna()
    train, test = data.iloc[:-test_size], data.iloc[-test_size:]

    # Evaluate: Random Forest vs baseline (average of previous 3 months)
    model = RandomForestRegressor(n_estimators=300, random_state=42)
    model.fit(train[FEATURES], train["Sales"])
    rf_pred = model.predict(test[FEATURES])

    rf_scores = _metrics(test["Sales"], rf_pred)
    base_scores = _metrics(test["Sales"], test["roll_3"])
    use_rf = rf_scores["MAE"] < base_scores["MAE"]

    # Refit on ALL data, then forecast month by month
    model.fit(data[FEATURES], data["Sales"])
    history = sales.copy()
    future_rows = []

    for _ in range(horizon):
        next_date = history.index[-1] + pd.offsets.MonthBegin(1)
        row = {
            "lag_1": history.iloc[-1],
            "lag_2": history.iloc[-2],
            "lag_3": history.iloc[-3],
            "lag_12": history.iloc[-12],
            "roll_3": history.iloc[-3:].mean(),
            "month": next_date.month,
        }
        if use_rf:
            pred = float(model.predict(pd.DataFrame([row])[FEATURES])[0])
        else:
            pred = float(row["roll_3"])
        history.loc[next_date] = pred
        future_rows.append((next_date, pred))

    future = pd.DataFrame(future_rows, columns=["Date", "Forecast"])

    return {
        "history": sales,
        "future": future,
        "test_index": test.index,
        "test_pred": rf_pred,
        "rf_scores": rf_scores,
        "baseline_scores": base_scores,
        "model_used": "Random Forest" if use_rf else "Baseline (3-month average)",
    }