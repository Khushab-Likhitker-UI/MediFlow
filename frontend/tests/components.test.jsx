import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';
import {
  SeverityBadge,
  StaleDataBadge,
  InsufficientHistoryBadge,
  SyntheticDemoBadge,
  TransferStatusBadge,
  DataSourceBadge
} from '../src/components/Badges';
import { INITIAL_FIXTURE_ALERTS, INITIAL_FIXTURE_TRANSFERS } from '../src/api/fixtures';

describe('UI Badge & Non-Color-Only Accessibility Tests', () => {
  it('renders critical severity with both icon and non-color text cue [!] CRITICAL', () => {
    const html = renderToString(<SeverityBadge severity="critical" />);
    assert.ok(html.includes('[!] CRITICAL'), 'Must include text symbol and label');
    assert.ok(html.includes('role="status"'), 'Must have accessible status role');
    assert.ok(html.includes('aria-label="Severity Critical'), 'Must have accessible label');
  });

  it('renders warning severity with non-color text cue [▲] WARNING', () => {
    const html = renderToString(<SeverityBadge severity="warning" />);
    assert.ok(html.includes('[▲] WARNING'), 'Must include text symbol and label');
    assert.ok(html.includes('role="status"'));
  });

  it('renders info severity with non-color text cue [i] INFO', () => {
    const html = renderToString(<SeverityBadge severity="info" />);
    assert.ok(html.includes('[i] INFO'), 'Must include text symbol and label');
  });

  it('renders stale data badge with time warning', () => {
    const html = renderToString(<StaleDataBadge lastVerifiedAt="2026-10-11T08:00:00Z" />);
    assert.ok(html.includes('STALE DATA (&gt;24h)'));
  });

  it('renders insufficient history badge', () => {
    const html = renderToString(<InsufficientHistoryBadge />);
    assert.ok(html.includes('INSUFFICIENT HISTORY'));
  });

  it('renders synthetic demo badge that cannot be mistaken for real operation', () => {
    const html = renderToString(<SyntheticDemoBadge />);
    assert.ok(html.includes('SYNTHETIC DEMO'));
    assert.ok(html.includes('role="alert"'));
  });

  it('renders transfer lifecycle badges with explicit states', () => {
    const proposed = renderToString(<TransferStatusBadge status="proposed" />);
    assert.ok(proposed.includes('Proposed'));

    const approved = renderToString(<TransferStatusBadge status="approved" />);
    assert.ok(approved.includes('Approved (Pending Dispatch)'));

    const dispatched = renderToString(<TransferStatusBadge status="dispatched" />);
    assert.ok(dispatched.includes('Dispatched (In Transit)'));

    const received = renderToString(<TransferStatusBadge status="received" />);
    assert.ok(received.includes('Received (Verifying)'));

    const reconciled = renderToString(<TransferStatusBadge status="reconciled" />);
    assert.ok(reconciled.includes('Reconciled'));

    const rejected = renderToString(<TransferStatusBadge status="rejected" />);
    assert.ok(rejected.includes('Rejected'));
  });

  it('renders data source provenance labels', () => {
    const dbHtml = renderToString(<DataSourceBadge source="database" />);
    assert.ok(dbHtml.includes('DATABASE'));

    const mlHtml = renderToString(<DataSourceBadge source="synthetic" />);
    assert.ok(mlHtml.includes('ML_SYNTHETIC'));
  });
});

describe('Coordinator Domain Contracts & Data Shape Conformance', () => {
  it('ensures all alert fixtures match frozen contract schema', () => {
    for (const alert of INITIAL_FIXTURE_ALERTS) {
      assert.ok(alert.alert_id.startsWith('ALT-'));
      assert.ok(alert.phc_id.startsWith('PHC-'));
      assert.ok(alert.item_name);
      assert.ok(['critical', 'warning', 'info'].includes(alert.severity));
      assert.ok(typeof alert.usable_stock === 'number');
      assert.ok(typeof alert.reserve_stock === 'number');
      assert.ok(typeof alert.avg_daily_consumption === 'number');
      assert.ok(alert.plain_language_reason.length > 10);
      assert.ok(alert.stock_curve.length > 0);
    }
  });

  it('ensures no transfer is created as completed upon approval', () => {
    for (const transfer of INITIAL_FIXTURE_TRANSFERS) {
      if (transfer.status === 'approved') {
        assert.equal(transfer.actual_received_quantity, null);
      }
    }
  });

  it('identifies alert with no safe donors to verify escalation path', () => {
    const noDonorAlert = INITIAL_FIXTURE_ALERTS.find(
      a => !a.donor_candidates || a.donor_candidates.length === 0 || a.donor_candidates.every(c => !c.eligible)
    );
    assert.ok(noDonorAlert, 'Must have at least one alert fixture with no safe donors to exercise replenishment escalation');
    assert.equal(noDonorAlert.phc_id, 'PHC-006');
    assert.equal(noDonorAlert.is_insufficient_history, true);
    assert.equal(noDonorAlert.data_source, 'synthetic');
  });
});
