import discord
from discord.ext import commands
from discord import app_commands
import json

class CustomActivity(commands.GroupCog,name="activity"):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot
        
    @app_commands.command()
    @commands.is_owner()
    async def set(self,interaction: discord.Interaction,content:str):
        await self.bot.change_presence(activity=discord.CustomActivity(name=content))
        await interaction.response.send_message('設置成功',ephemeral=True)
    
    @app_commands.command()
    @commands.is_owner()
    async def clear(self,interaction: discord.Interaction):
        await self.bot.change_presence(activity=None)
        await interaction.response.send_message('設置成功',ephemeral=True)
    
    class ModifyModal(discord.ui.Modal):
        def __init__(self, *,name:str,content:str) -> None:
            super().__init__(title="內容按行分隔喔!!")
            self.text = discord.ui.TextInput(label = name,default=content,style=discord.TextStyle.long)
            self.add_item(self.text)
            
        async def on_submit(self, interaction: discord.Interaction):
            with open('data/activity.json', 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data[str(interaction.user.id)] = self.text.value.splitlines()
                f.seek(0)
                json.dump(data, f, indent=4, separators=(',', ': '))
                f.truncate()
            await interaction.response.send_message(content="設置完成",ephemeral=True)     
    
    @app_commands.command(description="修改或添加\"乙醇機器人\"活動的欄隨機內容(僅能修改自己的內容)")
    async def modify(self,interaction: discord.Interaction):
        with open('data/activity.json', 'r+', encoding='utf-8') as f:
            data = json.load(f)
        await interaction.response.send_modal(self.ModifyModal(name=f"{interaction.user.name}",content= "\n".join(data.setdefault(str(interaction.user.id),[]))))

async def setup(bot):
    await bot.add_cog(CustomActivity(bot))