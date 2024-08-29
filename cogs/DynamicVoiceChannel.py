import discord
from discord.ext import commands
from discord import app_commands
import configparser
import datetime
import json

class DynamicVoiceChannel(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        
        self.config = configparser.ConfigParser()
        self.config.read('data/config.ini')
        self.channel_ID = self.config['DynamicVoiceChannel'].getint('channel_ID')
        self.channel_list = []

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel != after.channel:
            if after.channel and after.channel.id == self.channel_ID:  # create
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
                self.channel_list.append(new_channel)
                await self.create_notification(guild,member,new_channel.mention)
                await member.move_to(new_channel)
            elif before.channel and before.channel in self.channel_list and len(before.channel.members) == 0:  # delete
                await before.channel.delete()
             
    async def create_notification(self, guild : discord.Guild ,member: discord.Member,channel_mention:str):
        embed = discord.Embed(title=f"{member.display_name}創建了語音頻道", description="", color=0x30D5C8)
        embed.add_field(name="頻道", value=channel_mention, inline=True)
        embed.add_field(name="創建者", value=member.display_name, inline=True)
        with open('data/DynamicVoiceNotificationList.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault(str(member.id),[])
            notification_list = data[str(member.id)]
        notification_str = " ".join(f"<@{x}>" for x in notification_list)
        if notification_str == "":
            notification_str = "無"
        embed.add_field(name="通知", value=notification_str, inline=False)
        embed.timestamp = datetime.datetime.now(datetime.UTC)
        channelID = self.config['DynamicVoiceChannel'].getint('notification_Channel')
        await guild.get_channel(channelID).send(embed=embed)
    
    @app_commands.command(name='訂閱語音通知')
    async def subscription(self,interaction: discord.Interaction, member: discord.Member):
        with open('data/DynamicVoiceNotificationList.json', 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault(str(member.id),[])
                if (interaction.user.id not in data[str(member.id)]) and (member.id != interaction.user.id):
                    data[str(member.id)].append(interaction.user.id)
                f.seek(0)
                json.dump(data, f, indent=4, separators=(',', ': '))
                f.truncate()
        await interaction.response.send_message('設置成功',ephemeral=True)
    @app_commands.command(name='取消訂閱語音通知')
    async def unsubscription(self,interaction: discord.Interaction, member: discord.Member):
        with open('data/DynamicVoiceNotificationList.json', 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault(str(member.id),[])
                if interaction.user.id in data[str(member.id)] :
                    data[str(member.id)].remove(interaction.user.id)
                    await interaction.response.send_message('設置成功',ephemeral=True)
                else:
                    await interaction.response.send_message('設置失敗:原本並無訂閱',ephemeral=True)
                f.seek(0)
                json.dump(data, f, indent=4, separators=(',', ': '))
                f.truncate()
    @app_commands.command(name="顯示訂閱清單")    
    async def show_list(self,interaction: discord.Interaction):
        with open('data/DynamicVoiceNotificationList.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            result_list = []
            for key,value in data.items():
                if interaction.user.id in value:
                    result_list.append(key)
        await interaction.response.send_message('## 訂閱列表: \n'+'\n'.join([ interaction.guild.get_member(int(id)).display_name for id in result_list]),ephemeral=True)
        
async def setup(bot):
    await bot.add_cog(DynamicVoiceChannel(bot))