from dataclasses import dataclass, field
import json
import discord
import emojis
import logging
import openai
import openai.types.chat as chat
from tools.toolbase import ToolBase
import utilities.discord as discord_utilities
import utilities.openai as openai_utilities

from config import CONFIG, DISCORD_MAX_MESSAGE_LENGTH
from typing import List

@dataclass
class OpenAiMessageHandler:
    standard_tools : List[ToolBase]
    admin_tools : List[ToolBase]
    
    model : str = CONFIG.default_model

    @staticmethod   
    def get_empty_file_list() -> List[discord.File]:
        return []
    
    files : List[discord.File] = field(default_factory=get_empty_file_list)

    openai_client = openai.AsyncOpenAI()

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
        chat_completion_messages = [discord_utilities.discord_message_to_openai_chat_completion_param(m) for m in conversation]

        logging.info(f"Found {len(chat_completion_messages)} messages in the conversation.")

        await self.get_discord_message_response(
            messages=chat_completion_messages,
            discord_message=message)
        

    async def get_discord_message_response(
            self,
            discord_message: discord.Message,
            messages: list[chat.ChatCompletionMessageParam],        
            temperature: float = 1.0,
            max_tokens: int = 1024):
        
        logging.info(f"Getting discord message response with {self.model}...")

        author = discord_message.author    

        #messages.insert(0, openai_utilities.get_system_message(self.model))

        available_tools : List[ToolBase] = self.standard_tools + (self.admin_tools if author.id == CONFIG.admin_user_id else [])

        try:
            chat_completion = await self.openai_client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=temperature,
                top_p=1.0,
                #max_tokens=max_tokens,
                
                #tool_choice="auto",
                #tools=[t.parameter for t in available_tools],
                user=str(author.id))
        except Exception as e:
            logging.exception(e)
            discord_message = await discord_message.reply(content = f"I'm sorry, {author.mention}, I'm afraid I can't do that.\n{e}")
            await discord_message.add_reaction(emojis.HAL9000)        
            return
        
        #the model has generated a text reply
        if (chat_completion.choices[0].message.content is not None):        
            await self.send_response(content=chat_completion.choices[0].message.content, message=discord_message, is_edit=False)        

        #the model has elected to use a tool        
        elif (chat_completion.choices[0].message.tool_calls is not None):        
            discord_message = await discord_message.reply("🤔")
            #if ()
            #discord_message = await discord

            await discord_utilities.add_model_reactions(self.model, discord_message)

            num_tools = 0         

            self.files.clear()

            while chat_completion.choices[0].message.content is None: 
                assert chat_completion.choices[0].message.tool_calls is not None                    
               
                # it complains here but this works correctly
                messages += [chat_completion.choices[0].message]                 # type: ignore
                # do not try to fix this 

                for tool_call in chat_completion.choices[0].message.tool_calls:
                    #todo: do this in parallel
                    num_tools += 1                
                    
                    #log the tool call. i still think this may need to go into a db for full conversation history
                    log_message = f'{{ "id" = "{tool_call.id}", "name" = "{tool_call.function.name}", "args" = {tool_call.function.arguments}}}'            
                    logging.info(log_message)                

                    tool = next(filter(lambda t: t.parameter["function"]["name"] == tool_call.function.name, available_tools), None)
                    if tool is not None:
                        await discord_message.add_reaction(tool.emoji)
                        try:
                            tool_result = await tool.get_tool_result(tool_call.function.arguments, self)
                        except Exception as e:
                            logging.exception(e)
                            await discord_message.add_reaction(emojis.HAL9000)
                            tool_result = json.dumps({ "error" : str(e) })
                    else:
                        tool_result = f'{{ "status": "error", "message": "Unknown tool {tool_call.function.name}" }}'                   
                        await discord_message.add_reaction(emojis.HAL9000)          
                
                    tool_response = openai_utilities.get_function_message(                        
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                        content=tool_result)
                    
                    messages += [tool_response]

                    log_message = f'{{ "id" = "{tool_call.id}", "content" = {tool_response["content"]}}}'

                    logging.info(log_message)                
                
                #tool calls have been processed
                logging.info(f"Returning tool results to {self.model}...")            

                # hit the api again with our tool results in tow
                try:
                    chat_completion = await self.openai_client.chat.completions.create(
                        messages=messages,
                        model=self.model,
                        temperature=temperature,
                        top_p=1.0,
                        max_tokens=max_tokens,             
                        tool_choice="auto",
                        tools=[t.parameter for t in available_tools],
                        user=str(author.id))
                except openai.NotFoundError as e:
                    logging.exception(e)
                    await discord_message.add_reaction(emojis.HAL9000)
                    await discord_message.edit(content=f"I'm sorry, {author.mention}, I'm afraid I can't do that.\n{e}")
                    self.model = CONFIG.default_model
                    return
                except Exception as e:
                    logging.exception(e)
                    await discord_message.add_reaction(emojis.HAL9000)
                    await discord_message.edit(content=f"I'm sorry, {author.mention}, I'm afraid I can't do that.\n{str(e)}")
                    return                
                
            #handle files that may have been generated
            for file in self.files:
                discord_message = await discord_message.add_files(file)
            await self.send_response(content=chat_completion.choices[0].message.content, message=discord_message, is_edit=True)

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
            await discord_utilities.add_model_reactions(self.model, message)
