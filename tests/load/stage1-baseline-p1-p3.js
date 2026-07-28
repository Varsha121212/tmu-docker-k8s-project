// US-PLT-22: Stage 1 (VM-hosted monolith) baseline comparison scenarios,
// PMP section 15.4 — P1 (warm-up), P2 (normal), P3 (moderate). Targets
// vm-baseline-app's real public entry point (Nginx on :80), not the app's
// internal 127.0.0.1:8000, matching how real traffic reaches Stage 1.
//
// P1/P3 reuse the catalogue-heavy request mix already proven in
// catalog-hpa-load-test.js (Period 4). P2 adds the "mixed browse/login/cart"
// workload PMP 15.4 specifies: one registered user per VU, created once in
// setup() (not per-iteration, so login traffic hits real existing accounts
// instead of re-registering — and 409-conflicting — on every loop).
//
// Usage:
//   k6 run -e SCENARIO=p1 --out experimental-prometheus-rw ^
//     -e K6_PROMETHEUS_RW_SERVER_URL=http://172.16.200.23:9090/api/v1/write ^
//     tests/load/stage1-baseline-p1-p3.js
// SCENARIO is p1, p2, or p3 (default p2). VUS/DURATION can be overridden for
// re-tuning, same pattern as catalog-hpa-load-test.js's env-var overrides —
// PMP 15.4's own numbers (5/3m, 10/5m, 25/8m) are the defaults.

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://172.16.200.24';
const SCENARIO = __ENV.SCENARIO || 'p2';

const SCENARIO_DEFAULTS = {
  p1: { vus: 5, duration: '3m' },
  p2: { vus: 10, duration: '5m' },
  p3: { vus: 25, duration: '8m' },
};

const defaults = SCENARIO_DEFAULTS[SCENARIO];
if (!defaults) {
  throw new Error(`Unknown SCENARIO "${SCENARIO}" - expected p1, p2 or p3`);
}

const VUS = parseInt(__ENV.VUS || defaults.vus, 10);
const DURATION = __ENV.DURATION || defaults.duration;

export const options = {
  scenarios: {
    [`stage1_${SCENARIO}`]: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

// Mirrors the 16-book seed data's category spread (same list as
// catalog-hpa-load-test.js) closely enough to produce real filtered
// queries, not just list-everything calls.
const CATEGORIES = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Technology'];
const SEARCH_TERMS = ['the', 'a', 'and', 'of', 'life'];

function randomFrom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function browseCatalogue() {
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
  check(res, { 'catalogue status is 200': (r) => r.status === 200 });
  return res;
}

// P2 only: pre-register exactly VUS users once, before the measured window,
// so setup()'s own requests don't pollute the P2 load-test metrics.
export function setup() {
  if (SCENARIO !== 'p2') {
    return { users: [] };
  }
  const runId = Date.now();
  const users = [];
  for (let i = 0; i < VUS; i++) {
    // Note: NOT @example.test - pydantic's EmailStr (email-validator) rejects
    // RFC 2606 reserved test domains (.test/.example/.invalid/.localhost,
    // example.com/.net/.org) as "special-use or reserved". .internal is an
    // IANA-reserved private-use TLD instead - same intent, actually validates.
    const email = `us-plt-22-loadtest-${runId}-${i}@us-plt-22-loadtest.internal`;
    const password = 'LoadTest123!';
    const res = http.post(
      `${BASE_URL}/api/auth/register`,
      JSON.stringify({ email, password, display_name: `Load Test User ${i}` }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    check(res, { 'setup register is 201': (r) => r.status === 201 });
    users.push({ email, password });
  }
  return { users };
}

export default function (data) {
  if (SCENARIO === 'p2') {
    const user = data.users[(__VU - 1) % data.users.length];
    const loginRes = http.post(
      `${BASE_URL}/api/auth/login`,
      JSON.stringify({ email: user.email, password: user.password }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    check(loginRes, { 'login status is 200': (r) => r.status === 200 });
    const token = loginRes.json('access_token');

    const catalogueRes = browseCatalogue();

    if (token) {
      let books = [];
      try {
        books = catalogueRes.json('items') || [];
      } catch (e) {
        books = [];
      }
      if (books.length > 0) {
        const book = randomFrom(books);
        const cartRes = http.post(
          `${BASE_URL}/api/cart/items`,
          JSON.stringify({ book_id: book.id, quantity: 1 }),
          {
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
          },
        );
        check(cartRes, { 'cart add status is 201': (r) => r.status === 201 });
      }
    }
  } else {
    // P1 (warm-up) and P3 (moderate) are catalogue-heavy only, per PMP 15.4.
    browseCatalogue();
  }
  sleep(1);
}
