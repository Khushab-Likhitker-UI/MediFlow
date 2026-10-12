"""
verify_backend.py
=================

Smoke-test script for the Smart Health FastAPI backend.

What it does
------------
1. Imports ``requests`` and ``datetime``.
2. Generates a mock PredictionRequest payload:
     - 30 days of DailyFootfall data (dates leading up to today)
     - random patient_count values between 40 and 100
3. Sends a POST request to http://127.0.0.1:8000/api/predict
   (routes through shortage_router mounted at /api in main.py).
4. Asserts that the HTTP status code is 200.
5. Prints the raw JSON response to the console.

Route resolution
----------------
  predictions.py  :  shortage_router.post("/predict")
  main.py         :  app.include_router(shortage_router, prefix="/api")
  ─────────────────────────────────────────────────────────────────────
  Final endpoint  :  POST http://127.0.0.1:8000/api/predict

Usage
-----
    # Terminal 1 – start the server
    cd backend
    uvicorn main:app --reload

    # Terminal 2 – run this script
    cd backend
    python verify_backend.py
"""

# ── Standard library imports (required by task spec) ─────────────────────────
import json
import random
import sys
from datetime import date, datetime, timedelta   # <-- datetime imported here

# ── Third-party imports (required by task spec) ───────────────────────────────
import requests                                  # <-- requests imported here

# ── Configuration ─────────────────────────────────────────────────────────────

PREDICT_URL = "http://127.0.0.1:8000/api/predict"   # matches predictions.py route

DAYS_OF_HISTORY        = 30   # 30 DailyFootfall records
MIN_PATIENT_COUNT      = 40   # random patient_count lower bound
MAX_PATIENT_COUNT      = 100  # random patient_count upper bound
EXPECTED_FORECAST_DAYS = 7    # Prophet / SMA produces a 7-day forecast


# ── Payload builder ───────────────────────────────────────────────────────────

def build_payload() -> dict:
    """
    Generate a mock FootfallPredictionRequest payload.

    Creates 30 DailyFootfall records with dates leading up to today
    and random patient_counts between 40 and 100.

    Returns
    -------
    dict
        JSON-serialisable body matching the FootfallPredictionRequest schema::

            {
                "footfall_data": [
                    {
                        "phc_id":        "PHC-TEST-001",
                        "date":          "YYYY-MM-DD",
                        "patient_count": <int 40-100>
                    },
                    ...   # 30 records total
                ]
            }
    """
    today = date.today()                              # <-- uses datetime.date
    footfall_data = []

    for offset in range(DAYS_OF_HISTORY, 0, -1):     # oldest -> newest
        record_date = today - timedelta(days=offset)
        footfall_data.append(
            {
                "phc_id":        "PHC-TEST-001",
                "date":          record_date.isoformat(),   # "YYYY-MM-DD"
                "patient_count": random.randint(MIN_PATIENT_COUNT, MAX_PATIENT_COUNT),
            }
        )

    return {"footfall_data": footfall_data}


# ── Main test runner ──────────────────────────────────────────────────────────

def main() -> None:
    run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # <-- uses datetime

    print("=" * 64)
    print("  verify_backend.py  -  Footfall Prediction Smoke Test")
    print(f"  Run at : {run_at}")
    print("=" * 64)

    # ── Step 1: Build mock payload ────────────────────────────────────────────
    payload = build_payload()
    first_date = payload["footfall_data"][0]["date"]
    last_date  = payload["footfall_data"][-1]["date"]

    print(f"\n[INFO] Generated {len(payload['footfall_data'])} DailyFootfall records")
    print(f"       patient_count range : {MIN_PATIENT_COUNT} - {MAX_PATIENT_COUNT}")
    print(f"       date range          : {first_date}  ->  {last_date}")

    # ── Step 2: POST to /api/predict ──────────────────────────────────────────
    print(f"\n-->  POST {PREDICT_URL}")
    try:
        response = requests.post(PREDICT_URL, json=payload, timeout=60)
    except requests.ConnectionError:
        print(
            "\n[FAIL] Cannot connect to the FastAPI server.\n"
            "  Start it first:\n"
            "    cd backend\n"
            "    uvicorn main:app --reload"
        )
        sys.exit(1)

    # ── Step 3: Assert HTTP 200 ───────────────────────────────────────────────
    print(f"       Status code : {response.status_code}")
    assert response.status_code == 200, (
        f"Expected HTTP 200 but received {response.status_code}.\n"
        f"Response body: {response.text}"
    )
    print("       [OK] Status code is 200")

    # ── Step 4: Print raw JSON response ───────────────────────────────────────
    resp_json = response.json()
    print("\n-- Raw JSON Response --------------------------------------------------")
    print(json.dumps(resp_json, indent=2))
    print("-----------------------------------------------------------------------")

    # ── Step 5: Validate response structure ───────────────────────────────────
    assert "predictions" in resp_json, \
        "Response JSON is missing the 'predictions' key."

    predictions = resp_json["predictions"]
    assert len(predictions) == EXPECTED_FORECAST_DAYS, (
        f"Expected {EXPECTED_FORECAST_DAYS} forecast items, got {len(predictions)}."
    )

    required_keys = {"date", "predicted_count", "lower_bound", "upper_bound"}
    for idx, pred in enumerate(predictions):
        missing = required_keys - set(pred.keys())
        assert not missing, f"Prediction[{idx}] missing keys: {missing}"

    print(
        f"\n[OK] SUCCESS - received {len(predictions)}-day forecast. "
        "All assertions passed."
    )


if __name__ == "__main__":
    main()
