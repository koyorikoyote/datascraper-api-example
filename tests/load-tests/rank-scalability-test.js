import http from 'k6/http';
import { sleep } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

// Custom metrics
const errors = new Counter('errors');
const requestDuration = new Trend('request_duration');
const successRate = new Rate('success_rate');
const activeVUs = new Trend('active_vus');

// Test configuration for scalability testing
export const options = {
  // Start with 1 VU, then gradually increase to find the breaking point
  stages: [
    { duration: '5m', target: 1 },   // Start with 1 VU
    { duration: '5m', target: 3 },   // Increase to 3 VUs
    { duration: '5m', target: 5 },   // Increase to 5 VUs
    { duration: '5m', target: 8 },   // Increase to 8 VUs
    { duration: '5m', target: 12 },  // Increase to 12 VUs
    { duration: '5m', target: 15 },  // Increase to 15 VUs
    { duration: '5m', target: 0 },   // Ramp down to 0
  ],
  // Set a very long timeout since each call takes ~30 minutes
  timeout: '120m',
};

// Generate a pool of keyword IDs to test with
// We'll need more than the original 5 IDs to test higher parallelism
function generateKeywordBatches() {
  const batches = [];
  
  // First few specific batches as requested
  batches.push({ ids: [1, 2] });
  batches.push({ ids: [3, 4] });
  batches.push({ ids: [5] });
  
  // Additional batches for higher parallelism testing
  // Using IDs 6-30 in pairs
  for (let i = 6; i <= 30; i += 2) {
    if (i + 1 <= 30) {
      batches.push({ ids: [i, i+1] });
    } else {
      batches.push({ ids: [i] });
    }
  }
  
  return batches;
}

const keywordBatches = generateKeywordBatches();

export default function (data) {
  // Record the number of active VUs for analysis
  activeVUs.add(__VU);
  
  // Determine which batch to use based on the VU number
  // This ensures each VU gets a different batch
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
  
  // Add a small sleep to prevent hammering the server too hard
  sleep(1);
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
