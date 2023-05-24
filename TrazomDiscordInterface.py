import discord
from asyncio import Queue
from discord import app_commands

##  an override / child class of the default discord Client
#   Following the discord.py example code, this is done to
#   be able to sync to the server in the setup hook but in practice,
#   I found that I had to call the sync in the on_ready for the
#   right commands to be displayed in the actual text channels (the
#   server settings showed the right ones)
class MyClient(discord.Client):

    #   storing data structures inside the class since I am defining
    #   commands inside the setup hook. Unsure if this has any negative
    #   effects
    def __init__(self, *, intents: discord.Intents, guild, queue: Queue):
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)
        self.myguild = guild
        self.queryq = queue
        

    async def setup_hook(self):

        @self.tree.command(name = "print", description = "parrot back") 
        async def first_command(interaction, arg1: str):
            await interaction.response.send_message(arg1)

        @self.tree.command(name = "p", description = "youtube lookup") 
        async def query(interaction, arg1: str):
            response_msg = "placing " + arg1 + " into lookup queue"
            self.queryq.put_nowait(arg1)
            await interaction.response.send_message(response_msg)

##  Main function / class for the discord interface module. This consists of
#   two submodules, the input interface and the discord voice interface.
#   In practice the input submodule is fully implemented in commands while
#   the voice interface will be more integrated with the library / player module
class main:

    def __init__(self, token, guild, queue):
        self.token = token
        self.guild = discord.Object(id = guild)
        self.intents = discord.Intents.default()
        self.client = MyClient(intents = self.intents, guild = self.guild, queue = queue)

    ## starts the discord client and does the syncing in the on_ready event
    async def start(self):

        client = self.client
        # run at the end of this function

        @client.event
        async def on_ready():
            #self.tree.copy_global_to(guild=self.myguild)
            await client.tree.sync()
            print("Ready!")

        task = client.start(token = self.token)

        await task

