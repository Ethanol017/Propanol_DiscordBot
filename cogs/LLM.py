import discord
from discord.ext import commands,voice_recv
from discord import app_commands
import asyncio
import re
import warnings
from services.LLM.API import LiveAPI
from google.genai import types
import audioop
import threading
import logging
logging.getLogger('discord.ext.voice_recv').setLevel(logging.WARNING)

class GeminiAudioSource(discord.AudioSource):
    def __init__(self):
        self.buffer = bytearray()
        self.rate_state = None 
        self._lock = threading.Lock()
        
        # 超時控制
        self.silence_count = 0
        self.MAX_SILENCE_FRAMES = 25 # 25 * 20ms = 500ms (0.5秒)
        self.FRAME_SIZE = 3840 # 20ms PCM

    def add_data(self, data: bytes):
        """接收來自 Gemini 的 24kHz Mono PCM 數據"""
        if not data:
            return
            
        # 1. Resample 24k -> 48k
        out_data, self.rate_state = audioop.ratecv(data, 2, 1, 24000, 48000, self.rate_state)
        
        # 2. Mono -> Stereo
        out_data = audioop.tostereo(out_data, 2, 1, 1)
        
        with self._lock:
            self.buffer.extend(out_data)
            # 有新資料進來，重置靜音計數
            self.silence_count = 0

    def read(self) -> bytes:
        """Discord 語音執行緒會每 20ms 呼叫此方法"""
        
        with self._lock:
            if len(self.buffer) >= self.FRAME_SIZE:
                data = self.buffer[:self.FRAME_SIZE]
                del self.buffer[:self.FRAME_SIZE]
                self.silence_count = 0 # 確保有資料時重置計數
                return bytes(data)
        
        # Buffer 空了，檢查是否超過靜音容忍時間
        if self.silence_count < self.MAX_SILENCE_FRAMES:
            self.silence_count += 1
            # 回傳靜音封包，保持連線順暢，等待更多資料
            return b'\x00' * self.FRAME_SIZE
        else:
            # 超過 0.5 秒沒資料，回傳 b'' 結束播放，綠燈熄滅
            return b''

    def cleanup(self):
        with self._lock:
            self.buffer.clear()


class LLM(commands.GroupCog):
    def __init__(self, bot:commands.Bot):
        self.bot: commands.Bot = bot
        self.EDIT_RATE = 0.2  # seconds
        self.live_api = LiveAPI()
        
        # Text Init
        self.buffer = ""
        self.chunk = 0
        self.START_CHUNK = 2 # start sending after n chunks
        self.current_message = None
        self.last_edit_time = 0
        
        # Audio Init
        self.in_voice = False
        self.audio_source = GeminiAudioSource()
        self.audio_task = None
    
    async def handle_text_chunk(self, text: str,is_final: bool = False):
        self.chunk += 1
        self.buffer += text
        # edit rate limit
        current_time = asyncio.get_event_loop().time()
        # print(f"TESTLOG : Received text chunk: {text} (final: {is_final} current_time: {current_time})\n")
        if (self.chunk >= self.START_CHUNK or current_time - self.last_edit_time < self.EDIT_RATE) and not is_final:
            return
        
        if self.current_message:
            await self.current_message.edit(content=self.buffer[:2000]) # discord message limit 2000 chars
            self.last_edit_time = current_time
    
    def mentions_to_usernames(self,guild:discord.guild.Guild,text):
        pattern = r"<@(\d+)>"
        def repl(m):
            if int(m.group(1)) == self.bot.user.id:  # bot id
                return ""
            user = guild.get_member(int(m.group(1)))
            if user is not None:
                return f"@{user.display_name}"
            else :
                warnings.warn(f"Cannot find user with ID {m.group(1)} in guild {guild.name}")
                return "@unknown"
        new_text = re.sub(pattern, repl, text)
        return new_text
    
    @commands.Cog.listener()
    async def on_message(self, message:discord.Message):
        # ignore self message
        if message.author == self.bot.user:
            return

        if self.bot.user in message.mentions:
            named_message = await self.mentions_to_usernames(message.guild,message.content)
            print(f"TESTLOG : Received message: {message.author.display_name}:{named_message}")
            if self.in_voice:
                await self.live_api.start(audio_mode=True)
                await self.live_api.send_text(message.author.display_name,named_message)
            else:
                await self.live_api.start(audio_mode=False)
                # wait for last generation complete
                await self.live_api.generation_complete.wait()
                async with message.channel.typing():
                    self.buffer = ""
                    self.chunk = 0
                    self.current_message = None
                    self.last_edit_time = 0
                    
                    self.live_api.on_text_chunk = self.handle_text_chunk
                    await self.live_api.send_text(message.author.display_name,named_message)
                    # wait for chunk
                    while self.chunk < self.START_CHUNK:
                        await asyncio.sleep(0.1)
                    self.current_message = await message.channel.send(self.buffer)
                    
                    await self.live_api.generation_complete.wait()
                    
                    # print("TESTLOG : (in LLM.py) Generation complete.\n")
                    # Final edit to ensure complete message is sent
                    # Not written in receive_responses(API.py) because receive_responses process both voice and text when generation complete
                    await self.handle_text_chunk("",is_final=True)

    async def audio_consumer_task(self):
        """從 API 的 async Queue 搬運資料到 sync AudioSource"""
        print("Audio consumer task started.")
        while True:
            try:
                if hasattr(self.live_api, 'audio_out') and self.live_api.audio_out:
                    data = await self.live_api.audio_out.get()
                    
                    # 檢查是否需要開始新的播放
                    if self.in_voice and len(self.bot.voice_clients) > 0:
                        vc = self.bot.voice_clients[0]
                        
                        # 如果目前沒有在播放，或者之前的 Source 已經結束 (read 回傳 b'')
                        if not vc.is_playing():
                            print("Start new audio playback session")
                            self.audio_source = GeminiAudioSource()
                            vc.play(self.audio_source)
                            
                        # 將資料加入當前的 Source
                        # 注意：這裡假設 self.audio_source 永遠指向最新建立的 Source
                        if isinstance(self.audio_source, GeminiAudioSource):
                            self.audio_source.add_data(data)
                else:
                    # wait session start
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                print("Audio consumer task cancelled.")
                break
            except Exception as e:
                print(f"Error in audio consumer: {e}")
                await asyncio.sleep(1)

    @app_commands.command()
    async def join(self,interaction: discord.Interaction):
        if interaction.user.voice:
            # TEST TOOL: Save to wave.
            # import wave
            # vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            # wave_file = wave.open('test.wav', 'wb')
            # vc.listen(voice_recv.WaveSink('test.wav'))
            await self.live_api.start(audio_mode=True)
            users = [member.display_name for member in interaction.user.voice.channel.members if member.id != self.bot.user.id]
            await self.live_api.send_text("system",f"Hint: You are currently chatting. The chat contains individuals named\"{'\", \"'.join(users)}\". You cannot know who is speaking, but they are definitely one of them. (No need to reply to this hint)",is_system=True)
            # Listen
            def callback(user, data: voice_recv.VoiceData):
                """get voice data callback"""
                if user and user.id != self.bot.user.id:
                    # print(f"Received voice data from {user.display_name}, pcm length: {len(data.pcm)}")
                    if not hasattr(self.live_api, 'audio_in') or self.live_api.audio_in is None:
                        return
                    try:
                        # Discord sends 48kHz Stereo 16-bit PCM
                        pcm = data.pcm
                        # Stereo to Mono
                        mono = audioop.tomono(pcm, 2, 1, 1)
                        # Resample 48k -> 16k
                        resampled, _ = audioop.ratecv(mono, 2, 1, 48000, 16000, None)
                        
                        blob = types.Blob(data=resampled, mime_type="audio/pcm;rate=16000")
                        self.bot.loop.call_soon_threadsafe(
                            self.live_api.audio_in.put_nowait,
                            (user.display_name,blob)
                        )
                    except Exception as e:
                        print(f"Error processing voice data: {e}")
            vc = await interaction.user.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            self.in_voice = True
            vc.listen(voice_recv.BasicSink(callback))
            
            # Play
            if self.audio_task:
                self.audio_task.cancel()
            self.audio_task = asyncio.create_task(self.audio_consumer_task())
            
            await interaction.response.send_message("Connected to voice channel")
        else:
            await interaction.response.send_message("User did't in voice channel",ephemeral=True)

    @app_commands.command()
    async def leave(self,interaction: discord.Interaction):
        self.in_voice = False
        
        if isinstance(self.audio_source, GeminiAudioSource):
            self.audio_source.cleanup()

        if self.audio_task:
            self.audio_task.cancel()
            self.audio_task = None
        if len(self.bot.voice_clients)>0:
            for voice_client in self.bot.voice_clients:
                await voice_client.disconnect()
            await interaction.response.send_message("Disconnect to voice channel",ephemeral=True)
        else:
            await interaction.response.send_message("Bot did't in voice channel",ephemeral=True)

async def setup(bot):
    await bot.add_cog(LLM(bot))