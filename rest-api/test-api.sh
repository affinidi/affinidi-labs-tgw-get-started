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

# Test 1: Calculator - Addition (POST with JSON body)
echo -e "${BLUE}📝 Test 1: Calculator - Addition (10 + 5)${NC}"
curl -s -X POST "$BASE_URL/calculator" \
  -H "Content-Type: application/json" \
  -d '{"operation":"add","a":10,"b":5}' | jq '.'

echo ""
echo "================================"
echo ""

# Test 2: Calculator - Division (POST with JSON body)
echo -e "${BLUE}📝 Test 2: Calculator - Division (100 ÷ 4)${NC}"
curl -s -X POST "$BASE_URL/calculator" \
  -H "Content-Type: application/json" \
  -d '{"operation":"divide","a":100,"b":4}' | jq '.'

echo ""
echo "================================"
echo ""

# Test 3: Calculator - Multiplication (POST with JSON body)
echo -e "${BLUE}📝 Test 3: Calculator - Multiplication (6 × 7)${NC}"
curl -s -X POST "$BASE_URL/calculator" \
  -H "Content-Type: application/json" \
  -d '{"operation":"multiply","a":6,"b":7}' | jq '.'

echo ""
echo "================================"
echo ""

# Test 4: Greeting - Hello World (GET)
echo -e "${BLUE}📝 Test 4: Greeting - Hello World${NC}"
curl -s "$BASE_URL/greeting?name=World" | jq '.'

echo ""
echo "================================"
echo ""

# Test 5: Greeting - Hello Alice (GET)
echo -e "${BLUE}📝 Test 5: Greeting - Hello Alice${NC}"
curl -s "$BASE_URL/greeting?name=Alice" | jq '.'

echo ""
echo "================================"
echo ""

# Test 6: Weather - Single day
echo -e "${BLUE}📝 Test 6: Weather Forecast - London (1 day)${NC}"
curl -s "$BASE_URL/weather/forecast?city=London&days=1" | jq '.'

echo ""
echo "================================"
echo ""

# Test 7: Weather - Multiple days
echo -e "${BLUE}📝 Test 7: Weather Forecast - New York (3 days)${NC}"
curl -s "$BASE_URL/weather/forecast?city=New%20York&days=3" | jq '.'

echo ""
echo "================================"
echo ""

echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "💡 To view interactive API docs, visit: http://localhost:12000/docs"
