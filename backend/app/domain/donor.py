"""
Safe donor candidate evaluation and redistribution proposal engine.
Evaluates potential donor facilities, checks safety reserves, batch expiries,
and calculates capped transfer quantities deterministically.
"""

from __future__ import annotations
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.domain.inventory import calculate_usable_stock
from app.domain.models import (
    DonorCandidate,
    DonorFacilityContext,
    ProposalResult,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def evaluate_donor_candidates(
    recipient_facility_id: str,
    recipient_facility_name: str,
    recipient_district: str,
    recipient_lat: float,
    recipient_lng: float,
    item_id: int,
    item_name: str,
    unit: str,
    recipient_deficit: int,
    candidate_contexts: list[DonorFacilityContext],
    policy_max_cap: Optional[int] = None,
    min_shelf_life_days: int = 30,
    as_of_date: Optional[date] = None,
) -> ProposalResult:
    """
    Evaluate candidate facilities for safe transfer eligibility.

    Safety Boundary:
    - Never compromises donor's own protected reserve.
    - Excludes donor's own projected demand over the planning horizon.
    - Excludes batches expiring within min_shelf_life_days.
    - Transfer quantity is bounded by recipient deficit, donor surplus, and eligible batch stock.
    - Ranks deterministically by (same district, surplus DESC, distance ASC).
    - If no donor qualifies, explicitly returns has_safe_donor=False with escalation recommendation.
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).date()

    shelf_life_cutoff = as_of_date + timedelta(days=min_shelf_life_days)
    evaluated_candidates: list[DonorCandidate] = []

    for ctx in candidate_contexts:
        if ctx.facility_id == recipient_facility_id:
            continue  # A facility cannot donate to itself

        distance = haversine_distance(
            recipient_lat, recipient_lng, ctx.latitude, ctx.longitude
        )

        # 1. Usable stock at donor
        usable_res = calculate_usable_stock(
            facility_id=ctx.facility_id,
            item_id=item_id,
            item_name=item_name,
            unit=unit,
            batches=ctx.batches,
            active_reservations=ctx.active_reservations,
            as_of_date=as_of_date,
        )

        current_usable = usable_res.usable_quantity
        protected_reserve = ctx.safety_reserve
        donor_demand = ctx.projected_demand_over_horizon

        # 2. Donor safe surplus: what can leave without violating donor's own requirements
        # surplus = usable - protected_reserve - projected_demand
        safe_surplus = max(
            0, current_usable - protected_reserve - donor_demand
        )

        # 3. Check eligible batches with sufficient shelf-life
        eligible_batches: list[dict] = []
        eligible_batch_stock = 0
        for b in usable_res.active_batches:
            if b.expiry_date > shelf_life_cutoff:
                eligible_batches.append(
                    {
                        "batch_number": b.batch_number,
                        "quantity": b.quantity,
                        "expiry_date": b.expiry_date.isoformat(),
                    }
                )
                eligible_batch_stock += b.quantity

        # Batch stock after accounting for active reservations
        available_from_batches = max(
            0, eligible_batch_stock - ctx.active_reservations
        )

        # 4. Eligibility check
        is_eligible = True
        rejection_reason = None

        if current_usable <= protected_reserve:
            is_eligible = False
            rejection_reason = (
                f"Donor usable stock ({current_usable} {unit}) is at or below its "
                f"protected reserve ({protected_reserve} {unit})."
            )
        elif safe_surplus <= 0:
            is_eligible = False
            rejection_reason = (
                f"Donor requires its remaining stock for its own projected demand "
                f"({donor_demand} {unit}) and reserve ({protected_reserve} {unit})."
            )
        elif available_from_batches <= 0:
            is_eligible = False
            rejection_reason = (
                f"Donor has no batches with >= {min_shelf_life_days} days of shelf-life remaining."
            )

        # 5. Transferable quantity calculation
        if is_eligible:
            capped_qty = min(
                recipient_deficit,
                safe_surplus,
                available_from_batches,
            )
            if policy_max_cap is not None:
                capped_qty = min(capped_qty, policy_max_cap)

            if capped_qty <= 0:
                is_eligible = False
                rejection_reason = "Calculated safe transferable quantity is zero."
                transferable_qty = 0
            else:
                transferable_qty = capped_qty
        else:
            transferable_qty = 0

        candidate = DonorCandidate(
            facility_id=ctx.facility_id,
            facility_name=ctx.facility_name,
            district=ctx.district,
            item_id=item_id,
            item_name=item_name,
            unit=unit,
            current_usable_stock=current_usable,
            protected_reserve=protected_reserve,
            projected_demand=donor_demand,
            active_reservations=ctx.active_reservations,
            donor_safe_surplus=safe_surplus,
            transferable_quantity=transferable_qty,
            eligible_batches=eligible_batches,
            distance_km=distance,
            is_eligible=is_eligible,
            rejection_reason=rejection_reason,
        )
        evaluated_candidates.append(candidate)

    # 6. Rank eligible candidates deterministically
    eligible_list = [c for c in evaluated_candidates if c.is_eligible]
    eligible_list.sort(
        key=lambda c: (
            0 if c.district == recipient_district else 1,  # Same district prioritized
            -c.donor_safe_surplus,  # Higher surplus first
            c.distance_km if c.distance_km is not None else 9999.0,  # Proximity
        )
    )

    for rank_idx, cand in enumerate(eligible_list, start=1):
        cand.rank = rank_idx

    recommended = eligible_list[0] if eligible_list else None
    recommended_qty = recommended.transferable_quantity if recommended else 0
    has_safe_donor = recommended is not None

    escalation_action = None
    if not has_safe_donor:
        escalation_action = (
            "No safe donor facility available within protected stock bounds. "
            "Action: Raise emergency central purchase / requisition order via District Health Officer."
        )

    return ProposalResult(
        recipient_facility_id=recipient_facility_id,
        recipient_facility_name=recipient_facility_name,
        item_id=item_id,
        item_name=item_name,
        unit=unit,
        recipient_deficit=recipient_deficit,
        candidates=evaluated_candidates,
        recommended_candidate=recommended,
        recommended_quantity=recommended_qty,
        has_safe_donor=has_safe_donor,
        escalation_action=escalation_action,
    )
