import datetime
import json
import requests
from dataclasses import dataclass, field
from typing import Dict, Any
from anthropic.types import ToolParam
from config import NASA_API_KEY
from tools.toolbase import ToolBase

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"

@dataclass 
class NasaApodTool(ToolBase):
    emoji: str = "🚀"

    @staticmethod
    def create_anthropic_tool_param() -> ToolParam:
        return ToolParam(
            {
                "name": "nasa_apod",
                "description": "Get an image of the day from NASA's Astronomy Picture of the Day.",
                "input_schema": {
                    "type": "object",
                    "properties": {    
                        "date": {
                            "type": "string",
                            "description": "The date of the image to retrieve (YYYY-MM-DD)."
                        }                
                    },
                    "required": [],
                }
            }
        )

    parameter: ToolParam = field(default_factory=create_anthropic_tool_param)

    async def get_tool_result(self, arguments: str, message_handler) -> str:
        args = json.loads(arguments)

        # Initialize params with api_key and thumbs as they can always be included
        params = {'api_key': NASA_API_KEY}
            
        if "date" in args:    
            params['date'] = args["date"]
        else:
            params['date'] = datetime.date.today().strftime("%Y-%m-%d")

        # ensure date is in YYYY-MM-DD format by trying to parse to a date
        try:
            datetime.datetime.strptime(params['date'], '%Y-%m-%d')
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")    
            
        # Make the GET request with the parameters
        response = requests.get(NASA_APOD_URL, params=params)
        if response.status_code == 200:
            return json.dumps(response.json())
        else:
            response.raise_for_status()
            return ""