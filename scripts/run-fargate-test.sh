#!/bin/bash
# Script to run load tests against the Fargate-like environment

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to print section headers
print_header() {
  echo -e "\n${YELLOW}==== $1 ====${NC}\n"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
  exit 1
fi

# Check if docker-compose exists
if ! command_exists docker-compose; then
  echo -e "${RED}Error: docker-compose is not installed. Please install it and try again.${NC}"
  exit 1
fi

# Check if k6 exists
if ! command_exists k6; then
  echo -e "${YELLOW}Warning: k6 is not installed. You won't be able to run load tests.${NC}"
  echo -e "Install k6 from https://k6.io/docs/getting-started/installation/"
fi

# Check if .env file exists
if [ ! -f .env ]; then
  echo -e "${YELLOW}Warning: .env file not found. Creating a sample .env file...${NC}"
  cat > .env << 'EOF'
MYSQL_HOST=sales_assistant_db
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=sales_assistant
MYSQL_ROOT_PASSWORD=root
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
# Add other required environment variables here
EOF
  echo -e "${YELLOW}Please update the .env file with your actual values before proceeding.${NC}"
  echo -e "Press Enter to continue or Ctrl+C to exit and update the .env file..."
  read -r
fi

# Function to start the Fargate-like environment
start_environment() {
  print_header "Starting Fargate-like Environment"
  echo "Building and starting containers..."
  docker-compose -f docker-compose.fargate.yaml up -d --build
  
  # Wait for the application to be ready
  echo "Waiting for the application to be ready..."
  for i in {1..30}; do
    if curl -s http://localhost:8000/docs > /dev/null; then
      echo -e "${GREEN}Application is ready!${NC}"
      return 0
    fi
    echo -n "."
    sleep 2
  done
  
  echo -e "\n${RED}Timed out waiting for the application to start.${NC}"
  echo "Check the logs with: docker-compose -f docker-compose.fargate.yaml logs"
  
  # Ask if user wants to see logs
  echo -e "Do you want to see the logs? (y/n): "
  read -r show_logs
  if [[ "$show_logs" =~ ^[Yy]$ ]]; then
    docker-compose -f docker-compose.fargate.yaml logs
  fi
  
  # Ask if user wants to continue anyway
  echo -e "Do you want to continue anyway? (y/n): "
  read -r continue_anyway
  if [[ "$continue_anyway" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Continuing despite startup issues...${NC}"
    return 0
  else
    return 1
  fi
}

# Function to stop the Fargate-like environment
stop_environment() {
  print_header "Stopping Fargate-like Environment"
  docker-compose -f docker-compose.fargate.yaml down
  echo -e "${GREEN}Environment stopped.${NC}"
}

# Function to show container stats
show_stats() {
  print_header "Container Resource Usage"
  echo "Press Ctrl+C to stop monitoring."
  docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"
}

# Function to run load tests
run_load_test() {
  print_header "Running Load Test"
  
  if ! command_exists k6; then
    echo -e "${RED}Error: k6 is not installed. Cannot run load tests.${NC}"
    echo -e "Install k6 from https://k6.io/docs/getting-started/installation/"
    return 1
  fi
  
  # Select which test to run
  echo -e "Select which load test to run:"
  echo -e "1. General API load test (default)"
  echo -e "2. Rank endpoint scalability test (gradually increases load)"
  echo -e "3. Specific 3-parallel rank test (IDs 1-5)"
  echo -n "Enter your choice [1-3]: "
  read -r test_choice
  
  # Set the test file based on user choice
  case $test_choice in
    2)
      test_file="tests/load-tests/rank-scalability-test.js"
      test_name="Rank Endpoint Scalability Test"
      ;;
    3)
      test_file="tests/load-tests/rank-specific-test.js"
      test_name="Specific 3-Parallel Rank Test"
      ;;
    *)
      test_file="tests/load-tests/load-test.js"
      test_name="General API Load Test"
      ;;
  esac
  
  # Check if the selected test file exists
  if [ ! -f "$test_file" ]; then
    echo -e "${RED}Error: Load test file not found at $test_file${NC}"
    return 1
  fi
  
  # Create a temporary copy of the load test file
  echo -e "Creating temporary load test file..."
  temp_file=$(mktemp)
  cp "$test_file" "$temp_file"
  
  # Ask if user wants to customize the load test
  echo -e "Do you want to customize the $test_name parameters? (y/n): "
  read -r customize
  
  if [[ "$customize" =~ ^[Yy]$ ]]; then
    echo -e "Enter the number of virtual users (default: follows configuration in the script): "
    read -r vus
    
    echo -e "Enter the duration in seconds (default: follows configuration in the script): "
    read -r duration
    
    # Run with custom parameters if provided
    if [ -n "$vus" ] && [ -n "$duration" ]; then
      echo -e "Starting $test_name with k6 (custom parameters)..."
      k6 run --vus "$vus" --duration "${duration}s" "$temp_file"
    elif [ -n "$vus" ]; then
      echo -e "Starting $test_name with k6 (custom VUs)..."
      k6 run --vus "$vus" "$temp_file"
    elif [ -n "$duration" ]; then
      echo -e "Starting $test_name with k6 (custom duration)..."
      k6 run --duration "${duration}s" "$temp_file"
    else
      echo -e "Starting $test_name with k6 (default parameters)..."
      k6 run "$temp_file"
    fi
  else
    echo -e "Starting $test_name with k6 (default parameters)..."
    k6 run "$temp_file"
  fi
  
  # Clean up
  rm "$temp_file"
}

# Function to show logs
show_logs() {
  print_header "Container Logs"
  docker-compose -f docker-compose.fargate.yaml logs --tail=100 -f
}

# Function to check environment status
check_environment_status() {
  print_header "Environment Status"
  
  if docker ps | grep -q "sales_assistant_api_fargate"; then
    echo -e "${GREEN}Fargate-like environment is running.${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "sales_assistant"
    return 0
  else
    echo -e "${RED}Fargate-like environment is not running.${NC}"
    return 1
  fi
}

# Main menu
show_menu() {
  clear
  echo -e "${YELLOW}===== AWS Fargate-like Environment Testing Tool =====${NC}"
  echo -e "${YELLOW}This tool helps you test your application in a Fargate-like environment${NC}"
  echo ""
  echo "1. Start Fargate-like environment"
  echo "2. Run load test"
  echo "3. Monitor resource usage"
  echo "4. View container logs"
  echo "5. Stop Fargate-like environment"
  echo "6. Check environment status"
  echo "7. View documentation"
  echo "0. Exit"
  echo ""
  echo -n "Enter your choice [0-7]: "
}

# Function to show documentation
show_documentation() {
  print_header "Fargate Testing Documentation"
  
  if [ -f "tests/load-tests/FARGATE_TESTING.md" ]; then
    # Check if markdown viewer is available
    if command_exists glow; then
      glow tests/load-tests/FARGATE_TESTING.md
    elif command_exists bat; then
      bat tests/load-tests/FARGATE_TESTING.md
    elif command_exists less; then
      less tests/load-tests/FARGATE_TESTING.md
    else
      cat tests/load-tests/FARGATE_TESTING.md
    fi
  else
    echo -e "${RED}Documentation file not found at tests/load-tests/FARGATE_TESTING.md${NC}"
  fi
}

# Main loop
while true; do
  show_menu
  read -r choice
  
  case $choice in
    1) start_environment ;;
    2) run_load_test ;;
    3) show_stats ;;
    4) show_logs ;;
    5) stop_environment ;;
    6) check_environment_status ;;
    7) show_documentation ;;
    0) 
      echo -e "${GREEN}Exiting...${NC}"
      # Check if environment is running and ask to stop it
      if docker ps | grep -q "sales_assistant_api_fargate"; then
        echo -e "${YELLOW}Fargate-like environment is still running.${NC}"
        echo -e "Do you want to stop it before exiting? (y/n): "
        read -r stop_before_exit
        if [[ "$stop_before_exit" =~ ^[Yy]$ ]]; then
          stop_environment
        fi
      fi
      exit 0
      ;;
    *)
      echo -e "${RED}Invalid option. Please try again.${NC}"
      sleep 2
      ;;
  esac
  
  echo ""
  echo -n "Press Enter to continue..."
  read -r
done
