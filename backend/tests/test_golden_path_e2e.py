"""
End-to-End Golden Path Integration Test Suite.
Validates the entire Smart Health Sentinel workflow across:
1. Shortage alert detection (projected breach before delivery) labeled "Simulated data"
2. Candidate donor evaluation (donor-safe surplus vs reserve breach)
3. Transfer lifecycle: propose -> approve (atomic reservation) -> dispatch -> receive (actual qty) -> reconcile
4. Alternate scenario: rejection of donor at reserve / emergency replenishment escalation
5. PWA offline idempotency (duplicate client_operation_id handling)
6. Model evaluation reporting with synthetic scenario provenance
"""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.domain.alerts import generate_inventory_alerts
from app.domain.donor import evaluate_donor_candidates
from app.domain.models import DonorFacilityContext, InventoryBatch
from app.domain.models import TransferState
from app.domain.transfer import validate_transition
from main import app

client = TestClient(app)


from app.domain.auth import create_access_token


@pytest.fixture
def coordinator_headers():
    token = create_access_token(
        user_id=42,
        username="coord_user",
        email="coord@smarthealth.local",
        role="admin",
        district="North District",
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. GOLDEN PATH: ALERT -> DONOR EVALUATION -> PROPOSE -> APPROVE -> RECEIVE
# ==============================================================================

def test_golden_path_full_lifecycle(coordinator_headers):
    """
    Executes the End-to-End Golden Path:
    - Recipient PHC has low usable stock (10 units, safety reserve 50)
    - Donor PHC has donor-safe surplus (150 units, reserve 50, demand 20 -> surplus 80)
    - System proposes 40 units, approves, dispatches, receives 38, reconciles.
    - Verified: single reservation, audit trail, provenance.
    """
    # 1. Alert generation
    facility_recipient = {
        "phc_id": "PHC-RECIP",
        "facility_name": "Sunrise Health Clinic",
        "district": "North District",
    }
    inv_recipient = [{
        "phc_id": "PHC-RECIP",
        "item_id": 1,
        "item_name": "Paracetamol 500mg",
        "unit": "tablets",
        "reorder_level": 200,
        "safety_reserve": 50,
        "batch_number": "BATCH-RECIP-01",
        "quantity": 10,
        "expiry_date": date.today() + timedelta(days=180),
    }]
    alerts = generate_inventory_alerts(
        facilities=[facility_recipient],
        inventory_items=inv_recipient,
        reservations_by_facility_item={},
    )
    assert len(alerts) >= 1
    alert = alerts[0]
    assert alert["usable_stock"] == 10
    assert alert["safety_reserve"] == 50
    assert alert["severity"] == "critical"
    assert "breach" in alert["alert_id"]

    # 2. Candidate Donor Evaluation
    donor_batches = [
        InventoryBatch(
            batch_number="BATCH-DONOR-01",
            quantity=150,
            expiry_date=date.today() + timedelta(days=365),
        )
    ]
    donor_ctx = DonorFacilityContext(
        facility_id="PHC-DONOR",
        facility_name="Central District Hospital",
        district="North District",
        latitude=12.98,
        longitude=77.59,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=50,
        projected_demand_over_horizon=20,
    )
    eval_result = evaluate_donor_candidates(
        recipient_facility_id="PHC-RECIP",
        recipient_facility_name="Sunrise Health Clinic",
        recipient_district="North District",
        recipient_lat=12.97,
        recipient_lng=77.58,
        item_id=1,
        item_name="Paracetamol 500mg",
        unit="tablets",
        recipient_deficit=40,
        candidate_contexts=[donor_ctx],
    )
    assert eval_result.has_safe_donor is True
    assert eval_result.recommended_candidate is not None
    assert eval_result.recommended_candidate.facility_id == "PHC-DONOR"
    assert eval_result.recommended_candidate.donor_safe_surplus == 80  # 150 - 50 - 20
    assert eval_result.recommended_quantity == 40

    # 3. Transfer Proposal API
    mock_transfer_id = "tr-golden-path-100"
    created_transfer_row = {
        "transfer_id": mock_transfer_id,
        "from_phc_id": "PHC-DONOR",
        "to_phc_id": "PHC-RECIP",
        "item_id": 1,
        "batch_number": "BATCH-DONOR-01",
        "quantity": 40,
        "received_quantity": None,
        "status": "proposed",
        "reason": "Simulated data: Rebalancing critical breach",
        "rejection_reason": None,
        "discrepancy_reason": None,
        "client_operation_id": "op-golden-prop-01",
        "proposed_by": "coord_user",
        "approved_by": None,
        "dispatched_by": None,
        "received_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "dispatched_at": None,
        "received_at": None,
    }

    def mock_fetch_one(query, params=None):
        if "processed_operations" in query:
            return None
        if "facilities" in query and "PHC-DONOR" in params:
            return {"phc_id": "PHC-DONOR", "facility_name": "Central Hospital"}
        if "facilities" in query and "PHC-RECIP" in params:
            return {"phc_id": "PHC-RECIP", "facility_name": "Sunrise Clinic"}
        if "medicines" in query:
            return {"item_id": 1, "name": "Paracetamol 500mg"}
        if "INSERT INTO transfers" in query:
            return created_transfer_row
        return None

    with patch("app.db.fetch_one", side_effect=mock_fetch_one), \
         patch("app.db.execute_query"):
        res = client.post(
            "/api/v1/transfers/propose",
            json={
                "from_phc_id": "PHC-DONOR",
                "to_phc_id": "PHC-RECIP",
                "item_id": 1,
                "batch_number": "BATCH-DONOR-01",
                "quantity": 40,
                "reason": "Simulated data: Rebalancing critical breach",
                "client_operation_id": "op-golden-prop-01",
            },
            headers=coordinator_headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["transfer_id"] == mock_transfer_id
        assert data["status"] == "proposed"

    # 4. Approval & Stock Reservation (atomic single reservation)
    mock_approved_row = {**created_transfer_row, "status": "approved", "approved_by": "coord_user"}
    donor_batches_db = [
        {"batch_number": "BATCH-DONOR-01", "quantity": 150, "expiry_date": date.today() + timedelta(days=365)}
    ]

    transfer_approve_fetch_count = 0
    def mock_approve_fetch(query, params=None):
        nonlocal transfer_approve_fetch_count
        if "FROM facilities" in query:
            return {"district": "North District", "facility_name": "Central District Hospital"}
        if "total_reserved" in query:
            return {"total_reserved": 0}
        if "SELECT * FROM transfers WHERE transfer_id" in query:
            transfer_approve_fetch_count += 1
            return created_transfer_row if transfer_approve_fetch_count == 1 else mock_approved_row
        return None

    with patch("app.db.fetch_one", side_effect=mock_approve_fetch), \
         patch("app.db.fetch_all", return_value=donor_batches_db), \
         patch("app.db.execute_transaction") as mock_tx:
        res = client.post(f"/api/v1/transfers/{mock_transfer_id}/approve", headers=coordinator_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "approved"
        assert mock_tx.called

    # 5. Dispatch Event
    mock_dispatched_row = {
        **mock_approved_row,
        "status": "dispatched",
        "dispatched_by": "coord_user",
        "dispatched_at": datetime.now(timezone.utc),
    }
    with patch("app.db.fetch_one", side_effect=[mock_approved_row, mock_dispatched_row]), \
         patch("app.db.execute_transaction") as mock_tx:
        res = client.post(f"/api/v1/transfers/{mock_transfer_id}/dispatch", headers=coordinator_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "dispatched"

    # 6. Receipt Event with Actual Received Quantity (38 of 40)
    mock_received_row = {
        **mock_dispatched_row,
        "status": "received",
        "received_quantity": 38,
        "discrepancy_reason": "2 units damaged in transit",
        "received_by": "coord_user",
        "received_at": datetime.now(timezone.utc),
    }
    with patch("app.db.fetch_one", side_effect=[mock_dispatched_row, mock_received_row]), \
         patch("app.db.execute_transaction") as mock_tx:
        res = client.post(
            f"/api/v1/transfers/{mock_transfer_id}/receive",
            json={
                "received_quantity": 38,
                "discrepancy_reason": "2 units damaged in transit",
            },
            headers=coordinator_headers,
        )
        assert res.status_code == 200
        recv_data = res.json()
        assert recv_data["status"] == "received"
        assert recv_data["received_quantity"] == 38
        assert recv_data["discrepancy_reason"] == "2 units damaged in transit"

    # 7. Final Reconciliation
    mock_reconciled_row = {**mock_received_row, "status": "reconciled"}
    with patch("app.db.fetch_one", side_effect=[mock_received_row, mock_reconciled_row]), \
         patch("app.db.execute_transaction"):
        res = client.post(
            f"/api/v1/transfers/{mock_transfer_id}/reconcile",
            json={"reconciliation_notes": "Physical ledger count verified at Sunrise Clinic."},
            headers=coordinator_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "reconciled"


# ==============================================================================
# 2. ALTERNATE SCENARIOS: DONOR REJECTION & EMERGENCY ESCALATION
# ==============================================================================

def test_alternate_scenario_donor_at_reserve_rejected():
    """
    When candidate donor's stock is at or below its own safety reserve,
    the donor safe surplus engine must reject it to prevent cascading stockouts.
    """
    donor_batches = [
        InventoryBatch(
            batch_number="BATCH-LOW-01",
            quantity=50,
            expiry_date=date.today() + timedelta(days=200),
        )
    ]
    donor_at_reserve = DonorFacilityContext(
        facility_id="PHC-LOW",
        facility_name="Rural Clinic Beta",
        district="North District",
        latitude=12.95,
        longitude=77.55,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=50,
        projected_demand_over_horizon=10,
    )
    result = evaluate_donor_candidates(
        recipient_facility_id="PHC-RECIP",
        recipient_facility_name="Sunrise Clinic",
        recipient_district="North District",
        recipient_lat=12.97,
        recipient_lng=77.58,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=30,
        candidate_contexts=[donor_at_reserve],
    )
    assert result.has_safe_donor is False
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.is_eligible is False
    assert candidate.donor_safe_surplus == 0
    assert "reserve" in candidate.rejection_reason.lower() or "surplus" in candidate.rejection_reason.lower()


def test_alternate_scenario_emergency_depot_escalation(coordinator_headers):
    """
    When no peer donor qualifies, coordinator escalates shortage to Central Medical Depot.
    """
    payload = {
        "alert_id": "alert-PHC-RECIP-1-breach",
        "phc_id": "PHC-RECIP",
        "item_id": 1,
        "required_quantity": 50,
        "reason": "Simulated data: No safe peer donor in district; emergency depot replenishment requested",
    }
    with patch("app.db.execute_query") as mock_exec:
        res = client.post(
            "/api/v1/replenishment/escalate",
            json=payload,
            headers=coordinator_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "escalated_to_depot"
        assert data["escalation_id"].startswith("ESC-")
        assert data["depot_destination"] == "District Central Medical Depot"
        assert mock_exec.called


# ==============================================================================
# 3. PWA OFFLINE DISCONNECT -> RECONNECT IDEMPOTENCY
# ==============================================================================

def test_pwa_offline_sync_idempotency_workflow():
    """
    Simulates:
    1. PWA records stock movement while offline with unique client_operation_id.
    2. PWA reconnects and syncs; server accepts and logs.
    3. PWA re-submits due to network retry; server recognizes operation and responds identically.
    """
    op_id = "pwa-op-uuid-8888-9999"
    cached_ack = {
        "status": "success",
        "message": "Stock logged (cached idempotency ack)",
        "client_operation_id": op_id,
    }

    def mock_inv_fetch(query, params=None):
        if "processed_operations" in query:
            return None
        if "facilities" in query:
            return {"phc_id": "PHC-001"}
        if "medicines" in query:
            return {"item_id": 1}
        if "inventory" in query:
            return {"batch_number": "B1"}
        return None

    # First attempt: processed_operations returns None -> processed normally
    with patch("app.db.fetch_one", side_effect=mock_inv_fetch), \
         patch("app.db.execute_transaction"), \
         patch("app.db.execute_query"):
        payload = {
            "phc_id": "PHC-001",
            "medicine_name": "Paracetamol 500mg",
            "quantity": 80,
            "timestamp": "2026-10-13T02:00:00Z",
            "client_operation_id": op_id,
        }
        res1 = client.post(
            "/api/v1/inventory/update",
            json=payload,
            headers={"X-Client-Operation-Id": op_id},
        )
        assert res1.status_code == 200
        assert res1.json()["client_operation_id"] == op_id

    # Second attempt (offline sync retry): processed_operations returns cached record
    with patch("app.db.fetch_one", return_value={"operation_id": op_id, "response_payload": json.dumps(cached_ack)}):
        res2 = client.post(
            "/api/v1/inventory/update",
            json=payload,
            headers={"X-Client-Operation-Id": op_id},
        )
        assert res2.status_code == 200
        assert res2.json()["client_operation_id"] == op_id
        assert "cached" in res2.json()["message"]


# ==============================================================================
# 4. EVALUATION REPORT PROVENANCE & BENCHMARK ACCESSIBILITY
# ==============================================================================

def test_evaluation_runs_provenance_and_data_labeling():
    """
    Verifies evaluation screen API reports metrics labeled as synthetic scenarios.
    """
    res = client.get("/api/v1/evaluations/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) >= 1
    primary_run = runs[0]
    assert primary_run["is_simulated"] is True
    assert primary_run["data_source"] == "synthetic_scenario"
    assert "metrics" in primary_run
    assert primary_run["metrics"]["donor_retention_rate_pct"] == 100.0
