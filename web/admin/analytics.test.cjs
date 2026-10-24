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
