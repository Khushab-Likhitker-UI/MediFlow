# Smart Health Sentinel — Hackathon Demo Runbook & Pitch Guide

> **Target Pitch Duration:** 3 Minutes  
> **Backup Video Target:** 90 Seconds  
> **Audience:** Hackathon Technical Judges & Public Health Domain Evaluators  
> **Demo Environment:** 100% Local Self-Contained (`http://127.0.0.1:8000`, `5173`, `5174`)

---

## 1. Pre-Flight Verification Checklist

Before starting the demo or recording:
1. **Backend Running:**
   - URL: `http://127.0.0.1:8000/health` → Returns `{"status":"healthy","service":"MediFlow"}`
   - Interactive Docs: `http://127.0.0.1:8000/docs`
2. **Web Dashboard Running:**
   - URL: `http://127.0.0.1:5173`
   - Test login: Coordinator account (`admin@smarthealth.local` / `admin123`)
3. **PHC Worker PWA Running:**
   - URL: `http://127.0.0.1:5174`
   - Clean outbox with zero pending synchronization errors

---

## 2. Three-Minute Pitch Script & Demo Walkthrough

### Minute 0:00 – 0:45: The Problem & The Human Reality
> *"Every week, rural Primary Health Centres across low-resource districts face critical stockouts of life-saving medicines—like anti-malarials and ORS. Meanwhile, a clinic just 12 kilometers away often has a three-month surplus expiring on the shelf. Today, supply coordinators rely on fragmented WhatsApp messages and paper registers. Stockouts are discovered only when patients arrive at an empty dispensary.*
>
> *We built **MediFlow (Smart Health Sentinel)**: an offline-first medicine supply chain decision-support system that predicts stockouts before they happen, calculates safe inter-facility redistributions without compromising donor clinics, and synchronizes reliably from the field."*

### Minute 0:45 – 1:45: Live Golden Path Demonstration

#### Step 1: District Command Center (Screen 1)
- **Show:** `http://127.0.0.1:5173`
- **Action:** Point to the top critical alert for **Kengeri PHC (Paracetamol 500mg)**.
- **Narrative:**
  > *"Here on the District Command Center, our backend forecasting engine has projected that Kengeri PHC will breach its 50-unit safety reserve in 24 hours based on recent consumption trends. Notice that inbound supplier replenishment isn't scheduled for 5 days. We need an immediate redistribution."*

#### Step 2: Safe Donor Evaluation & Explainable Review (Screen 2)
- **Action:** Click **"Review Donors"** on the alert.
- **Show:** Donor Candidate List.
- **Narrative:**
  > *"The system evaluates all peer facilities in the district. Look at Hebbal PHC: it has 120 units, but our algorithm has calculated that donating stock would breach its own safety reserve next week, so Hebbal is rejected as a donor. Bidadi PHC, however, has a true usable surplus of 40 units above its protected reserve. The backend recommends transferring exactly 40 units."*
- **Action:** Click **"Explain Alert"** to show the grounded explainer modal.
  > *"Notice that our AI explainer is grounded strictly in backend numbers. Even if cloud AI is offline, our deterministic template explains the exact reserve breach calculation."*

#### Step 3: Approval & Atomic Reservation
- **Action:** Click **"Approve Transfer"**.
- **Show:** Status transitions to `APPROVED`.
- **Narrative:**
  > *"When the coordinator approves, an atomic database transaction immediately places a reservation hold on Bidadi's stock. Even if a competing coordinator tries to approve another transfer simultaneously, our row-level locks prevent double-allocation."*

#### Step 4: Dispatch, Receipt & Ledger Reconciliation (Screen 3)
- **Action:** Switch to **Transfer Tracking** tab. Click **"Dispatch"**, then **"Receive"**.
- **Show:** Enter 38 received units (noting 2 damaged in transit).
- **Narrative:**
  > *"The transfer moves through DISPATCHED to RECEIVED. When the destination records receipt of 38 units, both facilities' inventory ledgers settle atomically, and an immutable audit event is stamped."*

### Minute 1:45 – 2:30: Field PWA & Offline Synchronization
- **Show:** `http://127.0.0.1:5174` (PHC Worker PWA).
- **Action:** Open Chrome DevTools → Network tab → Toggle **"Offline"**.
- **Action:** Log dispensing 10 units of Paracetamol.
- **Show:** PWA badges `Pending Offline Sync (1)`.
- **Action:** Toggle **"Online"**.
- **Show:** PWA automatically synchronizes within 2 seconds. Status changes to `Synced`.
- **Narrative:**
  > *"PHC nurses often work with zero connectivity. The PWA writes mutations into an IndexedDB outbox with a stable UUID. When connectivity returns, it synchronizes exactly once. Retries cannot cause duplicate stock deductions."*

### Minute 2:30 – 3:00: Evaluation, Google Tech & Conclusion
- **Show:** Evaluation Metrics page / `backend/evaluation_report.json`.
- **Narrative:**
  > *"We don't make up impact claims. We evaluated our system across 10 deterministic scenarios. Our 7-day baseline achieved an MAE of 4.49, while Prophet achieved 5.25. Our model engine detected and rejected all 3 unsafe candidate proposals with zero constraint violations.
  >
  > MediFlow runs on FastAPI and PostgreSQL, and is architected for Cloud Run, Cloud SQL, and optional Vertex AI Gemini explanations. Thank you!"*

---

## 3. 90-Second Backup Demo Video Recording Checklist

| Timestamp | Screen / Visual | Audio Voiceover Focus |
|---|---|---|
| `0:00 - 0:15` | Command Center with open alerts | Problem: rural stockouts vs neighbor surpluses. Introduce MediFlow. |
| `0:15 - 0:35` | Alert detail & donor review | Show algorithm rejecting unsafe donor and selecting safe donor surplus. |
| `0:35 - 0:55` | Approval & transfer tracking | Coordinator approves; show atomic reservation, dispatch, and receipt. |
| `0:55 - 1:15` | PHC PWA in offline mode | Disconnect network; record dispensing; reconnect; verify exact-once sync. |
| `1:15 - 1:30` | Scientific evaluation & architecture | Show 10/10 scenario evaluation results and technology stack. |

---

## 4. Live Demo Troubleshooting & Safety Net

- **If local port 8000 is occupied:** Run `tasklist | findstr python` and terminate previous uvicorn instances.
- **If frontend is in mock mode:** Check URL query parameter: ensure `?mode=real` or clear sessionStorage.
- **If IndexedDB is dirty:** Click "Clear Local Outbox" in PWA settings to reset to pristine demo state.
- **If LLM API is unavailable:** The explainer service automatically falls back to the deterministic template within 0.1s; workflow remains 100% operational.
