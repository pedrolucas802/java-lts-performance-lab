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

const payload = JSON.stringify({
  requestId: 'req-123',
  customerName: '  Pedro Lucas  ',
  items: [' Item A ', 'Item B', 'ITEM C ', ' item d ', 'ITEM E'],
  metadata: {
    ' Region ': ' Brazil ',
    ' Segment ': ' Enterprise ',
    ' Priority ': ' High ',
  },
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

  sleep(0.1);
}
