// k6 load test: signs in once, then each virtual user exercises the main read paths.
//   k6 run -e BASE_URL=https://staging.example.com -e EMAIL=... -e PASSWORD=... ops/k6/smoke.js
// Run against staging only, never production.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = (__ENV.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const VUS = Number(__ENV.VUS || 50);

export const options = {
  scenarios: {
    browse: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "1m", target: VUS },
        { duration: "3m", target: VUS },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{kind:read}": ["p(95)<800"],
  },
};

export function setup() {
  const res = http.post(
    `${BASE}/api/auth/login?delivery=body`,
    JSON.stringify({ email: __ENV.EMAIL, password: __ENV.PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(res, { "signed in": (r) => r.status === 200 });
  return { token: res.json("access_token") };
}

const READS = [
  "/api/dashboard/summary",
  "/api/leads?limit=25",
  "/api/approvals?limit=25",
  "/api/campaigns",
  "/api/replies?limit=25",
];

export default function (data) {
  const params = { headers: { Authorization: `Bearer ${data.token}` }, tags: { kind: "read" } };
  for (const path of READS) {
    const res = http.get(`${BASE}${path}`, params);
    check(res, { [`${path} ok`]: (r) => r.status === 200 });
  }
  sleep(1);
}
