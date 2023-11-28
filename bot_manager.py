import asyncio
import nextcord
from nextcord.ext import commands
import json

async def main():
    
    ## load in the config for the bot, mainly the token and test guild
    try:
        config = json.load(open("myConfig.json"))
        TOKEN = config["token"]
        guild = config["guild"]
        botname = "trazom_cog"
    except:
        print("Manager: couldn't load config file!")
        return

    intents = nextcord.Intents.default()
    client = commands.Bot(command_prefix = "~", default_guild_ids = [guild], intents = intents)

    ## adding in the actual Cog
    @client.slash_command(name = "load", guild_ids=[guild])
    async def load_cmd(interaction: nextcord.Interaction):
        client.load_extension(botname)
        await client.sync_application_commands(guild_id = guild)
        await interaction.response.send_message(botname + " started!")

    ## reload cmd
    @client.slash_command(name = "reload", guild_ids=[guild])
    async def reload_cmd(interaction: nextcord.Interaction):
        client.reload_extension(botname)
        await client.sync_application_commands(guild_id = guild)
        await interaction.response.send_message("Reloading ...")

    await client.start(token = TOKEN)


## starting point of the bot manager
asyncio.run(main())
