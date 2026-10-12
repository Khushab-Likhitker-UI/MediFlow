"""
test_predictions.py — Frontend client simulator
=================================================

Generates 30 days of mock patient footfall data, POSTs it to the
/api/predict-shortage endpoint, and verifies the response.

Exit codes:
    0  – all assertions passed
    1  – a test assertion failed
    2  – the request itself failed (server down, network error, etc.)
"""

import json
import random
import sys
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    class _RequestsFallback:
        class Response:
            def __init__(self, status_code, text):
                self.status_code = status_code
                self.text = text
            def json(self):
                return json.loads(self.text)
        class ConnectionError(Exception):
            pass
        @staticmethod
        def post(url, **kwargs):
            import urllib.request
            import urllib.error
            import json as _j
            payload = kwargs.get("json", kwargs.get("data"))
            timeout = kwargs.get("timeout", 60)
            data = _j.dumps(payload).encode('utf-8') if payload is not None else None
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return _RequestsFallback.Response(resp.status, resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                return _RequestsFallback.Response(e.code, e.read().decode('utf-8'))
            except urllib.error.URLError as e:
                raise _RequestsFallback.ConnectionError(str(e))
    requests = _RequestsFallback()


# ── Configuration ────────────────────────────────────────────────────────────

API_URL = "http://localhost:8000/api/predict-shortage"
HISTORY_DAYS = 30
EXPECTED_PREDICTIONS = 7

# ── Generate mock data ───────────────────────────────────────────────────────


def generate_mock_history(days: int = HISTORY_DAYS) -> list[dict]:
    """Create `days` consecutive daily footfall records with realistic noise."""
    random.seed(42)
    base = 120  # average daily patient count
    today = datetime.now().date()
    start = today - timedelta(days=days)

    history = []
    for i in range(days):
        date = start + timedelta(days=i)
        # weekday bump + random noise
        weekday_factor = 1.15 if date.weekday() < 5 else 0.75
        count = int(base * weekday_factor + random.gauss(0, 15))
        count = max(0, count)
        history.append({"date": date.strftime("%Y-%m-%d"), "count": count})

    return history


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    history = generate_mock_history()
    payload = {"history": history}

    print(f"{'='*60}")
    print(f"  Test: POST {API_URL}")
    print(f"  Sending {len(history)} days of mock footfall data")
    print(f"{'='*60}\n")

    # ── Send request ─────────────────────────────────────────────────────
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
    except requests.ConnectionError:
        print("ERROR: Could not connect to the server at", API_URL)
        print("       Is `uvicorn main:app --reload` running?")
        sys.exit(2)
    except requests.RequestException as exc:
        print(f"ERROR: Request failed — {exc}")
        sys.exit(2)

    # ── Check status ─────────────────────────────────────────────────────
    print(f"Status code : {resp.status_code}")

    if resp.status_code != 200:
        print(f"FAIL: Expected 200 OK, got {resp.status_code}")
        print(f"Response body:\n{resp.text}")
        sys.exit(1)

    print("PASS: Received 200 OK\n")

    # ── Parse and validate JSON ──────────────────────────────────────────
    data = resp.json()
    print("Response JSON (pretty):")
    print(json.dumps(data, indent=2))
    print()

    # Check required keys
    for key in ("method", "horizon_days", "input_points", "predictions"):
        assert key in data, f"FAIL: Missing key '{key}' in response"
    print("PASS: All required keys present")

    # Check prediction count
    predictions = data["predictions"]
    actual_count = len(predictions)
    assert actual_count == EXPECTED_PREDICTIONS, (
        f"FAIL: Expected {EXPECTED_PREDICTIONS} predictions, got {actual_count}"
    )
    print(f"PASS: Exactly {EXPECTED_PREDICTIONS} prediction days returned")

    # Check input_points reflects what we sent
    assert data["input_points"] == HISTORY_DAYS, (
        f"FAIL: input_points is {data['input_points']}, expected {HISTORY_DAYS}"
    )
    print(f"PASS: input_points == {HISTORY_DAYS}")

    # Check method (30 points > 14 → Prophet, or fallback SMA if Prophet uninstalled)
    assert data["method"] in ("prophet", "sma"), (
        f"FAIL: method is '{data['method']}', expected 'prophet' or fallback 'sma'"
    )
    print(f"PASS: method == '{data['method']}' (valid forecasting engine)")

    # Check each prediction has required fields
    for i, pred in enumerate(predictions):
        for field in ("date", "predicted_count"):
            assert field in pred, f"FAIL: prediction[{i}] missing '{field}'"
    print("PASS: Every prediction contains 'date' and 'predicted_count'\n")

    print("=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
