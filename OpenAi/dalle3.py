import base64
import logging
from typing import Literal
import discord
import json
from openai import AsyncOpenAI
import openai.types.chat as chat
import openai.types.shared_params as shared_params
from MessageHandlerProtocol import MessageHandlerProtocol

from dataclasses import dataclass, field
from io import BytesIO
from tools.toolbase import ToolBase

AVAILABLE_SIZES = Literal["1024x1024", "1792x1024", "1024x1792"]
AVAILABLE_QUALITIES = Literal["standard", "hd"]
AVAILABLE_STYLES = Literal["natural", "vivid"]

DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "hd"
DEFAULT_STYLE = "vivid"

MAX_IMAGES = 7

@dataclass
class DallE3Tool(ToolBase):
    emoji: str = "🎨"
    openai = AsyncOpenAI()

    @staticmethod
    def create_chat_completion_tool_param():
        return chat.ChatCompletionToolParam(
            type="function",
            function=shared_params.FunctionDefinition(
                name="dall-e-3",
                description="Generate an image from a text prompt using DALL-E-3",
                parameters=dict(
                    type="object",
                    properties={
                        "prompt": {
                            "type": "string",
                            "description": "The text prompt from which the image will be generated"                    
                        },                                      
                        "size": {
                            "type": "string",
                            "description": "The size of the image",
                            "enum": ["1024x1024", "1792x1024", "1024x1792"],
                            "default": "1024x1024"
                        },
                        "n": {  
                            "type": "number",
                            "description": "The number of images to generate (max 7)",
                            "default": 1
                        },
                    },
                    required=["prompt", "size"],
                ),
            )
        )
    
    parameter: chat.ChatCompletionToolParam = field(default_factory=create_chat_completion_tool_param)

    async def get_tool_result(self, arguments: str, message_handler: MessageHandlerProtocol) -> str:
        args = json.loads(arguments)

        prompt = args.get("prompt")
        size = args.get("size", DEFAULT_SIZE)
        n = args.get("n", 1)
        quality = args.get("quality", DEFAULT_QUALITY)
        style = args.get("style", DEFAULT_STYLE)
        
        logging.info(f"Generating image for '{args['prompt'][:20]}' with model 'dall-e-3' and size '{args['size']}' and quality='hd' and style='vivid' and n={1}")

        for i in range(n):
            imagesReponse = await self.openai.images.generate(
                prompt=prompt,
                model="dall-e-3",
                size=size,
                quality=quality,
                style=style,
                n=1,
                response_format="b64_json")
            
            if imagesReponse.data[0].b64_json is not None:
                bytes_io = BytesIO(base64.b64decode(imagesReponse.data[0].b64_json))
                bytes_io.seek(0)                            
                message_handler.files.append(discord.File(bytes_io, filename=f"dalle3-{i}.png"))

        filenames = list(map(lambda f: f'attachment://{f.filename}', message_handler.files))
        return json.dumps({ "filenames" : filenames })
        