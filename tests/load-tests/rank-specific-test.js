import http from 'k6/http';
import { sleep } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

// Custom metrics
const errors = new Counter('errors');
const requestDuration = new Trend('request_duration');
const successRate = new Rate('success_rate');

// Test configuration for the specific 3 parallel calls
export const options = {
  // 3 virtual users to make 3 parallel calls
  vus: 3,
  iterations: 3,
  // Set a very long timeout since each call takes ~30 minutes
  timeout: '120m',
  // Increase the request timeout to match server-side timeout
  thresholds: {
    http_req_duration: ['p(95)<3600000'], // 60 minutes in milliseconds
  },
};

// The specific keyword ID batches to test
const keywordBatches = [
  { ids: [1, 2] },
  { ids: [3, 4] },
  { ids: [5] }
];

export default function (data) {
  // Determine which batch to use based on the VU number
  const batchIndex = (__VU - 1) % keywordBatches.length;
  const batch = keywordBatches[batchIndex];
  
  // Add authentication with token from setup
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${data.token}`,
    }
  };
  
  const url = 'http://localhost:8000/api/keywords/run-rank/';
  const payload = JSON.stringify({ ids: batch.ids });
  
  console.log(`VU ${__VU}: Testing with keyword IDs: ${batch.ids.join(', ')}`);
  
  // Make the POST request and record the response time
  const startTime = new Date();
  // Set a longer timeout for the HTTP request (60 minutes in ms)
  params.timeout = 3600000;
  const response = http.post(url, payload, params);
  const duration = new Date() - startTime;
  
  // Record custom metrics
  requestDuration.add(duration);
  
  // Check if the request was successful
  const success = response.status === 200;
  successRate.add(success);
  
  // Log the result
  if (success) {
    console.log(`VU ${__VU}: Request completed successfully in ${duration/1000} seconds`);
  } else {
    errors.add(1);
    console.error(`VU ${__VU}: Request failed with status ${response.status}: ${response.body}`);
  }
}

// Setup function to authenticate
export function setup() {
  // Get authentication token - using form data as required by OAuth2PasswordRequestForm
  const credentials = {
    username: 'keanujohn@yahoo.com',
    password: 'admin'
  };
  
  // Send as form data (application/x-www-form-urlencoded)
  const loginRes = http.post(
    'http://localhost:8000/api/auth/login', 
    credentials,
    { 
      headers: { 
        'Content-Type': 'application/x-www-form-urlencoded' 
      } 
    }
  );
  
  // Check if login was successful
  if (loginRes.status !== 200) {
    console.error(`Login failed with status ${loginRes.status}: ${loginRes.body}`);
    throw new Error('Authentication failed');
  }
  
  // Extract the token
  const responseBody = JSON.parse(loginRes.body);
  const token = responseBody.access_token;
  
  if (!token) {
    console.error('No access token found in response:', responseBody);
    throw new Error('No access token in response');
  }
  
  console.log('Successfully obtained access token');
  return { token: token };
}
