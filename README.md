Alembic commands
fastapi alembic revision --autogenerate -m "Initial migration"
fastapi alembic upgrade head

Seeder commands
python scripts/seed_db.py

Docker commands
docker exec -it sales_assistant_api /bin/bash

For fargate environment:
docker-compose -f docker-compose.fargate.yaml up -d
docker-compose -f docker-compose.fargate.yaml up --build -d

Logging
-------
Application logs are printed to stdout using the standard Python ``logging``
module. These logs will be forwarded to AWS CloudWatch in a future update.

Load Testing
-------
# Run the interactive load testing script (recommended)
./scripts/run-fargate-test.sh

# Direct load testing with k6
k6 run tests/load-tests/load-test.js

# Run load test with custom parameters
k6 run --vus 10 --duration 30s tests/load-tests/load-test.js

# Run the rank endpoint scalability test (gradually increases load)
k6 run tests/load-tests/rank-scalability-test.js

# Run the specific 3-parallel rank test (IDs 1-5)
k6 run tests/load-tests/rank-specific-test.js

# Monitor resource usage during testing
docker stats sales_assistant_api_fargate sales_assistant_mysql_fargate
