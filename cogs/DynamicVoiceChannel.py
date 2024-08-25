import discord
from discord.ext import commands
from discord import app_commands
import configparser
import datetime
import json

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
                await self.create_notification(guild,member,new_channel.mention)

                await member.move_to(new_channel)

                def check(a, b, c):
                    return len(new_channel.members) == 0  

                await self.bot.wait_for('voice_state_update', check=check)
                await new_channel.delete()

    async def create_notification(self, guild : discord.Guild ,member,channel_mention):
        embed = discord.Embed(title="語音頻道創建", description="", color=0x30D5C8)
        embed.add_field(name="頻道", value=channel_mention, inline=True)
        embed.add_field(name="創建者", value=member.display_name, inline=True)
        with open('DynamicVoiceNotificationList.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            notification_list = data[str(member.id)]
        notification_str = " ".join(f"<@{x}>" for x in notification_list)
        print(notification_str)
        if notification_str == "":
            notification_str = "無"
        embed.add_field(name="通知", value=notification_str, inline=False)
        embed.timestamp = datetime.datetime.now(datetime.UTC)
        channelID = self.config['DynamicVoiceChannel'].getint('notification_Channel')
        await guild.get_channel(channelID).send(embed=embed)
    
    @app_commands.command(name='訂閱語音通知')
    async def subscription(self,interaction: discord.Interaction, member: discord.Member):
        with open('DynamicVoiceNotificationList.json', 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault(str(member.id),[])
                data[str(member.id)].append(interaction.user.id)
                f.seek(0)
                json.dump(data, f, indent=4, separators=(',', ': '))
                f.truncate()
        await interaction.response.send_message('設置成功',ephemeral=True)
    @app_commands.command(name='取消訂閱語音通知')
    async def unsubscription(self,interaction: discord.Interaction, member: discord.Member):
        with open('DynamicVoiceNotificationList.json', 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data[str(member.id)].remove(interaction.user.id)
                f.seek(0)
                json.dump(data, f, indent=4, separators=(',', ': '))
                f.truncate()
        await interaction.response.send_message('設置成功',ephemeral=True)
async def setup(bot):
    await bot.add_cog(DynamicVoiceChannel(bot))