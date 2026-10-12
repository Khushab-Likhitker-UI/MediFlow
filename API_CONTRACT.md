# API Contract — Smart Health Backend

> ⚠️ **NOTICE FOR IMPLEMENTATION TEAMS:**  
> For the authoritative Smart Health Sentinel redesign contract (including all new Phase 1 routes, role permissions, transfer workflows, and alerts), refer to [docs/implementation/API_CONTRACT.md](file:///d:/Smart_Health/docs/implementation/API_CONTRACT.md).  
> This root document is retained as a reference for the original 5 legacy endpoints.

> **Base URL:** `http://localhost:8000`  
> **Interactive Docs:** `http://localhost:8000/docs`  
> **All request/response bodies are JSON.**  
> **All timestamps follow ISO 8601 format.**

---

## Table of Contents

| # | Endpoint | Method | Tag |
|---|----------|--------|-----|
| 1 | [`/api/predict`](#1-post-apipredict) | `POST` | Footfall Prediction |
| 2 | [`/api/predict-shortage`](#2-post-apipredict-shortage) | `POST` | Shortage Prediction |
| 3 | [`/api/v1/predictions/demand`](#3-post-apiv1predictionsdemand) | `POST` | Supply Demand Forecast |
| 4 | [`/api/v1/inventory/update`](#4-post-apiv1inventoryupdate) | `POST` | Stock Update |
| 5 | [`/api/v1/inventory/status/{phc_id}`](#5-get-apiv1inventorystatusphc_id) | `GET` | PHC Stock Status |

---

## 1. `POST /api/predict`

Forecasts **patient footfall** for the next 7 days from historical daily records.

- Uses **Facebook Prophet** when ≥ 14 records are supplied.
- Falls back to a **Simple Moving Average (±20 % bounds)** for smaller datasets.

### Request Body

```json
{
  "footfall_data": [
    { "phc_id": "PHC-001", "date": "2026-06-01", "patient_count": 112 },
    { "phc_id": "PHC-001", "date": "2026-06-02", "patient_count": 98  },
    { "phc_id": "PHC-001", "date": "2026-06-03", "patient_count": 134 }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `footfall_data` | `array` | ✅ | At least 1 entry required |
| `footfall_data[].phc_id` | `string` | ✅ | Primary Health Centre identifier |
| `footfall_data[].date` | `string` | ✅ | Format: `YYYY-MM-DD` |
| `footfall_data[].patient_count` | `integer` | ✅ | Must be ≥ 0 |

### Response Body — `200 OK`

```json
{
  "predictions": [
    { "date": "2026-07-07", "predicted_count": 119, "lower_bound": 95,  "upper_bound": 143 },
    { "date": "2026-07-08", "predicted_count": 125, "lower_bound": 100, "upper_bound": 150 },
    { "date": "2026-07-09", "predicted_count": 108, "lower_bound": 86,  "upper_bound": 130 },
    { "date": "2026-07-10", "predicted_count": 131, "lower_bound": 105, "upper_bound": 157 },
    { "date": "2026-07-11", "predicted_count": 122, "lower_bound": 98,  "upper_bound": 146 },
    { "date": "2026-07-12", "predicted_count": 117, "lower_bound": 94,  "upper_bound": 140 },
    { "date": "2026-07-13", "predicted_count": 128, "lower_bound": 102, "upper_bound": 154 }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `predictions` | `array` | Always 7 items — one per day |
| `predictions[].date` | `string` | `YYYY-MM-DD` |
| `predictions[].predicted_count` | `integer` | Central forecast value |
| `predictions[].lower_bound` | `number` | 80 % confidence lower bound |
| `predictions[].upper_bound` | `number` | 80 % confidence upper bound |

### Error Responses

| Status | Meaning |
|---|---|
| `422 Unprocessable Entity` | Validation error (e.g. negative count, bad date format) |
| `500 Internal Server Error` | ML model failure — `detail` field describes the cause |

---

## 2. `POST /api/predict-shortage`

Predicts a **patient footfall shortage** for the next 7 days.  
Same Prophet / SMA logic as endpoint 1 but accepts a simpler payload (no `phc_id`).

### Request Body

```json
{
  "history": [
    { "date": "2026-06-01", "count": 112 },
    { "date": "2026-06-02", "count": 98  },
    { "date": "2026-06-03", "count": 134 }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `history` | `array` | ✅ | At least 1 entry required |
| `history[].date` | `string` | ✅ | Format: `YYYY-MM-DD` |
| `history[].count` | `integer` | ✅ | Must be ≥ 0 |

### Response Body — `200 OK`

```json
{
  "forecast": [
    { "date": "2026-07-07", "predicted_count": 119 },
    { "date": "2026-07-08", "predicted_count": 125 },
    { "date": "2026-07-09", "predicted_count": 108 },
    { "date": "2026-07-10", "predicted_count": 131 },
    { "date": "2026-07-11", "predicted_count": 122 },
    { "date": "2026-07-12", "predicted_count": 117 },
    { "date": "2026-07-13", "predicted_count": 128 }
  ],
  "method": "prophet"
}
```

| Field | Type | Notes |
|---|---|---|
| `forecast` | `array` | 7-day outlook |
| `forecast[].date` | `string` | `YYYY-MM-DD` |
| `forecast[].predicted_count` | `integer` | Forecasted patient visits |
| `method` | `string` | `"prophet"` or `"moving_average"` |

### Error Responses

| Status | Meaning |
|---|---|
| `422 Unprocessable Entity` | Invalid input — check `detail` for field-level errors |

---

## 3. `POST /api/v1/predictions/demand`

Runs the **supply-item demand forecast** and anomaly detection for a specific inventory item.

- Forecast model: **Facebook Prophet**
- Anomaly detection: **Isolation Forest**

### Request Body

```json
{
  "item_id": 3,
  "horizon_days": 30
}
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `item_id` | `integer` | ✅ | — | Must match an existing inventory item |
| `horizon_days` | `integer` | ❌ | `30` | Range: 1 – 365 |

### Response Body — `200 OK`

```json
{
  "item_id": 3,
  "item_name": "Ibuprofen 200mg",
  "forecasted_demand": [
    { "date": "2026-07-07", "predicted_quantity": 18 },
    { "date": "2026-07-08", "predicted_quantity": 22 },
    { "date": "2026-07-09", "predicted_quantity": 15 }
  ],
  "anomaly_flags": [
    {
      "date": "2026-06-28",
      "quantity": 340,
      "is_anomaly": true,
      "score": -0.42
    }
  ],
  "generated_at": "2026-07-06T06:30:00.000000"
}
```

| Field | Type | Notes |
|---|---|---|
| `item_id` | `integer` | Echoed from the request |
| `item_name` | `string` | Human-readable name of the item |
| `forecasted_demand` | `array` | One entry per day up to `horizon_days` |
| `forecasted_demand[].date` | `string` | `YYYY-MM-DD` |
| `forecasted_demand[].predicted_quantity` | `number` | Daily predicted consumption |
| `anomaly_flags` | `array \| null` | `null` if no anomaly data is available |
| `anomaly_flags[].date` | `string` | Date of the detected anomaly |
| `anomaly_flags[].quantity` | `number` | Observed quantity at that date |
| `anomaly_flags[].is_anomaly` | `boolean` | `true` = flagged as anomalous |
| `anomaly_flags[].score` | `number` | Isolation Forest score — more negative = more anomalous |
| `generated_at` | `string` | UTC timestamp of response generation |

### Error Responses

| Status | Meaning |
|---|---|
| `404 Not Found` | `item_id` does not exist in the inventory |
| `422 Unprocessable Entity` | `horizon_days` out of range or wrong type |

---

## 4. `POST /api/v1/inventory/update`

Logs a **medicine stock update** for a Primary Health Centre.

> **Note for frontend:** The backend currently prints the update to the console and returns an acknowledgement.  
> Full database persistence will be wired in by **Member 4**.

### Request Body

```json
{
  "phc_id": "PHC-001",
  "medicine_name": "Paracetamol",
  "quantity": 450,
  "timestamp": "2026-07-06T06:30:00Z"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `phc_id` | `string` | ✅ | Primary Health Centre identifier (e.g. `"PHC-001"`) |
| `medicine_name` | `string` | ✅ | Name of the medicine being updated |
| `quantity` | `integer` | ✅ | Current stock quantity — must be a whole number |
| `timestamp` | `string` | ✅ | ISO 8601 datetime recording when the update occurred |

### Response Body — `200 OK`

```json
{
  "status": "success",
  "message": "Stock logged"
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `string` | Always `"success"` on a valid request |
| `message` | `string` | Human-readable confirmation |

### Error Responses

| Status | Meaning |
|---|---|
| `422 Unprocessable Entity` | Missing or invalid fields — check `detail` for field-level errors |

---

## 5. `GET /api/v1/inventory/status/{phc_id}`

Returns the **current stock levels** for Paracetamol, ORS, and Anti-venom at the requested PHC.

### URL Parameter

| Parameter | Type | Required | Example |
|---|---|---|---|
| `phc_id` | `string` | ✅ | `PHC-001`, `PHC-002`, `PHC-003` |

> The value is **case-insensitive** — `phc-001` and `PHC-001` resolve to the same data.  
> Unknown PHC IDs return default stock values (no 404).

### Example Request

```
GET /api/v1/inventory/status/PHC-001
```

No request body required.

### Response Body — `200 OK`

```json
{
  "phc_id": "PHC-001",
  "stock": {
    "Paracetamol": {
      "quantity": 520,
      "unit": "tablets",
      "reorder_level": 200,
      "status": "adequate"
    },
    "ORS": {
      "quantity": 85,
      "unit": "sachets",
      "reorder_level": 100,
      "status": "low"
    },
    "Anti-venom": {
      "quantity": 12,
      "unit": "vials",
      "reorder_level": 10,
      "status": "adequate"
    }
  },
  "last_updated": "2026-07-06T06:30:00Z"
}
```

| Field | Type | Notes |
|---|---|---|
| `phc_id` | `string` | Normalised to uppercase |
| `stock` | `object` | Keys are medicine names |
| `stock[medicine].quantity` | `integer` | Units currently in stock |
| `stock[medicine].unit` | `string` | `"tablets"`, `"sachets"`, or `"vials"` |
| `stock[medicine].reorder_level` | `integer` | Threshold below which a reorder is triggered |
| `stock[medicine].status` | `string` | See status values below |
| `last_updated` | `string` | UTC timestamp of the response |

#### Stock `status` Values

| Value | Meaning | Suggested UI colour |
|---|---|---|
| `"adequate"` | Stock is above the reorder level | 🟢 Green |
| `"low"` | Stock is at or below the reorder level | 🟡 Amber |
| `"critical"` | Stock is at zero or dangerously low | 🔴 Red |

---

## Common Error Shape

All error responses follow FastAPI's standard format:

```json
{
  "detail": "Inventory item not found"
}
```

For validation errors (`422`), `detail` is an array of objects:

```json
{
  "detail": [
    {
      "loc": ["body", "quantity"],
      "msg": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

---

## Quick Reference

```
POST  /api/predict                         → 7-day footfall forecast  (DailyFootfall payload)
POST  /api/predict-shortage                → 7-day shortage forecast  (simple history payload)
POST  /api/v1/predictions/demand           → Supply demand forecast + anomaly detection
POST  /api/v1/inventory/update             → Log a PHC medicine stock update
GET   /api/v1/inventory/status/{phc_id}   → Current stock levels for Paracetamol, ORS, Anti-venom
```
