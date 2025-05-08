from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from httpx import AsyncClient
from urllib.parse import urlencode
import os
import redis.asyncio as redis
import json

# Load environment variables from .env file
load_dotenv()

# Access environment variables
api_key = os.getenv("API_KEY")
if not api_key:
    raise RuntimeError("API_KEY environment variable is not set.")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize Redis connection
redis_client = redis.from_url("redis://localhost", decode_responses=True)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "weather_data": None})

@app.post("/", response_class=HTMLResponse)
async def get_weather(request: Request, city: str = Form(...)):
    # Fetch data from the API
    base_url = "http://api.weatherapi.com/v1/current.json"
    query_params = {
        "key": api_key,
        "q": city,
        "aqi": "no"
    }
    url = f"{base_url}?{urlencode(query_params)}"

    async with AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            api_weather_data = {
                "city": data["location"]["name"],
                "country": data["location"]["country"],
                "temperature_c": data["current"]["temp_c"],
                "condition": data["current"]["condition"]["text"]
            }
            
            # Check if the data is cached in Redis
            cached_data = await redis_client.get(city.lower())
            if cached_data:
                cached_weather_data = json.loads(cached_data)
                # Compare API data with cached data
                if cached_weather_data != api_weather_data:
                    # Update cache if data is different
                    await redis_client.set(city.lower(), json.dumps(api_weather_data), ex=3600)
                    weather_data = api_weather_data
                else:
                    weather_data = cached_weather_data
            else:
                # Cache the data in Redis for 1 hour (3600 seconds)
                await redis_client.set(city.lower(), json.dumps(api_weather_data), ex=3600)
                weather_data = api_weather_data
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching weather data: {str(e)}")

    return templates.TemplateResponse("index.html", {"request": request, "weather_data": weather_data})