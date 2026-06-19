#!/bin/bash

# PreVisit System - Launch Script
# Runs both backend and frontend simultaneously

set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAST_START=false
for arg in "$@"; do
    case "$arg" in
        --fast)
            FAST_START=true
            ;;
        *)
            echo -e "${RED}❌ Unknown argument: $arg${NC}"
            echo "Usage: ./run.sh [--fast]"
            exit 1
            ;;
    esac
done

BACKEND_PORT=8000
BACKEND_HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/health"
BACKEND_LOG="${TMPDIR:-/tmp}/previsit-backend.log"
BACKEND_PID=""
FRONTEND_PID=""

# Function to print section header
print_header() {
    echo -e "${YELLOW}----------------------------------------${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}----------------------------------------${NC}"
}

# Function to check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ Error: $1 is not installed${NC}"
        exit 1
    fi
}

stop_backend() {
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${YELLOW}Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    BACKEND_PID=""
}

stop_frontend() {
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    FRONTEND_PID=""
}

show_backend_log_tail() {
    if [ -f "$BACKEND_LOG" ]; then
        echo -e "${RED}Recent backend output:${NC}"
        tail -n 30 "$BACKEND_LOG"
    fi
}

fail_backend() {
    local message="$1"
    echo -e "${RED}❌ ${message}${NC}"
    show_backend_log_tail
    stop_backend
    exit 1
}



# Cleanup function to kill both processes on exit
cleanup() {
    echo -e "\n${YELLOW}----------------------------------------${NC}"
    echo -e "${YELLOW}Stopping PreVisit System...${NC}"
    echo -e "${YELLOW}----------------------------------------${NC}"
    stop_backend
    stop_frontend
    echo -e "${GREEN}✅ System stopped gracefully${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) to cleanup
trap cleanup SIGINT SIGTERM

print_header "🚀 Starting PreVisit System..."

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
check_command python3
check_command node
check_command npm
check_command curl
echo -e "${GREEN}✅ All prerequisites found${NC}"

# Start backend
echo -e ""
print_header "Starting Backend (FastAPI)..."
cd backend
if [ ! -d "../.venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv ../.venv
fi
# shellcheck disable=SC1091
source ../.venv/bin/activate
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${YELLOW}Starting backend server...${NC}"
if [ "$FAST_START" = true ]; then
    export SKIP_HEALTH_CHECK=true
    echo -e "${YELLOW}Fast mode: skipping LLM health check (SKIP_HEALTH_CHECK=true)${NC}"
fi
: > "$BACKEND_LOG"
uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to be healthy
echo -e "${YELLOW}Waiting for backend health check...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
HEALTHY=false
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s --connect-timeout 2 "$BACKEND_HEALTH_URL" > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}✅ Backend running at: http://localhost:${BACKEND_PORT}${NC}"
else
    fail_backend "Backend failed to become healthy after $MAX_RETRIES seconds"
fi

# Start frontend
echo -e ""
print_header "Starting Frontend (Next.js)..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    npm install
fi
echo -e "${YELLOW}Starting frontend server...${NC}"
npm run dev &
FRONTEND_PID=$!
cd ..
sleep 5
if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo -e "${GREEN}✅ Frontend running at: http://localhost:3000${NC}"
else
    echo -e "${RED}❌ Failed to start frontend${NC}"
    stop_backend
    exit 1
fi

echo -e ""
print_header "System is Ready!"
echo -e "${GREEN}✅ Backend: http://localhost:${BACKEND_PORT}${NC}"
echo -e "${GREEN}✅ Frontend: http://localhost:3000${NC}"
echo -e ""
echo -e "${YELLOW}Press CTRL+C to stop everything${NC}"
echo -e "${YELLOW}----------------------------------------${NC}"

# Wait for processes
wait
