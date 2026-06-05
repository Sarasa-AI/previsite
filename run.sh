#!/bin/bash

# PreVisit System - Launch Script
# Runs both backend and frontend simultaneously

set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Cleanup function to kill both processes on exit
cleanup() {
    echo -e "\n${YELLOW}----------------------------------------${NC}"
    echo -e "${YELLOW}Stopping PreVisit System...${NC}"
    echo -e "${YELLOW}----------------------------------------${NC}"
    if [ -n "$BACKEND_PID" ]; then
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo -e "${YELLOW}Stopping backend (PID: $BACKEND_PID)...${NC}"
            kill "$BACKEND_PID" 2>/dev/null || true
            wait "$BACKEND_PID" 2>/dev/null || true
        fi
    fi
    if [ -n "$FRONTEND_PID" ]; then
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
            kill "$FRONTEND_PID" 2>/dev/null || true
            wait "$FRONTEND_PID" 2>/dev/null || true
        fi
    fi
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
echo -e "${GREEN}✅ All prerequisites found${NC}"

# Start backend
echo -e ""
print_header "Starting Backend (FastAPI)..."
cd backend
if [ ! -d "../.venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv ../.venv
fi
source ../.venv/bin/activate
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${YELLOW}Starting backend server...${NC}"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..
sleep 3
if kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${GREEN}✅ Backend running at: http://localhost:8000${NC}"
else
    echo -e "${RED}❌ Failed to start backend${NC}"
    exit 1
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
    cleanup
    exit 1
fi

echo -e ""
print_header "System is Ready!"
echo -e "${GREEN}✅ Backend: http://localhost:8000${NC}"
echo -e "${GREEN}✅ Frontend: http://localhost:3000${NC}"
echo -e ""
echo -e "${YELLOW}Press CTRL+C to stop everything${NC}"
echo -e "${YELLOW}----------------------------------------${NC}"

# Wait for processes
wait
