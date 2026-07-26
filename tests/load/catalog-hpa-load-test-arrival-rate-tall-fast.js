// US-PLT-15 (exploratory variant, not the primary evidence script):
// same tall `ramping-arrival-rate` staircase as
// catalog-hpa-load-test-arrival-rate-tall.js, shortened toward ~5
// minutes total runtime instead of ~8.
//
// Why this file exists instead of just editing the tall one: a real run
// of catalog-hpa-load-test-arrival-rate-tall.js's defaults (25 Jul 2026,
// START_RATE=3/RATE_STEP=5/STEPS=10, top rung 53 req/s, 45s hold/step)
// produced a genuinely gradual 1->2->3->4 climb (scale-ups at roughly
// stages 3, 5, and 7-8 of 10) and, as a bonus, a gradual 4->2->1
// scale-down too - full success, just an 8-minute run (confirmed via the
// final tally line, `running (8m00.0s)`, matching
// 10 x 45s + 30s ramp-down = 480s exactly).
//
// What changed here and why: STEP_DURATION cut from 45s to 30s, STEPS
// left at 10 (unchanged) - `10 x 30s + 30s = 330s ~= 5m30s`. STEPS was
// deliberately left alone rather than cut, because the previous run's
// `kubectl get hpa -w` output has no timestamps, so the exact rate that
// triggered 3->4 (somewhere around the 7th-8th of 10 steps, roughly
// 38-43 req/s) is a rough estimate, not a precise reading - cutting
// STEPS instead risked landing short of whatever rate is actually needed
// and reproducing catalog-hpa-load-test-arrival-rate.js's original
// "capped at 2 replicas" problem. Keeping the full climb to 53 req/s
// preserves that safety margin; the cost is each rung now gets roughly 2
// HPA sync ticks (at the ~15s default sync period) instead of ~3-4, so
// the steps may look slightly less cleanly discrete on the `-w` output.
//
// Usage: k6 run -e START_RATE=3 -e RATE_STEP=5 -e STEPS=10 \
//   -e STEP_DURATION=30s catalog-hpa-load-test-arrival-rate-tall-fast.js
// Same caveat as both prior variants: extrapolated from limited real
// data, not a known-good value - watch `kubectl get hpa catalog-hpa -n
// bookstore -w` and `kubectl top pods` and adjust between runs.

import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://172.16.200.20:30080';
const START_RATE = parseInt(__ENV.START_RATE || '3', 10);
const RATE_STEP = parseInt(__ENV.RATE_STEP || '5', 10);
const STEPS = parseInt(__ENV.STEPS || '10', 10);
const STEP_DURATION = __ENV.STEP_DURATION || '30s';
const TIME_UNIT = __ENV.TIME_UNIT || '1s';
const PRE_ALLOCATED_VUS = parseInt(__ENV.PRE_ALLOCATED_VUS || '80', 10);
const MAX_VUS = parseInt(__ENV.MAX_VUS || '300', 10);

function buildStages() {
  const stages = [];
  for (let i = 1; i <= STEPS; i++) {
    stages.push({ target: START_RATE + i * RATE_STEP, duration: STEP_DURATION });
  }
  stages.push({ target: 0, duration: '30s' });
  return stages;
}

export const options = {
  scenarios: {
    catalog_heavy_tall_staircase_fast: {
      executor: 'ramping-arrival-rate',
      timeUnit: TIME_UNIT,
      startRate: START_RATE,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
      stages: buildStages(),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

// Mirrors the 16-book seed data's category spread closely enough to
// produce real filtered queries, not just list-everything calls.
const CATEGORIES = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Technology'];
const SEARCH_TERMS = ['the', 'a', 'and', 'of', 'life'];

function randomFrom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  const page = 1 + Math.floor(Math.random() * 3);
  const mode = Math.random();

  let res;
  if (mode < 0.5) {
    res = http.get(`${BASE_URL}/api/books?page=${page}&page_size=20`);
  } else if (mode < 0.8) {
    res = http.get(`${BASE_URL}/api/books?category=${encodeURIComponent(randomFrom(CATEGORIES))}&page=1&page_size=20`);
  } else if (mode < 0.95) {
    res = http.get(`${BASE_URL}/api/books?q=${encodeURIComponent(randomFrom(SEARCH_TERMS))}`);
  } else {
    res = http.get(`${BASE_URL}/api/books/categories`);
  }

  check(res, { 'status is 200': (r) => r.status === 200 });
}
