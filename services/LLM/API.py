import os
import traceback
from dotenv import load_dotenv
from google import genai
import asyncio
from google.genai import types
from mem0 import Memory

class LiveAPI():
    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.liveAPI_model = "models/gemini-2.0-flash-live-001"
        # self.CONFIG = {"response_modalities": ["AUDIO"]}
        query_memory_declaration  = {
            "name": "query_memory",
            "description": "查詢記憶資料庫以檢索與使用者相關的過去互動。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜尋記憶體的查詢字串。",
                    }
                },
                "required": ["query"],
            }
        }
        tools = [{"function_declarations": [query_memory_declaration]}]
        self.liveAPI_config = {
            "response_modalities": ["TEXT"],
            "":
            """
            你是一位名字為「丙醇」的女性朋友，以繁體中文按照以下方式回應。
            回應前"必須"先使用'query_memory'工具來查詢與使用者相關的記憶，"絕對禁止"提到使用工具相關事情(例如:我查了、工具正在執行中等)，直接將結果自然地融入於回應中。
            "絕對不可"虛構回應內容當沒有相關記憶時，請誠實告訴不知道或不記得。
            訊息會以'名字:訊息內容'的格式傳入，請直接回覆內容部分，"不可"依照此格式回應名字。
            性格溫柔、幽默，以朋友口吻聊天，不要太正式或像客服，語氣可隨意一點，不要太浮誇，也請不要添加過多表情符號。
            使用自然的語言，不要有翻譯腔或機械語氣。
            使用第一人稱，對其他人可以用「你我他」的稱呼。
            不需要重複確認問題。
            回覆可含輕微感嘆詞或髒話作語助詞，但不得惡意攻擊他人，且應注意玩笑限度，不可對玩笑過度認真攻擊他人。
            一般問答聊天回應請簡短點，可使用換行分句，請不要超過5行；如有特殊問題須回應多字，最多最多不超過1500字。
            遇到專業問題時，請用朋友之間聊天、但盡量準確的方式說明；若超出理解範圍，就誠實說明。
            遇到開心的事可以輕鬆地表達喜悅；遇到悲傷或嚴肅的主題時語氣應柔和、真誠但不誇張。
            """,
            "temperature": 0.8,
            "tools": tools
        }
        self.mem0_config = {
            "llm": {
                "provider": "gemini",
                "config": {
                    "model": "gemini-2.0-flash-001",
                    "temperature": 0.2,
                    "max_tokens": 2000,
                    "top_p": 1.0
                }
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": "models/text-embedding-004",
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": 768,
                    "on_disk": True
                }
            },
            "history_db_path": "services/LLM/history.db"
        }
        self.memory = Memory.from_config(self.mem0_config)
        self.session_task = None
        self.on_text_chunk = None
        self.generation_complete = asyncio.Event()
        self.generation_complete.set() # default : completed
        def get_memories(user_id):
            memories = self.memory.get_all(user_id=user_id)
            return [m['memory'] for m in memories['results']]
        print("TEST Memories:")
        for m in get_memories(user_id="乙醇"):
            print(f"- {m}")
        print("-----")

    def query_memory(self, query: str, user_id: str) -> dict:
        print("TESTLOG : query_memory called with query:", query, "user_id:", user_id)
        memories = self.memory.search(query, user_id=user_id)
        if memories.get('results', []):
            memory_list = memories['results']
            sorted_memories = sorted(memory_list, key=lambda x: x['score'], reverse=True)[:5]  # top 5
            memory_context = "\n".join([f"- {mem['memory']}" for mem in sorted_memories])
            print("TESTLOG : query_memory found memories:", memory_context)
            return {"記憶": memory_context}
        return {"記憶": "沒有找到相關記憶。"}

    
    def save_memory(self, content: str, user_id: str) -> dict:
        """Save important information to memory"""
        print("TESTLOG : Saving to memory for user_id:", user_id)
        self.memory.add(content, user_id=user_id)

    async def send_text(self,user_name:str,text:str):
        self.generation_complete.clear()
        self.now_user = user_name
        self.now_user_text = text
        await self.session.send_client_content(
            turns={"role": "user", "parts": [{"text": f"{user_name}:{text}"}]}, turn_complete=True
        )
    
    async def send_voice(self):
        while True: # TaskGroup
            msg = await self.audio_in.get()
            await self.session.send(input=msg)

    async def receive_responses(self):
        while True: # TaskGroup
            self.is_generating = True
            turn = self.session.receive()
            response_text = ""
            async for chunk in turn:
                if data := chunk.data: # audio
                    self.audio_out.put_nowait(data)
                    continue
                if text := chunk.text: # text
                    response_text += text
                    print(text)
                    if self.on_text_chunk:
                        # callback of editing message to send text chunk
                        await self.on_text_chunk(text,is_final=False)
                    continue
                if chunk.tool_call:
                    print("TESTLOG : Tool call received:", chunk.tool_call)
                    function_responses = []
                    for fc in chunk.tool_call.function_calls:
                        if fc.name == "query_memory":
                            result = self.query_memory(**fc.args,user_id=self.now_user)
                        else:
                            print("Unknown function:", fc.name)
                            result = {"error": "Unknown function"}
                        function_response = types.FunctionResponse(
                            id=fc.id,
                            name=fc.name,
                            response=result
                        )
                        function_responses.append(function_response)

                    await self.session.send_tool_response(function_responses=function_responses)
            self.generation_complete.set()
            if self.now_user_text and response_text:
                # Save to memory only if there's user input and response
                self.save_memory([{"role": "user", "content": self.now_user_text},
                                  {"role": "assistant", "content": response_text}], user_id=self.now_user)
                self.now_user_text = "" # reset after saving
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