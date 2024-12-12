from __future__ import annotations
from typing import List
import discord
import openai.types.chat as chat
from abc import ABC, abstractmethod
from dataclasses import dataclass
from MessageHandlerProtocol import MessageHandlerProtocol
 
@dataclass
class ToolBase(ABC):    
    class MessageHandler(MessageHandlerProtocol):
        def __init__(self):
            self.files : List[discord.File] = []

    emoji: str
    parameter: chat.ChatCompletionToolParam

    @abstractmethod
    def create_chat_completion_tool_param():
        pass

    @abstractmethod
    async def get_tool_result(
            self, 
            tool_args: str, 
            message_handler : MessageHandlerProtocol) -> str:
        pass        

    async def on_interaction(self, interaction: discord.Interaction, arguments: str, success_response: str):
        assert isinstance(interaction.channel, discord.TextChannel)
        
        await interaction.response.send_message("🤔")

        message_handler = self.MessageHandler()
        
        async with interaction.channel.typing():
            try:
                await self.get_tool_result(arguments, message_handler)

                if message_handler.files:
                    await interaction.edit_original_response(
                        content=success_response,
                        attachments=message_handler.files)

            except Exception as e:                
                await interaction.edit_original_response(
                   content=f"I'm sorry, {interaction.user.mention}, I'm afraid I can't do that.\n{str(e)}",
                )
