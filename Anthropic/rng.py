import json
import random
from dataclasses import dataclass, field
from typing import Dict, Any
from anthropic.types import ToolParam
from tools.toolbase import ToolBase

@dataclass
class RngTool(ToolBase):
    emoji: str = "🎲"

    @staticmethod
    def create_anthropic_tool_param() -> ToolParam:
        return ToolParam(
            {
                "name": "rng",
                "description": "Generate a random number between min and max, inclusive",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "min": {
                            "type": "number",
                            "description": "The minimum number"
                        },
                        "max": {
                            "type": "number",
                            "description": "The maximum number"
                        },
                        "n": {
                            "type": "number",
                            "description": "The number of random numbers to generate"
                        },
                        "response": {
                            "type": "string",
                            "description": "The confirmation message to the user."
                        }
                    },
                    "required": ["min", "max"],
                }
            }
        )

    parameter: ToolParam = field(default_factory=create_anthropic_tool_param)

    async def get_tool_result(self, arguments: str, message_handler) -> str:
        args = json.loads(arguments)

        n = args.get("n", 1)

        rn = [random.randint(args["min"], args["max"]) for i in range(n)]

        return json.dumps({"result": rn})