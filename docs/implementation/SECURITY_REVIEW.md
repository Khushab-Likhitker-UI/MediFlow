# Smart Health Sentinel — Security Review & Hardening Report

> **Document Version:** 1.0.0  
> **Date:** 2026-10-13  
> **Status:** APPROVED & VERIFIED  

---

## 1. Executive Security Summary

MediFlow / Smart Health Sentinel handles critical public-health supply chain operations. A comprehensive security remediation was conducted across the backend API, database layer, and frontend clients. All hardcoded credentials have been removed from source code, server-side authentication and role-based access control (RBAC) are strictly enforced, and state mutations are guarded with atomic transactions and tamper-resistant audit logs.

---

## 2. Threat Vector Remediation Matrix

| Threat Vector | Prior State (Vulnerability) | Remediation Applied | Verification Evidence |
|---|---|---|---|
| **Hardcoded Database Credentials** | Remote Supabase URL hardcoded in `config.py`, `db.py`, and `database/db.py`. | Stripped fallback strings. `DATABASE_URL` is parsed strictly from environment. Production startup fails fast if unset. | [config.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/core/config.py), [db.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/db.py). `test_api_endpoints.py`. |
| **Authentication Bypass** | Mock `jwt-supabase-` pseudo-token bypass allowed arbitrary caller authentication. | Removed pseudo-token bypass. All requests require valid cryptographic JWT signed with `JWT_SECRET_KEY` (HS256). | [auth.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/domain/auth.py). `test_auth_and_permissions.py` (expired/tampered tokens rejected with 401). |
| **Unprotected User Management** | `GET /api/v1/users/` and `POST /api/v1/users/` were unauthenticated. | Restricted to authenticated administrators (`require_roles(["admin"])`). Profile lookup restricted to self or admin. | [users.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/routes/users.py). `test_user_management_role_enforcement` passes. |
| **Unauthorized Inventory Mutations** | `POST /api/v1/inventory/` and `DELETE /{id}` allowed unauthenticated alterations. | Added `require_roles(["admin", "manager"])` for creations/updates and `require_roles(["admin"])` for deletions. | [inventory.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/routes/inventory.py). `test_inventory_mutations_require_roles` passes. |
| **Cross-District Scope Creep** | Managers could potentially approve transfers originating in other districts. | Enforced server-side `verify_district_access` comparing user district against donor facility district. | [transfers.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/routes/transfers.py). `test_district_scope_authority` passes. |
| **Idempotency Replay Inconsistency** | Reused operation ID with conflicting payload returned cached response without warning. | Added request fingerprint comparison; returns `HTTP 409 Conflict` if parameters contradict existing record. | [stock_movements.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/routes/stock_movements.py). `test_idempotency_payload_mismatch_conflict` passes. |
| **SQL Injection** | Potential risk in ad-hoc query string construction. | 100% of database interactions use parameterized queries (`%s` placeholders) or ORM schema mapping. | Clean static inspection across all route files. |
| **Production Debug & CORS** | `DEBUG=True` default and permissive wildcard CORS. | `DEBUG=False` by default; CORS restricted to configured origins parsed from `CORS_ORIGINS`. | [config.py](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/core/config.py). |

---

## 3. Role-Based Access Control (RBAC) Hierarchy

The application defines three strictly enforced operational roles:

1. **`admin` (System Administrator / State Health Director):**
   - Full global read and write privileges across all facilities and districts.
   - User creation, role assignment, and medicine catalog modification.
   - Global transfer approval and reconciliation.
2. **`manager` (District Supply Coordinator):**
   - Scoped strictly to assigned district (`user.district`).
   - May review shortage alerts and evaluate safe peer donors within their district.
   - Authorized to propose, approve, and dispatch transfers within their district.
   - Prohibited from creating users or mutating catalog medicines.
3. **`viewer` (PHC Pharmacist / Field Worker / Auditor):**
   - Read-only access to facility stock levels, alerts, and transfer timelines.
   - May record facility-level stock movements via the authenticated/offline sync endpoint.
   - Prohibited from approving transfers or accessing administrative user lists.

---

## 4. Audit Trail & Ledger Integrity

Every lifecycle action is durably recorded in the `audit_events` table within the same transaction:
- **`entity_type`**: `transfer`, `inventory`, `user`
- **`action`**: `propose`, `approve`, `reject`, `dispatch`, `receive`, `reconcile`
- **`actor_id` & `actor_role`**: Server-verified credentials from JWT claims
- **`details`**: JSON payload recording previous vs updated states, quantities, and justification reasons
- **`created_at`**: UTC timestamp generated by the database engine

---

## 5. Mandatory Manual Credential-Rotation Actions

> [!CAUTION]
> **Action Required by Repository Owner:**  
> The Supabase connection string previously committed to the upstream repository must be treated as compromised. Removing secrets from git history or working files does not revoke active database passwords.  
> 
> The project administrator must:
> 1. Log in to the Supabase web console and regenerate the database password immediately.
> 2. Ensure database network restrictions or VPC firewalls are active.
> 3. Issue a new random 256-bit secret string for `JWT_SECRET_KEY` in the hosting environment variables.
