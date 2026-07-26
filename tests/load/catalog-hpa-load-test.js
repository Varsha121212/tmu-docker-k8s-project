// US-PLT-15: sustained catalog-heavy read load to trigger the Catalog HPA
// (autoscaling/v2, 65% avg CPU target, 1-4 replicas - deploy/kubernetes/22-catalog.yaml).
//
// Targets the real Ingress path (not the Service directly), same request
// shape a real customer's browse/search traffic would produce, so the
// exercised code path matches AT-07's "catalog-heavy" wording rather than a
// synthetic endpoint. No auth needed - GET /api/books, /api/books/{id}, and
// /api/books/categories are all public per app/modules/catalog/api.py.
//
// Deliberately no `sleep()` between requests: the goal is sustained CPU
// pressure per pod (target 65% of the 100m CPU *request* set in
// US-PLT-14 - i.e. ~65m/pod), not a realistic-pacing user simulation. A
// think-time model would risk staying under the HPA's target and never
// proving the scale-up path at all.
//
// Tuned down after a first real run (25 Jul 2026, evidence/hpa/) at a flat
// 80 VUs drove CPU to 270-430% of the 65% target almost instantly and
// caused 53.52% of requests to fail with `request timeout` - proof the HPA
// mechanism works, but a stress-to-failure scenario, not a clean threshold
// crossing. Switched from `constant-vus` (instant full load) to
// `ramping-vus` (gradual ramp-up/hold/ramp-down) at a lower target VU
// count, so CPU eases past 65% instead of overshooting it by 6x - keep
// http_req_failed well under the 1% threshold on this tuned run.
//
// Usage: k6 run -e BASE_URL=http://172.16.200.20:30080 catalog-hpa-load-test.js
// VUS/RAMP_UP/HOLD/RAMP_DOWN are overridable the same way if the default
// doesn't push CPU past target on the actual worker hardware - see the
// runbook for how to tell from `kubectl top pods` whether to raise them.

import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://172.16.200.20:30080';
const VUS = parseInt(__ENV.VUS || '25', 10);
const RAMP_UP = __ENV.RAMP_UP || '60s';
const HOLD = __ENV.HOLD || '4m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '30s';

export const options = {
  scenarios: {
    catalog_heavy: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: RAMP_UP, target: VUS },
        { duration: HOLD, target: VUS },
        { duration: RAMP_DOWN, target: 0 },
      ],
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
