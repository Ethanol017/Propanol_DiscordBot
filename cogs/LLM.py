import discord
from discord.ext import commands
from discord import app_commands
import configparser
from google import genai
from google.genai import types



class LLM(commands.GroupCog):
    def __init__(self, bot:commands.Bot):
        self.bot: commands.Bot = bot
        config = configparser.ConfigParser()
        config.read('data/config.ini')
        GOOGLE_TOKEN = config['Global'].get('GOOGLE_TOKEN')
        self.client = genai.Client(api_key=GOOGLE_TOKEN)

    
    @commands.Cog.listener()
    async def on_message(self, message:discord.Message):
        # 忽略自己的訊息
        if message.author == self.bot.user:
            return

        if self.bot.user in message.mentions:
            print(f"Received message: {message.content}")
            content = f"{message.author.display_name} 說：{message.content.replace(self.bot.user.mention, '').strip()}"

            async with message.channel.typing():
                response = await self.client.aio.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=content,
                    config=types.GenerateContentConfig(
                        max_output_tokens=200,
                        temperature=0.2,
                        system_instruction=[
                            "你現在扮演一位具有以下特質的人，並以繁體中文回應",
                            "角色設定：女性朋友，名字叫「丙醇」",
                            "主要語氣：隨意一點不要太活潑浮誇，使用第一人稱，對其他人可以用「你我他」的稱呼",
                            "偶爾使用一點 emoji 或貼圖文字，但不要太多五花八門的不同 emoji 或貼圖文字",
                            "不用問候語或是確認問題(例如「XXX問我什麼哦？」)",
                            "可以吐槽人和調侃人",
                            "可以使用流行語或網路用詞",
                            "語句停頓處可以換行",
                            "以朋友口吻聊天，不要過度正式或條列式回覆",
                            "遇到專業問題可嘗試回答，如超出能力範圍則誠實說明",
                            "回應不超過 3 行"
                        ]
                    )
                )
                await message.channel.send(response.text)
            

async def setup(bot):
    await bot.add_cog(LLM(bot))