import http from 'k6/http';
import { sleep, check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Simple UUID v4 generator function
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Custom metrics
const errors = new Counter('errors');
const requestDuration = new Trend('request_duration');
const successRate = new Rate('success_rate');

// Test configuration
export const options = {
  // Simulating AWS Fargate constraints
  // Gradually increase load to test performance under Fargate-like constraints
  stages: [
    { duration: '1m', target: 5 },   // Ramp up to 5 users
    { duration: '2m', target: 10 },  // Ramp up to 10 users
    { duration: '5m', target: 20 },  // Stress test with 20 users
    { duration: '2m', target: 0 },   // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests should be below 500ms
    'success_rate': ['rate>0.95'],    // 95% of requests should be successful
  },
};

// Endpoints to test - updated with actual API endpoints
const getEndpoints = [
  '/api/keywords',
  '/api/dashboard',
  '/api/contact-templates',
  '/api/score-settings',
  '/api/users'
];

// POST endpoints with sample request bodies
const postEndpoints = [
  {
    url: '/api/keywords',
    body: {
      keyword: 'test keyword ' + uuidv4(),
      fetch_status: 'pending',
      rank_status: 'pending',
      is_scheduled: false
    }
  },
  {
    url: '/api/batch-history',
    body: {
      execution_id_list: [1, 2, 3]
    }
  },
];

export default function (data) {
  // Randomly choose between GET and POST requests (70% GET, 30% POST)
  const isGetRequest = Math.random() < 0.7;
  
  let url, response, requestType, requestBody;
  let duration;
  
  // Add authentication with token from setup
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${data.token}`,
    }
  };
  
  if (isGetRequest) {
    // Select a random GET endpoint
    const endpoint = getEndpoints[Math.floor(Math.random() * getEndpoints.length)];
    url = `http://localhost:8000${endpoint}`;
    requestType = 'GET';
    params.tags = { endpoint: endpoint, method: 'GET' };
    
    // Make the GET request and record the response time
    const startTime = new Date();
    response = http.get(url, params);
    duration = new Date() - startTime;
  } else {
    // Select a random POST endpoint
    const endpointData = postEndpoints[Math.floor(Math.random() * postEndpoints.length)];
    url = `http://localhost:8000${endpointData.url}`;
    requestBody = JSON.stringify(endpointData.body);
    requestType = 'POST';
    params.tags = { endpoint: endpointData.url, method: 'POST' };
    
    // Make the POST request and record the response time
    const startTime = new Date();
    response = http.post(url, requestBody, params);
    duration = new Date() - startTime;
  }
  
  // Record custom metrics
  requestDuration.add(duration);
  
  // Check if the request was successful
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  // Record success rate
  successRate.add(success);
  
  // If the request failed, increment the error counter
  if (!success) {
    errors.add(1);
    console.log(`${requestType} request to ${url} failed with status ${response.status}`);
    if (requestBody) {
      console.log(`Request body: ${requestBody}`);
    }
    console.log(`Response body: ${response.body}`);
  }
  
  // Sleep between requests to simulate real user behavior
  sleep(Math.random() * 3 + 1); // Random sleep between 1-4 seconds
}

// Optional: Add a setup function to create test data or authenticate
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

// Optional: Add a teardown function to clean up after the test
export function teardown(data) {
  // Example: Logout or clean up test data
  // http.post('http://localhost:8000/api/v1/auth/logout', null, 
  //   { headers: { 'Authorization': `Bearer ${data.token}` } }
  // );
}
