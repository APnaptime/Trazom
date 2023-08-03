import asyncio
import nextcord
from nextcord.ext import commands
from nextcord.ext import application_checks
import json

from nextcord.ext.commands.context import Context

from trazom import Trazom

# a Cog collection of commands and listeners to handle interfacing
# with the discord bot. Only one instance of this cog will exist
# for a number of player instances (1 per vc/server max) so commands
# should alter their behavior based on the interaction's (context) guild ID
class TrazomCog(commands.Cog):

    # default init function, called by add_cog
    def __init__(self, bot):
        self.bot : commands.Bot = bot
        self.players = {} # dictionary of guild_id : trazom instance mappings

    # gets the player associated with a guild/vc andcreates a new trazom instance
    # if one doesn't already exist, makes a new trazom instance
    async def get_player(self, interaction: nextcord.Interaction):
        # Check to see if we have a trazom instance in the player dict
        if interaction.guild_id in self.players:
            return self.players[interaction.guild_id]
        else:
            return None

    # debug printout function
    def dump_status():
        pass

    def remove_player(self, guild_id): # TODO: profile memory usage, is trazom for sure done running? and does del free the finished trazom
        if guild_id in self.players.keys():
            self.players[guild_id].stop()
            del self.players[guild_id]

    def cog_unload(self) -> None:
        print("trazom unloading!")
        for guild_id in self.players.keys():
            self.remove_player(guild_id)
        return super().cog_unload()

    ## slash command definitions

    async def cmd_check(self, interaction: nextcord.Interaction):
        guild = interaction.guild_id
        voice_channel = interaction.user.voice.channel
        # ensure the caller is in a vc
        if voice_channel is None:
            await interaction.response.send_message("You must be connected to a voice channel~")
            raise commands.CommandError("caller not in a voice channel")

        # ensure the guild the caller is in has a trazom instance
        if not guild in self.players:
            # create a new trazom instance
            new_instance = Trazom(interaction = interaction)
            new_instance.start()
            self.players[guild] = new_instance        

        # ensure the vc of trazom and the caller are the same
        if not voice_channel == self.players[guild].vchannel:
            await interaction.response.send_message("You must be in the same voice channel~")
            raise commands.CommandError("caller not in same voice channel")

    # play command:
    @nextcord.slash_command(name = "p", description = "Adds a song or playlist to be played")
    async def play_cmd(self, interaction: nextcord.Interaction, query: str):
        await self.cmd_check(interaction)
        await interaction.response.send_message("p ACK")
        # at this point, we should be guarenteed to have a trazom instance created
        # so we send the query to the trazom instance
        self.players[interaction.guild_id].play(interaction, query)

    # skip command:
    @nextcord.slash_command(name = "s", description = "Skip: skips the currently playing song")
    async def skip_cmd(self, interaction: nextcord.Interaction):
        await self.cmd_check(interaction)
        await interaction.response.send_message("s ACK")
        self.players[interaction.guild_id].skip()

    # queue command:
    @nextcord.slash_command(name = "q", description = "Queue: shows the songs to be played")
    async def queue_cmd(self, interaction: nextcord.Interaction):
        await self.cmd_check(interaction)
        await interaction.response.send_message("q ACK")

    # remove command:
    @nextcord.slash_command(name = "r", description = "Remove: deletes a song from the Queue by giving a #")
    async def remove_cmd(self, interaction: nextcord.Interaction):
        await self.cmd_check(interaction)
        await interaction.response.send_message("r ACK")

    # exit command:
    @nextcord.slash_command(name = "e", description = "Exit: Trazom - exit stage right")
    async def exit_cmd(self, interaction: nextcord.Interaction):
        await self.cmd_check(interaction)
        self.remove_player(interaction.guild_id)
        await interaction.response.send_message("exit ACK")


# function called by the manager somewhere that is run on startup. The cog itself is instantiated
# in the add_cog call 
async def setup(bot):
    bot.add_cog(TrazomCog(bot))
    print("trazom cog loaded")

def teardown(bot):
    print("trazom cog unloaded")
