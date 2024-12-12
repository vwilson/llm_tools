from dataclasses import dataclass, field
import datetime
import json
import discord
import emojis
import logging
from anthropic import Anthropic
from anthropic.types import MessageParam
from tools.toolbase import ToolBase
import utilities.discord as discord_utilities
import utilities.openai as openai_utilities

from config import CONFIG, DISCORD_MAX_MESSAGE_LENGTH
from typing import List

@dataclass
class AnthropicMessageHandler:
    standard_tools : List[ToolBase]
    admin_tools : List[ToolBase]

    @staticmethod   
    def get_empty_file_list() -> List[discord.File]:
        return []
    
    files : List[discord.File] = field(default_factory=get_empty_file_list)

    anthropic_client = Anthropic(
        # defaults to os.environ.get("ANTHROPIC_API_KEY")        
    )

    async def get_conversation(
            self,
            message: discord.Message) -> List[discord.Message]:
        conversation : List[discord.Message] = [message]

        while conversation[0].reference is not None and isinstance(conversation[0].reference.resolved, discord.Message):
            conversation.insert(0, await conversation[0].reference.resolved.fetch())
            
        return conversation

    async def on_message(
            self,
            message: discord.Message):
        
        conversation = await self.get_conversation(message)

        #convert the messages to chat completion params
        chat_completion_messages = [await discord_utilities.discord_message_to_openai_chat_completion_param(m) for m in conversation]

        logging.info(f"Found {len(chat_completion_messages)} messages in the conversation.")

        await self.get_discord_message_response(
            messages=chat_completion_messages, #type: ignore
            discord_message=message)


    async def get_discord_message_response(
    self,
    discord_message: discord.Message,
    messages: list[MessageParam],        
    temperature: float = 1.0,
    max_tokens: int = 1024):
        logging.info(f"Getting discord message response with claude...")

        author = discord_message.author    
        
        available_tools: List[ToolBase] = self.standard_tools + (self.admin_tools if author.id == CONFIG.admin_user_id else [])

        try:
            chat_completion = self.anthropic_client.messages.create(
                system=CONFIG.system_message,
                messages=messages,
                model="claude-3-5-sonnet-20241022",                
                max_tokens=max_tokens,
                tools=[t.parameter for t in available_tools]
            )
        except Exception as e:
            logging.exception(e)
            discord_message = await discord_message.reply(content=f"I'm sorry, {author.mention}, I'm afraid I can't do that.\n{e}")
            await discord_message.add_reaction(emojis.HAL9000)        
            return
        
        # Process tool calls
        tool_contents = [c for c in chat_completion.content if c.type == "tool_use"]
        # Process text content
        text_content = next((c for c in chat_completion.content if c.type == "text"), None)
        if tool_contents:
            thinking_message = await discord_message.reply("🤔")
            await discord_utilities.add_model_reactions("opus", thinking_message)

            for tool_content in tool_contents:
                tool_name = tool_content.name
                tool_args = tool_content.input
                tool = next((t for t in available_tools if t.parameter["name"] == tool_name), None)

                if tool:
                    await thinking_message.add_reaction(tool.emoji)
                    try:
                        tool_result = await tool.get_tool_result(json.dumps(tool_args), self)
                        # Attempt to parse the tool_result as JSON, but use it as a string if it fails
                        try:
                            json.loads(tool_result)
                        except json.JSONDecodeError:
                            tool_result = json.dumps(tool_result)    

                        # Send tool result back to the model
                        follow_up_message = self.anthropic_client.messages.create(
                            system=f'The current time is {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC. Your responses are sent through Discord.',
                            messages=messages + [
                                {
                                    "role": "assistant",
                                    "content": [
                                        {"type": "tool_use", "name": tool_name, "input": tool_args, "id": tool_content.id}
                                    ]
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "tool_result", "tool_use_id": tool_content.id, "content": tool_result}
                                    ]
                                }
                            ],
                            model="claude-3-5-sonnet-20240620",
                            max_tokens=max_tokens,
                            tools=[t.parameter for t in available_tools]
                        )

                        # Process the follow-up message
                        follow_up_text = next((c for c in follow_up_message.content if c.type == "text"), None)
                        if follow_up_text:
                            await self.send_response(content=follow_up_text.text, message=thinking_message, is_edit=True)
                        else:
                            await thinking_message.edit(content="I processed the tool result, but I don't have any additional comments.")

                    except Exception as e:
                        logging.exception(e)
                        await thinking_message.add_reaction(emojis.HAL9000)
                        await thinking_message.edit(content=f"I encountered an error while using the {tool_name} tool: {str(e)}")
                else:
                    await thinking_message.edit(content=f"I'm sorry, {author.mention}, I'm afraid I can't do that.\nI don't know how to use the tool {tool_name}.")
                    await thinking_message.add_reaction(emojis.HAL9000)

        elif text_content:
            await self.send_response(content=text_content.text, message=discord_message, is_edit=False)

        elif not text_content:
            await discord_message.reply(content=f"I'm sorry, {author.mention}, but I didn't generate any response or tool calls.")

    async def send_response(
            self, 
            content: str, 
            message: discord.Message, 
            is_edit: bool):
        chunks = [content[i:i + DISCORD_MAX_MESSAGE_LENGTH] for i in range(0, len(content), DISCORD_MAX_MESSAGE_LENGTH)]
        start = 0
        if is_edit:
            message = await message.edit(content=chunks[start])
            start += 1
        
        for i in range(start, len(chunks)):
            message = await message.reply(content = chunks[i])
            #await discord_utilities.add_model_reactions("opus", message)
