#!/bin/bash

# Simple Tools REST API Server Test Script

echo "================================"
echo "Testing REST API Server"
echo "================================"
echo ""

BASE_URL="http://localhost:12000"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if server is running
echo -e "${BLUE}🔍 Checking server health...${NC}"
HEALTH=$(curl -s "$BASE_URL/health")
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Server is running${NC}"
    echo "$HEALTH" | jq '.'
else
    echo -e "${RED}❌ Server is not running. Please start it with ./run.sh${NC}"
    exit 1
fi

echo ""
echo "================================"
echo ""

# Test 1: Calculator - Addition
echo -e "${BLUE}📝 Test 1: Calculator - Addition (10 + 5)${NC}"
curl -s "$BASE_URL/calculator?operation=add&a=10&b=5" | jq '.'

echo ""
echo "================================"
echo ""

# Test 2: Calculator - Division
echo -e "${BLUE}📝 Test 2: Calculator - Division (100 ÷ 4)${NC}"
curl -s "$BASE_URL/calculator?operation=divide&a=100&b=4" | jq '.'

echo ""
echo "================================"
echo ""

# Test 3: Calculator - Multiplication
echo -e "${BLUE}📝 Test 3: Calculator - Multiplication (6 × 7)${NC}"
curl -s "$BASE_URL/calculator?operation=multiply&a=6&b=7" | jq '.'

echo ""
echo "================================"
echo ""

# Test 4: Weather - Single day
echo -e "${BLUE}📝 Test 4: Weather Forecast - London (1 day)${NC}"
curl -s "$BASE_URL/weather/forecast?city=London&days=1" | jq '.'

echo ""
echo "================================"
echo ""

# Test 5: Weather - Multiple days
echo -e "${BLUE}📝 Test 5: Weather Forecast - New York (3 days)${NC}"
curl -s "$BASE_URL/weather/forecast?city=New%20York&days=3" | jq '.'

echo ""
echo "================================"
echo ""

echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "💡 To view interactive API docs, visit: http://localhost:12000/docs"
