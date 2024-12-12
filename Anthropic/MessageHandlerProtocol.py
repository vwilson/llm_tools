from typing import List, Protocol

import discord


class MessageHandlerProtocol(Protocol):
    files: List[discord.File]  