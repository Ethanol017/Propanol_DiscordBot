import discord
from discord.ext import commands
from discord import app_commands
import configparser

class DynamicVoiceChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.channel_ID = self.config['DynamicVoiceChannel'].getint('channel_ID')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel != after.channel:
            if after.channel and after.channel.id == self.channel_ID:  
                guild = member.guild
                category = after.channel.category  
                if category is None:
                    return
                
                overwrites = category.overwrites  

                new_channel = await guild.create_voice_channel(
                    f"{member.display_name}的頻道",
                    overwrites=overwrites,
                    category=category  
                )

                await member.move_to(new_channel)

                def check(a, b, c):
                    return len(new_channel.members) == 0  

                await self.bot.wait_for('voice_state_update', check=check)
                await new_channel.delete()

async def setup(bot):
    await bot.add_cog(DynamicVoiceChannel(bot))