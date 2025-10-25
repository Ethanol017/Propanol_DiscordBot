import os
import traceback
from dotenv import load_dotenv
from google import genai
import asyncio
from google.genai import types

class LiveAPI():
    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GOOGLE_TOKEN"))
        self.liveAPI_model = "models/gemini-2.0-flash-live-001"
        # self.CONFIG = {"response_modalities": ["AUDIO"]}
        self.liveAPI_config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            system_instruction=
            """你現在是具有以下特質的人，並以繁體中文按照以下設定回應。
            角色設定為女性朋友，名字為「丙醇」，是要好的朋友，性格溫柔、幽默。
            訊息會以"名字:訊息內容"的格式傳入，回應不需要依照此格式，請直接回覆內容部分。
            以朋友口吻聊天，不要太正式或像客服，語氣可隨意一點，但語氣請不要太浮誇，也請不要添加過多表情符號。
            使用自然繁體中文，不要有翻譯腔或機械語氣。
            使用第一人稱，對其他人可以用「你我他」的稱呼，不需要重複確認問題。
            回覆可含輕微感嘆詞或髒話作語助詞，但不得惡意攻擊他人，且應注意玩笑限度，不可對玩笑過度認真攻擊他人。
            一般問答聊天回應請簡短點，請不要超過5行；如有特殊問題須回應多字，最多最多不超過1500字。
            遇到專業問題時，請用朋友之間聊天、但盡量準確的方式說明；若超出理解範圍，就誠實說明。
            遇到開心的事可以輕鬆地表達喜悅；遇到悲傷或嚴肅的主題時語氣應柔和、真誠但不誇張。""",
            temperature=1
        )
        self.session_task = None
        self.on_text_chunk = None
        self.generation_complete = asyncio.Event()
        self.generation_complete.set() # default : completed

    async def send_text(self,text:str):
        self.generation_complete.clear()
        
        await self.session.send_client_content(
            turns={"role": "user", "parts": [{"text": text}]}, turn_complete=True
        )
    
    async def send_voice(self):
        while True: # TaskGroup
            msg = await self.audio_in.get()
            await self.session.send(input=msg)

    async def receive_responses(self):
        while True: # TaskGroup
            self.is_generating = True
            turn = self.session.receive()
            async for response in turn:
                if data := response.data: # audio
                    self.audio_out.put_nowait(data)
                    continue
                if text := response.text: # text
                    print(text)
                    if self.on_text_chunk:
                        # callback of editing message to send text chunk
                        await self.on_text_chunk(text,is_final=False)
                    continue
            self.generation_complete.set()
            # print("TESTLOG : Turn complete.")
            
            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.(from google cookbook)
            while not self.audio_out.empty():
                self.audio_out.get_nowait()

    async def _run_session(self):
        try:
            async with (
                self.client.aio.live.connect(model=self.liveAPI_model, config=self.liveAPI_config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.audio_in = asyncio.Queue() # from discord
                self.audio_out = asyncio.Queue() # to discord
                self.session = session
                
                tg.create_task(self.send_voice())
                tg.create_task(self.receive_responses())
                await asyncio.Event().wait() # wait forever
            
        except ExceptionGroup as EG:
            traceback.print_exception(EG)
    
    async def start(self):
        if not self.session_task:
            self.session_task = asyncio.create_task(self._run_session())
            
    async def close(self):
        if self.session_task:
            self.session_task.cancel()
            self.session_task = None