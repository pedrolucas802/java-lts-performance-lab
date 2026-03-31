import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://localhost:8080';
const transformItemCount = Number(__ENV.TRANSFORM_ITEM_COUNT || 5);
const transformMetadataCount = Number(__ENV.TRANSFORM_METADATA_COUNT || 3);
const thinkTimeSeconds = Number(__ENV.THINK_TIME_SECONDS || 0.1);

function buildItems(count) {
  return Array.from({ length: count }, (_, index) => ` Item ${index + 1} `);
}

function buildMetadata(count) {
  return Object.fromEntries(
    Array.from({ length: count }, (_, index) => [
      ` Meta Key ${index + 1} `,
      ` Meta Value ${index + 1} `,
    ]),
  );
}

const payload = JSON.stringify({
  requestId: 'req-heavy-transform',
  customerName: '  Pedro Lucas Benchmark User  ',
  items: buildItems(transformItemCount),
  metadata: buildMetadata(transformMetadataCount),
});

const params = {
  headers: {
    'Content-Type': 'application/json',
  },
};

export default function () {
  const res = http.post(`${baseUrl}/transform`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(thinkTimeSeconds);
}
