#!/usr/bin/env python3
"""
Simple Tools REST API Server

A REST API providing calculator and weather forecast endpoints.
"""

import random
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, List
import uvicorn
from contextlib import asynccontextmanager

# Server info
SERVER_INFO = {
    "name": "Simple Tools API",
    "version": "1.0.0"
}


# Request/Response Models
class CalculatorResponse(BaseModel):
    result: float = Field(..., description="The result of the calculation")
    expression: str = Field(..., description="The formatted expression")


class Temperature(BaseModel):
    fahrenheit: int = Field(..., description="Temperature in Fahrenheit")
    celsius: float = Field(..., description="Temperature in Celsius")


class ForecastDay(BaseModel):
    day: int = Field(..., description="Day number (1-7)")
    dayLabel: str = Field(..., description="Human-readable day label")
    condition: str = Field(..., description="Weather condition")
    temperature: Temperature
    humidity: int = Field(..., ge=0, le=100, description="Humidity percentage")
    wind: int = Field(..., description="Wind speed in mph")


class WeatherForecastResponse(BaseModel):
    city: str
    days: int
    forecast: List[ForecastDay]


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"\n{'='*60}")
    print(f"🚀 {SERVER_INFO['name']} v{SERVER_INFO['version']}")
    print(f"   Endpoints:")
    print(f"   - POST /calculator")
    print(f"   - GET /weather/forecast")
    print(f"   - GET /health")
    print(f"{'='*60}\n")
    yield
    # Shutdown
    print(f"\n👋 Server shutting down\n")


app = FastAPI(
    title="Simple Tools API",
    description="A simple REST API providing calculator and weather forecast tools",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", tags=["Health"])
@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "server": SERVER_INFO}


@app.get("/calculator", 
         response_model=CalculatorResponse,
         responses={
             400: {"model": ErrorResponse, "description": "Invalid request"}
         },
         tags=["Calculator"],
         summary="Perform arithmetic calculation",
         description="Execute basic arithmetic operations (add, subtract, multiply, divide)",
         operation_id="calculator")
async def calculate(
    operation: Literal["add", "subtract", "multiply", "divide"] = Query(..., description="The arithmetic operation to perform"),
    a: float = Query(..., description="First number"),
    b: float = Query(..., description="Second number")
):
    """
    Perform a calculation based on the operation and operands.
    
    - **operation**: The arithmetic operation (add, subtract, multiply, divide)
    - **a**: First number
    - **b**: Second number
    """

    print(f"🔢 Calculator: {operation} {a} and {b}")

    try:
        if operation == "add":
            result = a + b
            expr = f"{a} + {b}"
        elif operation == "subtract":
            result = a - b
            expr = f"{a} - {b}"
        elif operation == "multiply":
            result = a * b
            expr = f"{a} × {b}"
        elif operation == "divide":
            if b == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot divide by zero"
                )
            result = a / b
            expr = f"{a} ÷ {b}"
        
        print(f"✅ Result: {expr} = {result}")
        
        return CalculatorResponse(
            result=result,
            expression=expr
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Calculation error: {str(e)}"
        )


@app.get("/weather/forecast",
         response_model=WeatherForecastResponse,
         responses={
             400: {"model": ErrorResponse, "description": "Invalid request parameters"}
         },
         tags=["Weather"],
         summary="Get weather forecast",
         description="Retrieve weather forecast for a specified city",
         operation_id="weather_forecast")
async def get_weather_forecast(
    city: str = Query(..., description="Name of the city"),
    days: int = Query(1, ge=1, le=7, description="Number of days to forecast (1-7)")
):
    """
    Get weather forecast for a city.
    
    - **city**: Name of the city (required)
    - **days**: Number of days to forecast, between 1 and 7 (default: 1)
    """
    if not city or city.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="City is required"
        )
    
    print(f"🌤️  Weather forecast: {city} for {days} day(s)")
    
    # Generate mock weather forecast
    conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Stormy", "Snowy"]
    
    forecast_list = []
    
    for day in range(1, days + 1):
        condition = random.choice(conditions)
        temp_f = random.randint(45, 85)
        temp_c = round((temp_f - 32) * 5/9, 1)
        humidity = random.randint(30, 90)
        wind = random.randint(5, 25)
        
        day_label = "Today" if day == 1 else f"Day {day}"
        
        forecast_day = ForecastDay(
            day=day,
            dayLabel=day_label,
            condition=condition,
            temperature=Temperature(
                fahrenheit=temp_f,
                celsius=temp_c
            ),
            humidity=humidity,
            wind=wind
        )
        
        forecast_list.append(forecast_day)
    
    return WeatherForecastResponse(
        city=city,
        days=days,
        forecast=forecast_list
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Simple Tools REST API Server")
    print("=" * 60)
    print(f"Server: {SERVER_INFO['name']} v{SERVER_INFO['version']}")
    print(f"Endpoints: 3 (calculator, weather, health)")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=12000, log_level="info")
