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

const transformPayload = JSON.stringify({
  requestId: 'mixed-req-123',
  customerName: '  Benchmark User  ',
  items: [' Item A ', 'Item B', 'ITEM C '],
  metadata: {
    ' Region ': ' Brazil ',
    ' Segment ': ' Platform ',
  },
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
    response = http.get(`${baseUrl}/products?count=100`);
  } else if (roll < 0.7) {
    response = http.get(`${baseUrl}/products-db?count=100`);
  } else if (roll < 0.9) {
    response = http.post(`${baseUrl}/transform`, transformPayload, transformParams);
  } else {
    response = http.get(`${baseUrl}/aggregate?mode=platform`);
  }

  check(response, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.05);
}
