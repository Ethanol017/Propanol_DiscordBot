import json
import discord
from discord.ext import commands
from discord import app_commands
import configparser
from google import genai
from google.genai.chats import AsyncChat
from google.genai import types


def export_history_to_json(history, filepath="data/chat_history.json"):
    result = []

    for item in history:
        parts = []
        for part in item.parts:
            if hasattr(part, "text") and part.text:
                parts.append({"text": part.text})
        result.append({
            "role": item.role,
            "parts": parts
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
def load_json_as_dict(filepath="data/chat_history.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

class LLM(commands.GroupCog):
    def __init__(self, bot:commands.Bot):
        self.bot: commands.Bot = bot
        config = configparser.ConfigParser()
        config.read('data/config.ini')
        GOOGLE_TOKEN = config['Global'].get('GOOGLE_TOKEN')
        self.client = genai.Client(api_key=GOOGLE_TOKEN)
        self.chat : AsyncChat = None

    
    @commands.Cog.listener()
    async def on_message(self, message:discord.Message):
        # 忽略自己的訊息
        if message.author == self.bot.user:
            return

        if self.bot.user in message.mentions:
            print(f"Received message: {message.content}")


            async with message.channel.typing():
                if self.chat is None:
                    self.chat = self.client.aio.chats.create(
                        model="gemini-2.0-flash-lite",
                        config=types.GenerateContentConfig(
                            max_output_tokens=200,
                            temperature=0.2,
                            system_instruction=[
                                "你現在扮演一位具有以下特質的人，並以繁體中文回應",
                                "角色設定：女性朋友，名字叫「丙醇」，是我們很要好的朋友",
                                "主要語氣：隨意一點不要太活潑浮誇，使用第一人稱，對其他人可以用「你我他」的稱呼",
                                "偶爾使用一點 emoji 或貼圖文字，但不要太多五花八門的不同 emoji 或貼圖文字",
                                "不用問候語或是確認問題(例如「XXX問我什麼哦?」)",
                                "可以偶爾幽默的吐槽人和調侃人",
                                "可以用髒話當感嘆或語助詞，但不能無原無故罵人"
                                "可以使用流行語或網路用詞",
                                "語句停頓處可以換行",
                                "以朋友口吻聊天，不要過度正式或條列式回覆",
                                "遇到專業問題可嘗試回答，如超出能力範圍則誠實說明",
                                "回應不超過 3 行"
                            ]
                        ),
                        history=load_json_as_dict()
                    )
                response = await self.chat.send_message(f"{message.author.display_name}:{message.content.replace(self.bot.user.mention, '')}")
                export_history_to_json(self.chat.get_history())
                await message.channel.send(response.text)
            

async def setup(bot):
    await bot.add_cog(LLM(bot))