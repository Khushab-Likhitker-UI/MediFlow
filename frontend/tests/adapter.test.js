import { describe, it, beforeEach } from 'vitest';
import assert from 'node:assert/strict';
import {
  api,
  setApiMode,
  resetMockData,
  setMockScenario
} from '../src/api/adapter';
import { INITIAL_FIXTURE_ALERTS, INITIAL_FIXTURE_EVALUATION_RUNS } from '../src/api/fixtures';

describe('Sentinel API Adapter & Security Protocol', () => {
  beforeEach(() => {
    resetMockData();
    setApiMode('mock');
  });

  describe('1. Production Mode Guard', () => {
    it('prohibits mock mode when production flag is active', () => {
      // Test that api mode getter honors production
      if (api.isProduction) {
        assert.equal(api.getApiMode(), 'real');
        assert.throws(
          () => setApiMode('mock'),
          /Mock mode is strictly forbidden in production builds/
        );
      } else {
        // In dev environment, switching to mock is allowed
        setApiMode('mock');
        assert.equal(api.getApiMode(), 'mock');
      }
    });

    it('ensures all development fixtures are clearly flagged as synthetic or simulation', () => {
      // Alerts using synthetic sources must be labeled
      const syntheticAlerts = INITIAL_FIXTURE_ALERTS.filter(a => a.data_source === 'synthetic');
      assert.ok(syntheticAlerts.length > 0, 'Should include at least one synthetic alert fixture');
      for (const alert of syntheticAlerts) {
        assert.equal(alert.data_source, 'synthetic');
        assert.ok(alert.plain_language_reason.includes('synthetic') || alert.is_insufficient_history);
      }

      // Evaluation runs must be marked as simulated fixture
      for (const run of INITIAL_FIXTURE_EVALUATION_RUNS) {
        assert.equal(run.data_source, 'simulated_fixture');
        assert.equal(run.is_simulated, true);
        assert.ok(run.baseline_name, 'Must have a named baseline');
      }
    });
  });

  describe('2. Shortage Alerts Triage (Screen 1)', () => {
    it('fetches ranked shortage alerts in normal scenario', async () => {
      setMockScenario('normal');
      const alerts = await api.fetchAlerts();

      assert.ok(Array.isArray(alerts));
      assert.ok(alerts.length >= 3);

      // Verifies priority ranking ascending
      for (let i = 0; i < alerts.length - 1; i++) {
        assert.ok(alerts[i].rank <= alerts[i + 1].rank);
      }

      // Verifies required contract fields
      const first = alerts[0];
      assert.ok(first.alert_id);
      assert.ok(first.phc_id);
      assert.ok(first.facility_name);
      assert.ok(first.item_name);
      assert.ok(first.severity);
      assert.ok(typeof first.usable_stock === 'number');
      assert.ok(typeof first.reserve_stock === 'number');
      assert.ok(first.last_verified_at);
      assert.ok(first.data_source);
    });

    it('supports filtering by severity, facility, and status', async () => {
      const criticalOnly = await api.fetchAlerts({ severity: 'critical' });
      for (const a of criticalOnly) {
        assert.equal(a.severity, 'critical');
      }

      const phcOnly = await api.fetchAlerts({ phc_id: 'PHC-003' });
      for (const a of phcOnly) {
        assert.equal(a.phc_id, 'PHC-003');
      }
    });

    it('handles empty alerts scenario gracefully', async () => {
      setMockScenario('empty');
      const alerts = await api.fetchAlerts();
      assert.deepEqual(alerts, []);
    });

    it('handles failed backend scenario', async () => {
      setMockScenario('error');
      await assert.rejects(
        async () => await api.fetchAlerts(),
        /Simulated API Error/
      );
    });
  });

  describe('3. Alert Detail & Safe Donor Review (Screen 2)', () => {
    it('retrieves donor candidates with protected reserve calculations from server', async () => {
      const candidates = await api.fetchAlertDonorCandidates('ALT-2026-001');
      assert.ok(candidates.length > 0);

      const safeDonor = candidates.find(c => c.eligible);
      assert.ok(safeDonor, 'Must have an eligible donor for ALT-2026-001');
      assert.ok(safeDonor.transferable_quantity > 0);
      assert.ok(safeDonor.donor_reserve_after_transfer >= safeDonor.safety_reserve);
      assert.ok(safeDonor.batch_number);
      assert.ok(safeDonor.expiry_date);

      const ineligibleDonor = candidates.find(c => !c.eligible);
      assert.ok(ineligibleDonor, 'Must have an ineligible donor test case');
      assert.ok(ineligibleDonor.ineligibility_reason, 'Ineligible donor must specify reason');
    });

    it('blocks viewer role from approving transfer proposals (Permission Denied)', async () => {
      const viewerUser = { username: 'charlie_viewer', role: 'viewer' };
      const proposal = {
        alert_id: 'ALT-2026-001',
        from_phc_id: 'PHC-001',
        to_phc_id: 'PHC-003',
        item_id: 12,
        quantity: 10,
      };

      await assert.rejects(
        async () => await api.proposeTransfer(proposal, viewerUser),
        (err) => {
          assert.equal(err.status, 403);
          assert.match(err.message, /Permission Denied/);
          return true;
        }
      );
    });

    it('enforces mandatory rejection reason when rejecting a proposal', async () => {
      const managerUser = { username: 'manager_rao', role: 'manager' };

      // Empty rejection reason must fail
      await assert.rejects(
        async () => await api.rejectTransfer('TR-2026-8801', '', managerUser),
        (err) => {
          assert.equal(err.status, 422);
          assert.match(err.message, /clinical or operational reason/);
          return true;
        }
      );
    });
  });

  describe('4. Transfer Lifecycle Workflow & Timeline (Screen 3)', () => {
    it('executes full proposal -> approval -> dispatch -> receive -> reconcile lifecycle', async () => {
      const managerUser = { username: 'coordinator_sharma', role: 'manager' };
      const adminUser = { username: 'cmo_admin', role: 'admin' };

      // Step 1: Propose
      const proposed = await api.proposeTransfer({
        alert_id: 'ALT-2026-001',
        from_phc_id: 'PHC-001',
        from_phc_name: 'Central District Hospital',
        to_phc_id: 'PHC-003',
        to_phc_name: 'Green Valley Clinic',
        item_id: 12,
        item_name: 'Anti-venom 10ml',
        unit: 'vials',
        quantity: 10,
        batch_number: 'AV-2026-904',
        expiry_date: '2027-11-30',
        reason: 'Emergency prophylaxis rebalance',
      }, managerUser);

      assert.equal(proposed.status, 'proposed');
      assert.equal(proposed.proposed_quantity, 10);
      assert.equal(proposed.actual_received_quantity, null);
      assert.equal(proposed.timeline.length, 1);

      // Step 2: Approve
      const approved = await api.approveTransfer(proposed.transfer_id, adminUser);
      assert.equal(approved.status, 'approved');
      assert.notEqual(approved.status, 'received');
      assert.notEqual(approved.status, 'reconciled');
      // Crucial rule: Never displayed as completed when only approved!
      assert.ok(approved.timeline.length >= 2);
      assert.equal(approved.timeline[1].status, 'approved');

      // Step 3: Dispatch
      const dispatched = await api.dispatchTransfer(proposed.transfer_id, {
        vehicle_id: 'KA-04-E-9988',
        note: 'Monitored refrigerated transport',
      });
      assert.equal(dispatched.status, 'dispatched');
      assert.equal(dispatched.vehicle_id, 'KA-04-E-9988');

      // Step 4: Receive with actual physical count
      const received = await api.receiveTransfer(proposed.transfer_id, {
        actual_received_quantity: 9, // 1 vial damaged
        remarks: '1 vial broken during mountain road transit',
      }, managerUser);
      assert.equal(received.status, 'received');
      assert.equal(received.actual_received_quantity, 9);
      assert.equal(received.proposed_quantity, 10);

      // Step 5: Reconcile
      const reconciled = await api.reconcileTransfer(proposed.transfer_id, {}, adminUser);
      assert.equal(reconciled.status, 'reconciled');

      // Verify that ledger reflects updated state
      const allTransfers = await api.fetchTransfers();
      const persisted = allTransfers.find(t => t.transfer_id === proposed.transfer_id);
      assert.ok(persisted);
      assert.equal(persisted.status, 'reconciled');
      assert.equal(persisted.actual_received_quantity, 9);
    });

    it('rejects a proposal and preserves rejection audit entry', async () => {
      const managerUser = { username: 'manager_desai', role: 'manager' };
      const rejected = await api.rejectTransfer(
        'TR-2026-8801',
        'Cold-chain transport vehicle offline due to landslide.',
        managerUser
      );

      assert.equal(rejected.status, 'rejected');
      assert.equal(rejected.rejection_reason, 'Cold-chain transport vehicle offline due to landslide.');

      const lastEvent = rejected.timeline[rejected.timeline.length - 1];
      assert.equal(lastEvent.status, 'rejected');
      assert.match(lastEvent.note, /landslide/);
    });
  });

  describe('5. Named Evaluation Runs (Screen 4)', () => {
    it('retrieves only named evaluation runs with model provenance and baseline', async () => {
      const runs = await api.fetchEvaluationRuns();
      assert.ok(Array.isArray(runs));
      assert.ok(runs.length >= 1);

      const run = runs[0];
      assert.ok(run.run_id);
      assert.ok(run.run_name);
      assert.ok(run.model_version);
      assert.ok(run.baseline_name);
      assert.ok(run.metrics);
      assert.ok(typeof run.metrics.shortage_prevention_rate_pct === 'number');
      assert.ok(typeof run.metrics.stockout_hours_avoided === 'number');
      assert.equal(run.metrics.donor_retention_rate_pct, 100);
    });
  });
});
