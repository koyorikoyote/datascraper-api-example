# AWS Fargate-like Environment for Load and Performance Testing

This setup replicates AWS Fargate constraints in a local Docker Compose environment for load and performance testing.

## Fargate Attributes Simulated

| AWS Fargate Attribute | Local Equivalent |
|-----------------------|------------------|
| OS / Arch | Linux / x86_64 |
| vCPU | 0.5 vCPU (limit) |
| Memory | 1 GB (limit) |
| Platform Version | Linux + Docker |
| Launch type | Docker container |
| ECS Task Definition | Docker Compose setup |

## Files Created/Modified

1. `docker-compose.fargate.yaml` - Docker Compose configuration with Fargate-like resource constraints
2. `Dockerfile.fargate` - Optimized Dockerfile for the constrained environment
3. `docker-entrypoint.fargate.sh` - Optimized entrypoint script with reduced resource usage

## How to Use

### Starting the Fargate-like Environment

```bash
# Build and start the Fargate-like environment
docker-compose -f docker-compose.fargate.yaml up --build
```

### Running Load Tests

You can use tools like [k6](https://k6.io/), [Locust](https://locust.io/), or [Apache JMeter](https://jmeter.apache.org/) to perform load testing against this environment.

Example with k6:

```bash
# Install k6
# For Ubuntu/Debian
sudo apt-get install k6

# For macOS
brew install k6

# Create a simple load test script (save as load-test.js)
cat > load-test.js << 'EOF'
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 10,  // Number of virtual users
  duration: '30s',  // Test duration
};

export default function () {
  http.get('http://localhost:8000/api/v1/your-endpoint');
  sleep(1);
}
EOF

# Run the load test
k6 run load-test.js
```

## Monitoring Resource Usage

To monitor resource usage during testing:

```bash
# Install Docker stats helper
pip install docker-stats-monitor

# Monitor container resource usage
docker stats sales_assistant_api_fargate
```

## Performance Optimization Notes

The Fargate-like environment has been optimized in several ways:

1. **Resource Constraints**:
   - CPU limited to 0.5 vCPU
   - Memory limited to 1 GB
   - Shared memory reduced to 256 MB

2. **Application Optimizations**:
   - Reduced Selenium memory usage with optimized Chrome flags
   - Optimized Python memory usage with environment variables
   - Single worker for uvicorn to stay within resource constraints
   - Limited concurrency to prevent resource exhaustion

3. **Database Optimizations**:
   - Reduced MySQL buffer pool size
   - Limited max connections
   - Optimized character set and collation settings

## Comparing with AWS Fargate

When comparing performance metrics between this local environment and actual AWS Fargate:

1. **Network Latency**: Local environment will have lower network latency than AWS Fargate
2. **I/O Performance**: Local disk I/O may differ from AWS Fargate EBS volumes
3. **CPU Performance**: Local CPU throttling is approximate and may not exactly match AWS Fargate behavior

For the most accurate comparison, record baseline metrics in both environments and calculate relative performance differences.

## Troubleshooting

If the application fails to start or performs poorly:

1. Check container logs:
   ```bash
   docker-compose -f docker-compose.fargate.yaml logs fastapi
   ```

2. Verify resource constraints are applied:
   ```bash
   docker inspect sales_assistant_api_fargate | grep -A 20 "HostConfig"
   ```

3. If Selenium fails to start, you may need to increase the memory limit slightly:
   ```bash
   # Edit docker-compose.fargate.yaml to increase memory limit to 1.25G
   ```
