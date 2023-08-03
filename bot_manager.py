import asyncio
import nextcord
from nextcord.ext import commands
import json
from trazom_cog import TrazomCog


async def main():
    
    ## load in the config for the bot, mainly the token and test guild
    try:
        config = json.load(open("myConfig.json"))
        TOKEN = config["token"]
        guild = config["guild"]
        botname = 'trazom_cog'
    except:
        print("Manager: couldn't load config file!")
        return
    
    ## Note:    client is used instead of bot to avoid needing a command prefix
    #           since that would require read message permissions which I would
    #           like to avoid. As a downside of using client, extensions can't
    #           be used limiting the effectiveness of cogs. However, this is just
    #           a bot manager for personal testing and all functionality of a
    #           module is independant of the manager's use of bot or client
    #           as long as the cog / module only uses client methods since
    #           bot inherits from client
    intents = nextcord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix = "~", default_guild_ids = [guild], intents = intents)
    #client = nextcord.Client()

    ## adding in the actual Cog
    @client.slash_command(name = "load", guild_ids=[guild])
    async def load_cmd(interaction: nextcord.Interaction):
        client.load_extension(botname)
        await client.sync_application_commands(guild_id = guild)
        await interaction.response.send_message("loaded " + botname)

    ## reload cmd
    @client.slash_command(name = "reload", guild_ids=[guild])
    async def reload_cmd(interaction: nextcord.Interaction):
        client.reload_extension(botname)
        await client.sync_application_commands(guild_id = guild)
        await interaction.response.send_message("reloaded " + botname)

    await client.start(token = TOKEN)


## starting point of the bot manager
asyncio.run(main())
