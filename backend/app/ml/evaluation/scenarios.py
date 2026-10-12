"""
Deterministic scenario fixtures for Smart Health Sentinel evaluation.

Defines 10 canonical test scenarios:
1. normal_consumption: Steady daily usage, healthy stock.
2. demand_surge: Abrupt 3.5x consumption spike testing rapid shortage alert.
3. critically_low_stock_before_delivery: Lead time exceeds stock runway -> breach.
4. delivery_arrives_before_breach: Timely replenishment prevents stockout.
5. no_safe_donor: All network facilities at or below critical reserve.
6. donor_at_protected_reserve: Transfer would violate donor's protected reserve floor.
7. expired_batch: Usable inventory drops abruptly when batch expires.
8. competing_recipients: Multiple needy facilities compete for limited donor surplus.
9. zero_sparse_history: Empty or very few observations testing quality gates & fallbacks.
10. offline_duplicate_retry: Idempotent replay of offline sync payload without double counting.

All fixtures are strictly synthetic, deterministic, and self-contained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class BatchRecord:
    batch_number: str
    quantity: int
    expiry_date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class DeliveryRecord:
    day_offset: int  # Day relative to forecast start (1-indexed)
    quantity: int


@dataclass(frozen=True)
class ScenarioFixture:
    """Deterministic fixture representing a health facility inventory scenario."""
    scenario_id: str
    name: str
    description: str
    data_provenance: str
    item_id: int
    item_name: str
    unit: str
    reorder_level: int
    facility_id: str
    initial_stock: int
    batches: list[BatchRecord]
    history_records: list[dict[str, Any]]
    test_actual_records: list[dict[str, Any]]
    horizon_days: int
    deliveries: list[DeliveryRecord] = field(default_factory=list)
    protected_reserve: int = 50
    network_donors: list[dict[str, Any]] = field(default_factory=list)
    competing_recipients: list[dict[str, Any]] = field(default_factory=list)
    offline_duplicate_payloads: list[dict[str, Any]] = field(default_factory=list)
    expected_stockout_ground_truth: bool = False
    expected_transfer_violation: bool = False


def _generate_linear_history(
    base_date: date,
    days: int,
    base_val: float,
    weekday_weights: list[float] | None = None,
    noise_seq: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Generate deterministic historical daily consumption records."""
    if weekday_weights is None:
        weekday_weights = [1.2, 1.1, 1.0, 1.0, 0.9, 0.8, 0.7]  # Mon-Sun pattern
    records = []
    for i in range(days):
        dt = base_date - timedelta(days=days - i)
        w = weekday_weights[dt.weekday()]
        noise = noise_seq[i % len(noise_seq)] if noise_seq else 0.0
        val = max(0.0, round(base_val * w + noise, 1))
        records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "quantity_consumed": val,
            "patients_served": int(val * 1.5),
        })
    return records


def get_deterministic_scenarios(reference_date: date | None = None) -> dict[str, ScenarioFixture]:
    """Build and return all 10 canonical deterministic scenario fixtures.

    Safe, in-memory, deterministic. Does not touch or reset any database.
    """
    ref_date = reference_date or date(2026, 10, 1)

    scenarios: dict[str, ScenarioFixture] = {}

    # Deterministic noise sequence (no random generator dependencies)
    noise_45 = [
        0.5, -0.4, 1.1, -0.8, 0.2, -1.0, 0.7, 0.3, -0.5, 1.2,
        -0.2, 0.4, -0.7, 0.9, -1.1, 0.3, -0.3, 0.6, -0.9, 0.1,
        0.8, -0.6, 0.4, -0.5, 1.0, -1.2, 0.3, -0.1, 0.5, -0.4,
        0.7, -0.8, 0.2, 0.6, -0.3, 1.1, -0.7, 0.4, -0.2, 0.5,
        -0.6, 0.8, -0.3, 0.2, -0.5,
    ]

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Normal Consumption
    # ──────────────────────────────────────────────────────────────────────────
    hist_1 = _generate_linear_history(ref_date, 60, base_val=15.0, noise_seq=noise_45)
    test_1 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 15.0}
        for i in range(1, 15)
    ]
    scenarios["normal_consumption"] = ScenarioFixture(
        scenario_id="normal_consumption",
        name="Normal Steady Consumption",
        description="Steady routine outpatient dispensing at PHC-001. Stock remains well above reorder level.",
        data_provenance="synthetic_scenario",
        item_id=101,
        item_name="Paracetamol 500mg",
        unit="tablets",
        reorder_level=50,
        facility_id="PHC-001",
        initial_stock=350,
        batches=[BatchRecord("BATCH-A1", 350, (ref_date + timedelta(days=180)).strftime("%Y-%m-%d"))],
        history_records=hist_1,
        test_actual_records=test_1,
        horizon_days=14,
        expected_stockout_ground_truth=False,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Demand Surge
    # ──────────────────────────────────────────────────────────────────────────
    hist_2 = _generate_linear_history(ref_date, 60, base_val=15.0, noise_seq=noise_45)
    # Sudden 3.5x surge in the test horizon (e.g. seasonal outbreak spike)
    test_2 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 55.0}
        for i in range(1, 15)
    ]
    scenarios["demand_surge"] = ScenarioFixture(
        scenario_id="demand_surge",
        name="Abrupt Demand Surge",
        description="Unanticipated 3.5x demand surge testing early stockout warning before baseline catches up.",
        data_provenance="synthetic_scenario",
        item_id=102,
        item_name="Amoxicillin 500mg",
        unit="capsules",
        reorder_level=60,
        facility_id="PHC-002",
        initial_stock=200,
        batches=[BatchRecord("BATCH-B1", 200, (ref_date + timedelta(days=120)).strftime("%Y-%m-%d"))],
        history_records=hist_2,
        test_actual_records=test_2,
        horizon_days=14,
        expected_stockout_ground_truth=True,  # 200 stock depleted in ~4 days
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Critically Low Stock Before Delivery
    # ──────────────────────────────────────────────────────────────────────────
    hist_3 = _generate_linear_history(ref_date, 45, base_val=12.0, noise_seq=noise_45)
    test_3 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 12.0}
        for i in range(1, 15)
    ]
    # Initial stock 24 units, consuming 12/day -> stockout on Day 2. Replenishment scheduled on Day 5!
    scenarios["critically_low_stock_before_delivery"] = ScenarioFixture(
        scenario_id="critically_low_stock_before_delivery",
        name="Critically Low Stock Before Delayed Delivery",
        description="Runway is only 2 days, but delivery arrives on day 5. A breach of 3 stockout days occurs.",
        data_provenance="synthetic_scenario",
        item_id=103,
        item_name="ORS Sachets",
        unit="sachets",
        reorder_level=50,
        facility_id="PHC-003",
        initial_stock=24,
        batches=[BatchRecord("BATCH-C1", 24, (ref_date + timedelta(days=90)).strftime("%Y-%m-%d"))],
        history_records=hist_3,
        test_actual_records=test_3,
        horizon_days=14,
        deliveries=[DeliveryRecord(day_offset=5, quantity=150)],
        expected_stockout_ground_truth=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Delivery Arrives Before Breach
    # ──────────────────────────────────────────────────────────────────────────
    hist_4 = _generate_linear_history(ref_date, 45, base_val=10.0, noise_seq=noise_45)
    test_4 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 10.0}
        for i in range(1, 15)
    ]
    # Initial stock 45 units, consuming 10/day -> would breach on Day 5, but delivery of 100 arrives on Day 3!
    scenarios["delivery_arrives_before_breach"] = ScenarioFixture(
        scenario_id="delivery_arrives_before_breach",
        name="Delivery Arrives Before Breach",
        description="Scheduled shipment arrives on Day 3 while 15 units remain, successfully averting breach.",
        data_provenance="synthetic_scenario",
        item_id=104,
        item_name="Ciprofloxacin 500mg",
        unit="tablets",
        reorder_level=40,
        facility_id="PHC-004",
        initial_stock=45,
        batches=[BatchRecord("BATCH-D1", 45, (ref_date + timedelta(days=120)).strftime("%Y-%m-%d"))],
        history_records=hist_4,
        test_actual_records=test_4,
        horizon_days=14,
        deliveries=[DeliveryRecord(day_offset=3, quantity=100)],
        expected_stockout_ground_truth=False,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 5. No Safe Donor
    # ──────────────────────────────────────────────────────────────────────────
    hist_5 = _generate_linear_history(ref_date, 45, base_val=8.0, noise_seq=noise_45)
    test_5 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 8.0}
        for i in range(1, 15)
    ]
    # Recipient has 10 units. Nearby facilities have 20, 15, 30 units (all < protected reserve 50).
    scenarios["no_safe_donor"] = ScenarioFixture(
        scenario_id="no_safe_donor",
        name="No Safe Donor in Transfer Network",
        description="Recipient needs transfer, but all network peers are at or below their protected reserves.",
        data_provenance="synthetic_scenario",
        item_id=105,
        item_name="Metformin 500mg",
        unit="tablets",
        reorder_level=40,
        facility_id="PHC-005",
        initial_stock=10,
        batches=[BatchRecord("BATCH-E1", 10, (ref_date + timedelta(days=90)).strftime("%Y-%m-%d"))],
        history_records=hist_5,
        test_actual_records=test_5,
        horizon_days=14,
        protected_reserve=40,
        network_donors=[
            {"facility_id": "PHC-101", "current_stock": 20, "protected_reserve": 50},
            {"facility_id": "PHC-102", "current_stock": 15, "protected_reserve": 50},
        ],
        expected_stockout_ground_truth=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Donor at Protected Reserve
    # ──────────────────────────────────────────────────────────────────────────
    hist_6 = _generate_linear_history(ref_date, 45, base_val=10.0, noise_seq=noise_45)
    test_6 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 10.0}
        for i in range(1, 15)
    ]
    # Candidate donor PHC-006 has 55 units with protected reserve = 50. Transferring 30 would breach reserve!
    scenarios["donor_at_protected_reserve"] = ScenarioFixture(
        scenario_id="donor_at_protected_reserve",
        name="Donor Transfer Breaches Protected Reserve",
        description="Donor has 55 units (protected reserve 50). Transferring 30 units leaves only 25 (violation).",
        data_provenance="synthetic_scenario",
        item_id=106,
        item_name="Azithromycin 250mg",
        unit="tablets",
        reorder_level=30,
        facility_id="PHC-006",
        initial_stock=55,
        batches=[BatchRecord("BATCH-F1", 55, (ref_date + timedelta(days=120)).strftime("%Y-%m-%d"))],
        history_records=hist_6,
        test_actual_records=test_6,
        horizon_days=14,
        protected_reserve=50,
        network_donors=[{"facility_id": "PHC-006", "current_stock": 55, "protected_reserve": 50}],
        expected_transfer_violation=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Expired Batch
    # ──────────────────────────────────────────────────────────────────────────
    hist_7 = _generate_linear_history(ref_date, 45, base_val=15.0, noise_seq=noise_45)
    test_7 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 15.0}
        for i in range(1, 15)
    ]
    # Facility has 120 units total, but 90 units belong to BATCH-G1 expiring on Day 2!
    # On Day 2, usable stock drops to 30 units - (15*2) = 0 -> Stockout on Day 3!
    scenarios["expired_batch"] = ScenarioFixture(
        scenario_id="expired_batch",
        name="Inventory Batch Expiry Cliff",
        description="Physical stock appears sufficient (120 units), but 90 units expire on Day 2.",
        data_provenance="synthetic_scenario",
        item_id=107,
        item_name="Insulin Regular 100IU",
        unit="vials",
        reorder_level=40,
        facility_id="PHC-007",
        initial_stock=120,
        batches=[
            BatchRecord("BATCH-G1", 90, (ref_date + timedelta(days=2)).strftime("%Y-%m-%d")),
            BatchRecord("BATCH-G2", 30, (ref_date + timedelta(days=180)).strftime("%Y-%m-%d")),
        ],
        history_records=hist_7,
        test_actual_records=test_7,
        horizon_days=14,
        expected_stockout_ground_truth=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Competing Recipients
    # ──────────────────────────────────────────────────────────────────────────
    hist_8 = _generate_linear_history(ref_date, 45, base_val=10.0, noise_seq=noise_45)
    test_8 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 10.0}
        for i in range(1, 15)
    ]
    # Two facilities (PHC-008A runway 2 days, PHC-008B runway 3 days) compete for donor PHC-009 with only 30 surplus units
    scenarios["competing_recipients"] = ScenarioFixture(
        scenario_id="competing_recipients",
        name="Competing Recipients with Constrained Donor",
        description="Two recipient facilities face impending stockouts; donor only has enough surplus for one.",
        data_provenance="synthetic_scenario",
        item_id=108,
        item_name="Artesunate Injection",
        unit="vials",
        reorder_level=30,
        facility_id="PHC-008A",
        initial_stock=20,
        batches=[BatchRecord("BATCH-H1", 20, (ref_date + timedelta(days=90)).strftime("%Y-%m-%d"))],
        history_records=hist_8,
        test_actual_records=test_8,
        horizon_days=14,
        protected_reserve=40,
        network_donors=[{"facility_id": "PHC-009", "current_stock": 80, "protected_reserve": 50}],  # 30 surplus
        competing_recipients=[
            {"facility_id": "PHC-008A", "deficit": 40, "urgency_days": 2},
            {"facility_id": "PHC-008B", "deficit": 40, "urgency_days": 3},
        ],
        expected_stockout_ground_truth=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Zero / Sparse History
    # ──────────────────────────────────────────────────────────────────────────
    # Only 3 days of dispensing data recorded (below minimum threshold 30)
    sparse_hist = [
        {"date": (ref_date - timedelta(days=3)).strftime("%Y-%m-%d"), "quantity_consumed": 5.0, "patients_served": 5},
        {"date": (ref_date - timedelta(days=2)).strftime("%Y-%m-%d"), "quantity_consumed": 8.0, "patients_served": 8},
        {"date": (ref_date - timedelta(days=1)).strftime("%Y-%m-%d"), "quantity_consumed": 6.0, "patients_served": 6},
    ]
    test_9 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 6.0}
        for i in range(1, 15)
    ]
    scenarios["zero_sparse_history"] = ScenarioFixture(
        scenario_id="zero_sparse_history",
        name="Zero or Sparse Consumption History",
        description="Newly onboarded PHC with only 3 observations; tests quality failure & transparent baseline.",
        data_provenance="synthetic_scenario",
        item_id=109,
        item_name="Cetirizine 10mg",
        unit="tablets",
        reorder_level=50,
        facility_id="PHC-009",
        initial_stock=100,
        batches=[BatchRecord("BATCH-I1", 100, (ref_date + timedelta(days=180)).strftime("%Y-%m-%d"))],
        history_records=sparse_hist,
        test_actual_records=test_9,
        horizon_days=14,
        expected_stockout_ground_truth=False,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Offline Duplicate / Retry
    # ──────────────────────────────────────────────────────────────────────────
    hist_10 = _generate_linear_history(ref_date, 45, base_val=10.0, noise_seq=noise_45)
    test_10 = [
        {"date": (ref_date + timedelta(days=i)).strftime("%Y-%m-%d"), "quantity_consumed": 10.0}
        for i in range(1, 15)
    ]
    # Offline sync event submitted twice with the same offline_sync_id
    offline_duplicate = [
        {
            "offline_sync_id": "00000000-0000-0000-0000-000000000001",
            "date": (ref_date - timedelta(days=1)).strftime("%Y-%m-%d"),
            "quantity_consumed": 15.0,
            "submission_number": 1,
        },
        {
            "offline_sync_id": "00000000-0000-0000-0000-000000000001",  # exact duplicate sync ID
            "date": (ref_date - timedelta(days=1)).strftime("%Y-%m-%d"),
            "quantity_consumed": 15.0,
            "submission_number": 2,
        },
    ]
    scenarios["offline_duplicate_retry"] = ScenarioFixture(
        scenario_id="offline_duplicate_retry",
        name="Offline Duplicate / Retry Sync Event",
        description="Simulates network retry sending duplicate offline sync ID. Ingestion must deduplicate.",
        data_provenance="synthetic_scenario",
        item_id=110,
        item_name="Ibuprofen 400mg",
        unit="tablets",
        reorder_level=50,
        facility_id="PHC-010",
        initial_stock=120,
        batches=[BatchRecord("BATCH-J1", 120, (ref_date + timedelta(days=180)).strftime("%Y-%m-%d"))],
        history_records=hist_10,
        test_actual_records=test_10,
        horizon_days=14,
        offline_duplicate_payloads=offline_duplicate,
        expected_stockout_ground_truth=False,
    )

    return scenarios
