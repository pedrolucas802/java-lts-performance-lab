import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://localhost:8080';
const mode = __ENV.AGG_MODE || 'platform';

export default function () {
  const res = http.get(`${baseUrl}/aggregate?mode=${mode}`);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.05);
}
