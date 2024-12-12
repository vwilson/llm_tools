import json
import random
import openai.types.chat as chat

from dataclasses import dataclass, field

from tools.toolbase import ToolBase
import openai.types.shared_params as shared_params

@dataclass
class RngTool(ToolBase):
    emoji: str = "🎲"

    @staticmethod
    def create_chat_completion_tool_param():
        return chat.ChatCompletionToolParam(
            type="function",
            function=shared_params.FunctionDefinition(
                name="rng",
                description="Generate a random number between min and max, inclusive",
                parameters=dict(
                    type="object",
                    properties={
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
                            "type" :"string",
                            "description":"The confirmation message to the user."
                        }
                    },
                    required=["min", "max"],
                )
            )
        )

    parameter: chat.ChatCompletionToolParam = field(default_factory=create_chat_completion_tool_param)

    async def get_tool_result(self, arguments: str, message_handler) -> str:
        args = json.loads(arguments)

        n = args.get("n", 1)

        rn = [random.randint(args["min"], args["max"]) for i in range(n)]

        return json.dumps({ "result": rn })
