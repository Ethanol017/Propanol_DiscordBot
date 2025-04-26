import json
import re
from typing import List
import discord
from discord.ext import commands
from discord import app_commands
import configparser
from google import genai
from google.genai.chats import AsyncChat
from google.genai import types


def export_history_to_json(history, filepath="data/chat_history.json"):
    result = [content.to_json_dict() for content in history]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
def load_json_as_dict(filepath="data/chat_history.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def check_text_replace_to_display(guild:discord.guild.Guild,text):
    pattern = r"<@(\d+)>"
    def repl(m):
        print(int(m.group(1)))
        user = guild.get_member(int(m.group(1)))
        if user is not None:
            return f"@{user.display_name}"
    new_text = re.sub(pattern, repl, text)
    return new_text

get_chat_history_declaration = {
    "name": "get_chat_history",
    "description": "取得聊天室過去的對話紀錄",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "想要取得的對話紀錄數量"
            }
        },
        "required": ["limit"]
    }
}
async def get_chat_history(channel,limit=10)-> List[str]:
    history = []
    async for message in channel.history(limit=limit):
        history.append(f"{message.author.display_name}:{check_text_replace_to_display(channel.guild,message.content)}")
    history.reverse()
    print(history)
    return history

class LLM(commands.GroupCog):
    def __init__(self, bot:commands.Bot):
        self.bot: commands.Bot = bot
        config = configparser.ConfigParser()
        config.read('data/config.ini')
        GOOGLE_TOKEN = config['Global'].get('GOOGLE_TOKEN')
        self.client = genai.Client(api_key=GOOGLE_TOKEN)
        self.chat : AsyncChat = None
        self.tools = types.Tool(function_declarations=[get_chat_history_declaration])

    
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
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(
                            max_output_tokens=200,
                            temperature=0.5,
                            tools=[self.tools],
                            system_instruction=[
                                "你現在扮演一位具有以下特質的人，並以繁體中文回應",
                                "角色設定：女性朋友，名字叫「丙醇」，是我們很要好的朋友",
                                "性格：溫柔、幽默",
                                "主要語氣：隨意一點，不要太活潑浮誇，使用第一人稱，對其他人可以用「你我他」的稱呼",
                                "不用問候語或是確認問題(例如「XXX問我什麼哦?」)",
                                "可以偶爾吐槽人或調侃人",
                                "可以用髒話當感嘆或語助詞，但不要太過火"
                                "可以使用流行語或網路用詞",
                                "語句停頓處可以換行，但不要超過5行",
                                "以朋友口吻聊天，不要過度正式或條列式回覆",
                                "遇到專業問題可嘗試回答，如超出能力範圍則誠實說明",
                                "回應不超過 3 行"
                                "可以使用一點Discord表情符號，使用文字傳出<:名稱:ID>的格式，妳可以用以下貼圖，再貼圖格式後的是描述:\n<:Sadge:1280149806043365479> 哭哭，表示難過的時候\n<:kspRRR:1336296088084156416> 阿阿阿，或等於 >< 這個閉眼表符\n<:YEP:1185595544832327690> 表示OK，但比較偏向 \"就是這樣\" 或 \"都給你說\" 或 \"理所當然\"的語境時用，但用來當OK也沒問題\n<:PepeLaugh:1185592789912797295> 很好笑\n<:kspEhhh:1332761541438869544> ㄎㄧㄤ，表示傻\n<:uncle_roger:1128314929003376661> 抱頭，表示很驚訝時或是沒辦法接受\n<:Madge:1185592511268409487> 生氣\n<:pepegaLoad:1344651441217994846> 加載，表示驚訝過度或無法思考或不想思考時\n<:peepoClap:1185595226736300142> 開心地拍手\n<:Susge:1344651820722683966> 懷疑\n<:Waiting:1332227639804432424> 等待或是無以言對\n<:pepegaphone:1318238246722994237> 造謠或宣傳\n<:Gayge:1257737817447202937> 你是Gay，通常用於開玩笑，不是真的只一定是Gay\n<:kspmad:1336567513051562036> 怨恨\n<:dejaVu:1185623994523730040> 緊張地開車，有時候表示自己覺得對方有點危險\n<:wait:1257737343084007565> 瞪大眼睛表示驚訝\n<:huh:1185593315291308092> 驚訝或無以言對\n<:ew:1339536702150021130> 矮額，表示對方奇怪或噁心\n<:JOKER:1318589512208617502> 出糗時的小丑 \n<:emotional_damage:1128300757356134531> 情感攻擊，網路迷因，傷感情時用\n<:split:1204471604164431912> 心態不好時或覺得某件事沒有達到預期\n<:Deadge:1185593028811964536> 死掉或躺平，不代表真的死亡，通常表示放棄或躺平\n",
                            ]
                        ),
                        history=load_json_as_dict()
                    )
                message_send = check_text_replace_to_display(message.guild,message.content.replace(self.bot.user.mention, ''))
                response = await self.chat.send_message(f"{message.author.display_name}:{message_send}")
                print(f"function_calls: {response.function_calls}")
                if response.function_calls is not None:
                    for tool_call in response.function_calls:
                        if tool_call.name == "get_chat_history":
                            result = await get_chat_history(message.channel,**tool_call.args)
                            print(f"Function execution result: {result}")
                        
                        function_response_part = types.Part.from_function_response(
                            name=tool_call.name,
                            response={"result": result},
                        )
                        response = await self.chat.send_message(function_response_part)
                export_history_to_json(self.chat.get_history())
                await message.channel.send(response.text)
            

async def setup(bot):
    await bot.add_cog(LLM(bot))