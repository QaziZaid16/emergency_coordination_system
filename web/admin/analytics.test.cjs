const test = require('node:test');
const assert = require('node:assert/strict');

global.window = {};
require('./redesign.js');
const analytics = global.window.ECSAnalytics;

test('normalizes sparse daily data to consecutive UTC dates and zero values', () => {
  const today = new Date('2026-10-24T13:45:00.000Z');
  const result = analytics.normalizeDailyCounts({ '2026-10-23': 4, '2026-10-24': '2' }, 3, today);
  assert.deepEqual(result, [
    { date: '2026-10-22', count: 0 },
    { date: '2026-10-23', count: 4 },
    { date: '2026-10-24', count: 2 },
  ]);
});

test('does not produce negative counts for malformed analytics values', () => {
  const result = analytics.normalizeDailyCounts({ '2026-10-24': -7, '2026-10-23': 'bad' }, 2, new Date('2026-10-24T00:00:00Z'));
  assert.deepEqual(result.map(point => point.count), [0, 0]);
});

test('filters incidents by search, status, priority, and category', () => {
  const rows = [
    { reference: 'ECS-1', emergency_type: 'Fire and Rescue', description: 'Smoke in a building', location_label: 'North', status: 'Unassigned', priority: 'High' },
    { reference: 'ECS-2', emergency_type: 'Medical', description: 'Injury', location_label: 'South', status: 'Assigned', priority: 'Critical' },
  ];
  assert.deepEqual(analytics.filterIncidents(rows, { query: 'smoke', status: 'Unassigned', priority: 'High', category: 'Fire and Rescue' }), [rows[0]]);
  assert.deepEqual(analytics.filterIncidents(rows, { category: 'Medical' }), [rows[1]]);
  assert.deepEqual(analytics.filterIncidents(rows, { query: 'missing' }), []);
});

test('chart points are finite and bounded for empty, constant, and varied series', () => {
  assert.equal(analytics.chartPoints([]), '');
  const points = analytics.chartPoints([0, 3, 1]);
  assert.equal(points, '18,162 320,18 622,114');
  for (const coordinate of points.split(' ').flatMap(pair => pair.split(',').map(Number))) assert.ok(Number.isFinite(coordinate));
});

test('category chart maps actual totals to ordered, keyboard-drillable segment geometry', () => {
  const rows = [['Medical', 3], ['Fire', 1]];
  const segments = analytics.categorySegments(rows, 4);
  assert.deepEqual(segments.map(({ name, value, percentage }) => ({ name, value, percentage })), [
    { name: 'Medical', value: 3, percentage: 75 },
    { name: 'Fire', value: 1, percentage: 25 },
  ]);
  assert.equal(segments[0].offset, 0);
  assert.ok(segments[1].offset < 0);
  assert.equal(segments[0].dash + segments[1].dash, 2 * Math.PI * 40);
});

test('analysis summary counts persisted states and leaves missing records out', () => {
  const rows = [
    { analysis: { status: 'ready', last_error_type: null } },
    { analysis: { status: 'pending' } },
    { analysis: { status: 'processing' } },
    { analysis: { status: 'unavailable', last_error_type: 'provider_timeout' } },
    { analysis: null },
  ];
  assert.deepEqual(analytics.summarizeAnalysis(rows), { ready: 1, pending: 2, failed: 1 });
});

test('status pipeline counts only persisted incidents in the reporting window', () => {
  const now = Date.parse('2026-10-24T12:00:00.000Z');
  const rows = [
    { status: 'Unassigned', created_at: '2026-10-24T10:00:00.000Z' },
    { status: 'Assigned', created_at: '2026-10-20T10:00:00.000Z' },
    { status: 'Resolved', created_at: '2026-10-01T10:00:00.000Z' },
    { status: 'Invalid date', created_at: 'unknown' },
  ];
  assert.deepEqual(analytics.countRecentStatuses(rows, 7, now), { Unassigned: 1, Assigned: 1 });
});
