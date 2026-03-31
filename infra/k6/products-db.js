import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 15),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://localhost:8080';
const productCount = Number(__ENV.PRODUCT_COUNT || 100);
const thinkTimeSeconds = Number(__ENV.THINK_TIME_SECONDS || 0.1);

export default function () {
  const res = http.get(`${baseUrl}/products-db?count=${productCount}`);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(thinkTimeSeconds);
}
