import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://localhost:8080';
const productCount = Number(__ENV.PRODUCT_COUNT || 100);
const transformItemCount = Number(__ENV.TRANSFORM_ITEM_COUNT || 5);
const transformMetadataCount = Number(__ENV.TRANSFORM_METADATA_COUNT || 3);
const thinkTimeSeconds = Number(__ENV.THINK_TIME_SECONDS || 0.05);

function buildItems(count) {
  return Array.from({ length: count }, (_, index) => ` Mixed Item ${index + 1} `);
}

function buildMetadata(count) {
  return Object.fromEntries(
    Array.from({ length: count }, (_, index) => [
      ` Mixed Meta ${index + 1} `,
      ` Mixed Value ${index + 1} `,
    ]),
  );
}

const transformPayload = JSON.stringify({
  requestId: 'mixed-req-123',
  customerName: '  Benchmark User  ',
  items: buildItems(transformItemCount),
  metadata: buildMetadata(transformMetadataCount),
});

const transformParams = {
  headers: {
    'Content-Type': 'application/json',
  },
};

export default function () {
  const roll = Math.random();
  let response;

  if (roll < 0.5) {
    response = http.get(`${baseUrl}/products?count=${productCount}`);
  } else if (roll < 0.7) {
    response = http.get(`${baseUrl}/products-db?count=${productCount}`);
  } else if (roll < 0.9) {
    response = http.post(`${baseUrl}/transform`, transformPayload, transformParams);
  } else {
    response = http.get(`${baseUrl}/aggregate?mode=platform`);
  }

  check(response, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(thinkTimeSeconds);
}
