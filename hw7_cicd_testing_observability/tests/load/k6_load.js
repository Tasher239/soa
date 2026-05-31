import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const publishedEvents = new Counter('published_events');
const errorRate = new Rate('error_rate');
const eventLatency = new Trend('event_latency_ms', true);

export const options = {
  vus: 20,
  duration: '60s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
    error_rate: ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

const PRODUCER_URL = __ENV.PRODUCER_URL || 'http://localhost:8000';

const EVENT_TYPES = ['VIEW_STARTED', 'VIEW_FINISHED', 'VIEW_PAUSED', 'VIEW_RESUMED', 'LIKED', 'SEARCHED'];
const DEVICE_TYPES = ['MOBILE', 'DESKTOP', 'TV', 'TABLET'];

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  const payload = JSON.stringify({
    user_id: `load_user_${__VU}`,
    movie_id: `load_movie_${Math.floor(Math.random() * 100)}`,
    event_type: randomItem(EVENT_TYPES),
    device_type: randomItem(DEVICE_TYPES),
    session_id: `load_sess_${__VU}_${__ITER}`,
    progress_seconds: Math.floor(Math.random() * 7200),
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '5s',
  };

  const start = Date.now();
  const res = http.post(`${PRODUCER_URL}/events`, payload, params);
  const elapsed = Date.now() - start;

  const ok = check(res, {
    'status 201': (r) => r.status === 201,
    'has event_id': (r) => {
      try { return JSON.parse(r.body).event_id !== undefined; } catch { return false; }
    },
  });

  errorRate.add(!ok);
  if (ok) {
    publishedEvents.add(1);
    eventLatency.add(elapsed);
  }

  sleep(0.1);
}

export function handleSummary(data) {
  return {
    'k6-summary.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data),
  };
}

function textSummary(data) {
  const metrics = data.metrics;
  const lines = [
    '=== k6 Load Test Summary ===',
    `Duration: ${data.state.testRunDurationMs}ms`,
    `VUs: ${options.vus}`,
    '',
    `http_req_duration p95: ${metrics.http_req_duration?.values?.['p(95)']?.toFixed(2)}ms`,
    `http_req_failed rate: ${(metrics.http_req_failed?.values?.rate * 100)?.toFixed(2)}%`,
    `published_events: ${metrics.published_events?.values?.count}`,
    '',
    'Thresholds:',
  ];
  for (const [name, threshold] of Object.entries(data.root_group.checks || {})) {
    lines.push(`  ${threshold.passes > 0 ? 'PASS' : 'FAIL'}: ${name}`);
  }
  return lines.join('\n');
}
