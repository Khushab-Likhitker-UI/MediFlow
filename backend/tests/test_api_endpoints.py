"""
API Contract and Integration tests for Sentinel endpoints:
- Authentication & JWT token validation
- Transfer propose, approve, reject, dispatch, receive
- Idempotency via client_operation_id
- Shortage alerts listing
- Batch-level facility inventory
"""

import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.domain.auth import create_access_token
from main import app

client = TestClient(app)


@pytest.fixture
def admin_token():
    return create_access_token(
        user_id=1,
        username="admin",
        email="admin@smarthealth.local",
        role="admin",
    )


@pytest.fixture
def manager_token():
    return create_access_token(
        user_id=2,
        username="manager1",
        email="manager1@smarthealth.local",
        role="manager",
        district="Central District",
    )


@pytest.fixture
def viewer_token():
    return create_access_token(
        user_id=3,
        username="viewer1",
        email="viewer1@smarthealth.local",
        role="viewer",
    )


# ── 1. Auth Endpoint Tests ───────────────────────────────────────────────────

def test_login_success():
    """Verify login returns signed JWT token and user details."""
    mock_user = {
        "id": 1,
        "username": "admin",
        "email": "admin@smarthealth.local",
        "role": "admin",
        "password_hash": "$2b$12$e80yE6kImsaLq1yQo5W1kOu5U4bE9n8Y.v1/6mQyH1tXj7U9K0L8i",
        "is_active": True,
    }

    with patch("app.db.fetch_one", return_value=mock_user), \
         patch("app.routes.users.pwd_context.verify", return_value=True):
        res = client.post(
            "/api/v1/users/login",
            json={"email": "admin@smarthealth.local", "password": "password123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "admin@smarthealth.local"
        assert data["role"] == "admin"
        assert "token" in data
        assert "access_token" in data
        assert data["token_type"] == "bearer"


def test_login_invalid_credentials():
    """Invalid password returns 401."""
    mock_user = {
        "id": 1,
        "username": "admin",
        "email": "admin@smarthealth.local",
        "role": "admin",
        "password_hash": "$2b$12$xyz",
        "is_active": True,
    }

    with patch("app.db.fetch_one", return_value=mock_user), \
         patch("app.routes.users.pwd_context.verify", return_value=False):
        res = client.post(
            "/api/v1/users/login",
            json={"email": "admin@smarthealth.local", "password": "wrongpassword"},
        )
        assert res.status_code == 401


def test_protected_me_endpoint(admin_token):
    """GET /users/me validates the Bearer token claims."""
    res = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


# ── 2. Transfer Endpoint Tests ───────────────────────────────────────────────

def test_propose_transfer_success(admin_token):
    """Proposing a transfer creates record in proposed state."""
    mock_source = {"phc_id": "PHC-001", "facility_name": "PHC Alpha", "district": "Central"}
    mock_dest = {"phc_id": "PHC-002", "facility_name": "PHC Beta", "district": "Central"}
    mock_med = {"item_id": 1, "name": "Paracetamol 500mg", "unit": "tablets"}

    created_row = {
        "transfer_id": "11111111-1111-1111-1111-111111111111",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 50,
        "received_quantity": None,
        "status": "proposed",
        "reason": "Rebalancing surplus",
        "rejection_reason": None,
        "discrepancy_reason": None,
        "client_operation_id": "550e8400-e29b-41d4-a716-446655440000",
        "proposed_by": "admin",
        "approved_by": None,
        "dispatched_by": None,
        "received_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "dispatched_at": None,
        "received_at": None,
    }

    def mock_fetch(query, params=None):
        if "processed_operations" in query:
            return None
        if "facilities" in query and "PHC-001" in params:
            return mock_source
        if "facilities" in query and "PHC-002" in params:
            return mock_dest
        if "medicines" in query:
            return mock_med
        if "INSERT INTO transfers" in query:
            return created_row
        return None

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.execute_query", return_value=None):
        payload = {
            "from_phc_id": "PHC-001",
            "to_phc_id": "PHC-002",
            "item_id": 1,
            "batch_number": "B1",
            "quantity": 50,
            "reason": "Rebalancing surplus",
            "client_operation_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        res = client.post(
            "/api/v1/transfers/propose",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["transfer_id"] == "11111111-1111-1111-1111-111111111111"
        assert data["status"] == "proposed"
        assert data["quantity"] == 50


def test_propose_transfer_idempotency(admin_token):
    """Submitting duplicate client_operation_id returns cached response."""
    cached_payload = {
        "transfer_id": "cached-id-123",
        "from_phc_id": "PHC-001",
        "from_facility_name": "PHC Alpha",
        "to_phc_id": "PHC-002",
        "to_facility_name": "PHC Beta",
        "item_id": 1,
        "item_name": "Paracetamol",
        "batch_number": "B1",
        "quantity": 50,
        "received_quantity": None,
        "status": "proposed",
        "reason": "Prior submission",
        "rejection_reason": None,
        "discrepancy_reason": None,
        "client_operation_id": "op-dup-uuid-1",
        "proposed_by": "admin",
        "approved_by": None,
        "dispatched_by": None,
        "received_by": None,
        "created_at": "2026-10-13T00:00:00Z",
        "updated_at": "2026-10-13T00:00:00Z",
        "dispatched_at": None,
        "received_at": None,
    }

    mock_cached_row = {
        "operation_id": "op-dup-uuid-1",
        "response_payload": json.dumps(cached_payload),
    }

    with patch("app.db.fetch_one", return_value=mock_cached_row):
        payload = {
            "from_phc_id": "PHC-001",
            "to_phc_id": "PHC-002",
            "item_id": 1,
            "quantity": 50,
            "client_operation_id": "op-dup-uuid-1",
        }
        res = client.post(
            "/api/v1/transfers/propose",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["transfer_id"] == "cached-id-123"


def test_propose_self_transfer_rejected(admin_token):
    """Self transfers (from_phc == to_phc) must return 400."""
    payload = {
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-001",
        "item_id": 1,
        "quantity": 10,
    }
    res = client.post(
        "/api/v1/transfers/propose",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "identical" in res.json()["detail"].lower()


def test_approve_transfer_success(admin_token):
    """Approving transfer reserves stock and transitions state to approved."""
    transfer_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 30,
        "status": "proposed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    approved_row = {
        **transfer_row,
        "status": "approved",
        "approved_by": "admin",
    }

    donor_batches = [
        {"batch_number": "B1", "quantity": 100, "expiry_date": date(2027, 1, 1)}
    ]

    transfer_fetch_count = 0
    def mock_fetch(query, params=None):
        nonlocal transfer_fetch_count
        if "FROM facilities" in query:
            return {"district": "Central", "facility_name": "PHC Alpha"}
        if "total_reserved" in query:
            return {"total_reserved": 0}
        if "SELECT * FROM transfers WHERE transfer_id" in query:
            transfer_fetch_count += 1
            return transfer_row if transfer_fetch_count == 1 else approved_row
        return None

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.fetch_all", return_value=donor_batches), \
         patch("app.db.execute_transaction", return_value=None):
        res = client.post(
            "/api/v1/transfers/t-1/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "approved"


def test_approve_transfer_insufficient_stock_fails(admin_token):
    """If donor usable stock is lower than transfer quantity, approval returns 409."""
    transfer_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 100,  # Requested 100
        "status": "proposed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    # Donor only has 40 units
    donor_batches = [
        {"batch_number": "B1", "quantity": 40, "expiry_date": date(2027, 1, 1)}
    ]

    def mock_fetch(query, params=None):
        if "SELECT * FROM transfers" in query:
            return transfer_row
        if "FROM facilities" in query:
            return {"district": "Central", "facility_name": "PHC Alpha"}
        if "total_reserved" in query:
            return {"total_reserved": 0}
        return None

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.fetch_all", return_value=donor_batches):
        res = client.post(
            "/api/v1/transfers/t-1/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 409
        assert "insufficient" in res.json()["detail"].lower()


def test_reject_transfer_with_reason(admin_token):
    """Rejecting transfer transitions to rejected."""
    transfer_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 30,
        "status": "proposed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    rejected_row = {
        **transfer_row,
        "status": "rejected",
        "rejection_reason": "Stock reserved for local epidemic",
    }

    call_count = 0
    def mock_fetch(query, params=None):
        nonlocal call_count
        call_count += 1
        return transfer_row if call_count == 1 else rejected_row

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.execute_query", return_value=None):
        res = client.post(
            "/api/v1/transfers/t-1/reject",
            json={"reason": "Stock reserved for local epidemic"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "rejected"
        assert res.json()["rejection_reason"] == "Stock reserved for local epidemic"


def test_dispatch_transfer_success(admin_token):
    """Dispatching approved transfer transitions state to dispatched."""
    approved_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 30,
        "status": "approved",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    dispatched_row = {
        **approved_row,
        "status": "dispatched",
        "dispatched_at": datetime.now(timezone.utc),
    }

    call_count = 0
    def mock_fetch(query, params=None):
        nonlocal call_count
        call_count += 1
        return approved_row if call_count == 1 else dispatched_row

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.execute_transaction", return_value=None):
        res = client.post(
            "/api/v1/transfers/t-1/dispatch",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "dispatched"


def test_receive_transfer_full_quantity(admin_token):
    """Receiving exact quantity marks transfer as reconciled."""
    dispatched_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 50,
        "status": "dispatched",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    reconciled_row = {
        **dispatched_row,
        "status": "reconciled",
        "received_quantity": 50,
        "received_at": datetime.now(timezone.utc),
    }

    call_count = 0
    def mock_fetch(query, params=None):
        nonlocal call_count
        call_count += 1
        return dispatched_row if call_count == 1 else reconciled_row

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.execute_transaction", return_value=None):
        res = client.post(
            "/api/v1/transfers/t-1/receive",
            json={"received_quantity": 50},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "reconciled"
        assert res.json()["received_quantity"] == 50


def test_receive_transfer_partial_discrepancy(admin_token):
    """Partial receipt records discrepancy reason and remains received."""
    dispatched_row = {
        "transfer_id": "t-1",
        "from_phc_id": "PHC-001",
        "to_phc_id": "PHC-002",
        "item_id": 1,
        "batch_number": "B1",
        "quantity": 50,
        "status": "dispatched",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    partial_row = {
        **dispatched_row,
        "status": "received",
        "received_quantity": 40,
        "discrepancy_reason": "10 vials broken during transit",
        "received_at": datetime.now(timezone.utc),
    }

    call_count = 0
    def mock_fetch(query, params=None):
        nonlocal call_count
        call_count += 1
        return dispatched_row if call_count == 1 else partial_row

    with patch("app.db.fetch_one", side_effect=mock_fetch), \
         patch("app.db.execute_transaction", return_value=None):
        res = client.post(
            "/api/v1/transfers/t-1/receive",
            json={
                "received_quantity": 40,
                "discrepancy_reason": "10 vials broken during transit",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "received"
        assert res.json()["received_quantity"] == 40
        assert res.json()["discrepancy_reason"] == "10 vials broken during transit"


# ── 3. Stock Movements Endpoint Tests ────────────────────────────────────────

def test_stock_movement_idempotent_deduplication():
    """Stock movement endpoint deduplicates requests by client_operation_id."""
    cached_payload = {
        "client_operation_id": "op-pwa-sync-99",
        "status": "synced",
        "message": "Stock movement 'dispensed' recorded successfully.",
        "current_usable_stock": 85,
        "acknowledged_at": "2026-10-13T00:00:00Z",
    }

    mock_cached_row = {
        "operation_id": "op-pwa-sync-99",
        "response_payload": json.dumps(cached_payload),
    }

    with patch("app.db.fetch_one", return_value=mock_cached_row):
        payload = {
            "client_operation_id": "op-pwa-sync-99",
            "phc_id": "PHC-001",
            "item_id": 1,
            "movement_type": "dispensed",
            "quantity": 15,
        }
        res = client.post("/api/v1/stock-movements", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["client_operation_id"] == "op-pwa-sync-99"
        assert data["current_usable_stock"] == 85
        assert data["status"] == "synced"


# ── 4. Alerts Endpoint Tests ─────────────────────────────────────────────────

def test_list_alerts_endpoint():
    """GET /alerts/ returns computed alerts."""
    mock_facs = [{"phc_id": "PHC-001", "facility_name": "PHC One", "district": "District A"}]
    mock_inv = [
        {
            "phc_id": "PHC-001",
            "item_id": 1,
            "item_name": "ORS Packets",
            "unit": "sachets",
            "reorder_level": 500,
            "safety_reserve": 50,
            "batch_number": "B1",
            "quantity": 0,  # Depleted
            "expiry_date": date(2027, 1, 1),
        }
    ]

    with patch("app.db.fetch_all", side_effect=[mock_facs, mock_inv, []]):
        res = client.get("/api/v1/alerts/?phc_id=PHC-001")
        assert res.status_code == 200
        alerts = res.json()
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"
        assert alerts[0]["type"] == "critical_stock"


def test_reconcile_transfer_endpoint(manager_token):
    """POST /transfers/{id}/reconcile transitions status to reconciled."""
    transfer_id = "tr-reconcile-01"
    mock_transfer = {
        "transfer_id": transfer_id,
        "from_phc_id": "PHC-002",
        "to_phc_id": "PHC-001",
        "item_id": 1,
        "quantity": 25,
        "status": "received",
        "created_at": datetime.now(timezone.utc),
    }
    mock_reconciled = {**mock_transfer, "status": "reconciled"}

    with patch("app.db.fetch_one", side_effect=[mock_transfer, mock_reconciled]), \
         patch("app.db.execute_transaction") as mock_tx:
        headers = {"Authorization": f"Bearer {manager_token}"}
        res = client.post(
            f"/api/v1/transfers/{transfer_id}/reconcile",
            json={"reconciliation_notes": "All counts verified against physical tally"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "reconciled"
        assert mock_tx.called


def test_alert_donor_candidates_endpoint():
    """GET /alerts/{alert_id}/donors evaluates candidate donors for deficit."""
    mock_alert_fac = [{"phc_id": "PHC-001", "facility_name": "Recipient PHC", "district": "District A"}]
    mock_alert_inv = [{
        "phc_id": "PHC-001", "item_id": 1, "item_name": "Paracetamol", "unit": "tablets",
        "reorder_level": 500, "safety_reserve": 50, "batch_number": "B1",
        "quantity": 10, "expiry_date": date(2027, 1, 1),
    }]
    mock_recip = {
        "phc_id": "PHC-001", "facility_name": "Recipient PHC", "district": "District A",
        "latitude": 12.97, "longitude": 77.59,
    }
    mock_med = {"item_id": 1, "name": "Paracetamol", "unit": "tablets"}
    mock_donor = {
        "phc_id": "PHC-002", "facility_name": "Donor Hospital", "district": "District A",
        "latitude": 13.00, "longitude": 77.60,
    }
    mock_donor_batches = [
        {"batch_number": "B-DONOR-1", "quantity": 150, "expiry_date": date(2027, 6, 1)}
    ]

    with patch("app.db.fetch_all", side_effect=[
        mock_alert_fac, mock_alert_inv, [],  # list_alerts inside get_alert
        [mock_donor],                         # other_facs
        mock_donor_batches,                   # donor batches
    ]), patch("app.db.fetch_one", side_effect=[
        mock_recip, mock_med, {"total": 0}    # recip, med, active reservations
    ]):
        res = client.get("/api/v1/alerts/alert-PHC-001-1-breach/donors")
        assert res.status_code == 200
        donors = res.json()
        assert isinstance(donors, list)
        assert len(donors) == 1
        assert donors[0]["donor_phc_id"] == "PHC-002"
        assert donors[0]["eligible"] is True
        assert donors[0]["transferable_quantity"] > 0


def test_replenishment_escalation_endpoint(manager_token):
    """POST /replenishment/escalate logs emergency depot escalation."""
    payload = {
        "alert_id": "ALT-2026-003",
        "phc_id": "PHC-006",
        "item_id": 8,
        "required_quantity": 50,
        "reason": "No safe donor available in district",
    }
    with patch("app.db.execute_query") as mock_exec:
        headers = {"Authorization": f"Bearer {manager_token}"}
        res = client.post("/api/v1/replenishment/escalate", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "escalated_to_depot"
        assert data["escalation_id"].startswith("ESC-")
        assert data["depot_destination"] == "District Central Medical Depot"
        assert mock_exec.called


def test_evaluations_runs_endpoints():
    """GET /evaluations/runs returns named benchmarks with synthetic provenance."""
    res = client.get("/api/v1/evaluations/runs")
    assert res.status_code == 200
    runs = res.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1
    run = runs[0]
    assert "run_id" in run
    assert run["is_simulated"] is True
    assert run["data_source"] == "synthetic_scenario"
    assert "metrics" in run
    assert run["metrics"]["shortage_prevention_rate_pct"] > 0
    assert run["metrics"]["donor_retention_rate_pct"] == 100.0


def test_inventory_update_idempotency():
    """POST /inventory/update honors client_operation_id for exact-once deduplication."""
    op_id = "op-idemp-update-999"
    cached = {"status": "success", "message": "Stock logged (cached idempotency ack)", "client_operation_id": op_id}

    with patch("app.db.fetch_one", return_value={"operation_id": op_id, "response_payload": json.dumps(cached)}):
        headers = {"X-Client-Operation-Id": op_id}
        payload = {
            "phc_id": "PHC-001",
            "medicine_name": "Paracetamol 500mg",
            "quantity": 100,
            "timestamp": "2026-10-12T10:00:00Z",
            "client_operation_id": op_id,
        }
        res = client.post("/api/v1/inventory/update", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["client_operation_id"] == op_id
        assert "cached" in res.json()["message"]


def test_idempotency_payload_mismatch_conflict():
    """POST /inventory/update returns HTTP 409 Conflict if operation UUID is reused with different parameters."""
    op_id = "op-conflict-uuid-123"
    stored = {
        "status": "success",
        "message": "Stock logged",
        "client_operation_id": op_id,
        "_request": {
            "phc_id": "PHC-001",
            "medicine_name": "Paracetamol 500mg",
            "quantity": 50,
        },
    }

    with patch("app.db.fetch_one", return_value={"operation_id": op_id, "phc_id": "PHC-001", "response_payload": json.dumps(stored)}):
        payload_conflicting = {
            "phc_id": "PHC-001",
            "medicine_name": "Paracetamol 500mg",
            "quantity": 200,  # Contradicts stored 50
            "timestamp": "2026-10-12T10:00:00Z",
            "client_operation_id": op_id,
        }
        res = client.post("/api/v1/inventory/update", json=payload_conflicting)
        assert res.status_code == 409
        assert "conflict" in res.json()["detail"].lower()


def test_stock_movement_payload_mismatch_conflict():
    """POST /stock-movements returns HTTP 409 Conflict if same operation ID is submitted with different payload."""
    op_id = "op-mov-conflict-456"
    stored = {
        "client_operation_id": op_id,
        "status": "synced",
        "message": "Recorded",
        "current_usable_stock": 100,
        "_request": {
            "phc_id": "PHC-001",
            "item_id": 1,
            "batch_number": "BATCH-01",
            "movement_type": "dispensed",
            "quantity": 10,
        },
    }

    with patch("app.db.fetch_one", return_value={"operation_id": op_id, "phc_id": "PHC-001", "response_payload": json.dumps(stored)}):
        conflicting_movement = {
            "client_operation_id": op_id,
            "phc_id": "PHC-001",
            "item_id": 1,
            "batch_number": "BATCH-01",
            "movement_type": "received",  # Differs from dispensed
            "quantity": 50,
        }
        res = client.post("/api/v1/stock-movements", json=conflicting_movement)
        assert res.status_code == 409
        assert "conflict" in res.json()["detail"].lower()


def test_user_management_role_enforcement():
    """GET /users/ and POST /users/ reject unauthenticated or non-admin users with 401/403."""
    # 1. Unauthenticated GET /users/
    res_unauth = client.get("/api/v1/users/")
    assert res_unauth.status_code in (401, 403)

    # 2. Authenticated as regular viewer
    from app.domain.auth import create_access_token
    viewer_token = create_access_token(user_id=10, username="guest", email="guest@phc.local", role="viewer")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    res_forbidden = client.get("/api/v1/users/", headers=viewer_headers)
    assert res_forbidden.status_code == 403
    assert "forbidden" in res_forbidden.json()["detail"].lower()


def test_inventory_mutations_require_roles():
    """POST /inventory/ and DELETE /inventory/{id} reject viewers with 403 Forbidden."""
    from app.domain.auth import create_access_token
    viewer_token = create_access_token(user_id=10, username="guest", email="guest@phc.local", role="viewer")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    item_payload = {
        "name": "Unauthorized Amoxicillin",
        "category": "Antibiotic",
        "quantity": 100,
        "unit": "capsules",
        "reorder_level": 50,
    }
    res_create = client.post("/api/v1/inventory/", json=item_payload, headers=viewer_headers)
    assert res_create.status_code == 403

    res_del = client.delete("/api/v1/inventory/99", headers=viewer_headers)
    assert res_del.status_code == 403


def test_alert_explanation_deterministic_fallback():
    """GET /alerts/{alert_id}/explanation returns structured narrative with deterministic fallback."""
    fake_alert = {
        "alert_id": "alert-PHC-001-1-shortage",
        "phc_id": "PHC-001",
        "facility_name": "Kengeri PHC",
        "district": "Bengaluru South",
        "item_id": 1,
        "item_name": "Paracetamol 500mg",
        "unit": "tablets",
        "type": "shortage",
        "severity": "critical",
        "current_stock": 10,
        "usable_stock": 10,
        "reserved_stock": 0,
        "reorder_level": 50,
        "safety_reserve": 50,
        "message": "Stock is critically low.",
        "status": "open",
        "data_source": "database",
        "generated_at": "2026-10-13T00:00:00Z",
    }

    with patch("app.routes.alerts.get_alert") as mock_get_alert, patch("app.routes.alerts.get_alert_donor_candidates", return_value=[]):
        from app.models.schemas import AlertResponse
        mock_get_alert.return_value = AlertResponse(**fake_alert)

        res = client.get("/api/v1/alerts/alert-PHC-001-1-shortage/explanation")
        assert res.status_code == 200
        body = res.json()
        assert body["alert_id"] == "alert-PHC-001-1-shortage"
        assert body["facility_name"] == "Kengeri PHC"
        assert body["is_ai_generated"] is False
        assert body["model_version"] == "deterministic-rule-v1"
        assert "evidence_fields" in body
        assert body["evidence_fields"]["current_usable_stock"] == 10
        assert "data_limitations" in body
        assert len(body["data_limitations"]) > 0
        assert "recommended_action" in body


