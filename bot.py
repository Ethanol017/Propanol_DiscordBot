import discord
from discord import app_commands 
from discord.ext import commands
import os
from typing import Literal, Optional
from dotenv import load_dotenv

def run():
    dotenv_path = '.env'
    load_dotenv(dotenv_path)
    
    intents = discord.Intents.all()
    bot = commands.Bot(intents=intents,command_prefix="!!")
    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user}')

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')

    
    # from https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html
    @bot.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    
    #region load Unlode Relode Cog commands
    def get_cogs():
        cogs = []
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                cogs.append(filename[:-3])
        return cogs
    
    async def cog_autocomplete(interaction: discord.Interaction, current: str):
        cogs = get_cogs()
        return [app_commands.Choice(name=cog, value=cog) for cog in cogs if current.lower() in cog.lower()]
    # 加载單個插件
    @bot.tree.command(name='load')
    @commands.is_owner()
    async def load(interaction: discord.Interaction, extension: str):
        await bot.load_extension(f'cogs.{extension}')
        await interaction.response.send_message(f'Loaded {extension}', ephemeral=True)
    load.autocomplete('extension')(cog_autocomplete)

    # 卸載單個插件
    @bot.tree.command(name='unload')
    @commands.is_owner()
    async def unload(interaction: discord.Interaction, extension: str):
        await bot.unload_extension(f'cogs.{extension}')
        await interaction.response.send_message(f'Unloaded {extension}', ephemeral=True)
    unload.autocomplete('extension')(cog_autocomplete)

    # 重新加载單個插件
    @bot.tree.command(name='reload')
    @commands.is_owner()
    async def reload(interaction: discord.Interaction, extension: str):
        await bot.unload_extension(f'cogs.{extension}')
        await bot.load_extension(f'cogs.{extension}')
        await interaction.response.send_message(f'Reloaded {extension}', ephemeral=True)
    reload.autocomplete('extension')(cog_autocomplete)
    #endregion

    
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini')
    bot.run(config['Global'].get('TOKEN'))
     
if __name__ == "__main__":
    run() 