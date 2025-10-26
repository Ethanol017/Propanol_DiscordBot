import discord
from discord.ext import commands,voice_recv
from discord import app_commands
import asyncio
import re
import warnings
from services.LLM.API import LiveAPI

class LLM(commands.GroupCog):
    def __init__(self, bot:commands.Bot):
        self.bot: commands.Bot = bot
        self.EDIT_RATE = 0.2  # seconds
        self.live_api = LiveAPI()
        
        # Text Init
        self.buffer = ""
        self.current_message = None
        self.last_edit_time = 0
    
    async def handle_text_chunk(self, text: str,is_final: bool = False):
        self.buffer += text
        # edit rate limit
        current_time = asyncio.get_event_loop().time()
        # print(f"TESTLOG : Received text chunk: {text} (final: {is_final} current_time: {current_time})\n")
        if current_time - self.last_edit_time < self.EDIT_RATE and not is_final:
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
            named_message = self.mentions_to_usernames(message.guild,message.content)
            print(f"TESTLOG : Received message: {message.author.display_name}:{named_message}")
            await self.live_api.start()
            # wait for last generation complete
            await self.live_api.generation_complete.wait()
            async with message.channel.typing():
                self.buffer = ""
                self.current_message = None
                self.last_edit_time = 0
                
                self.live_api.on_text_chunk = self.handle_text_chunk
                await self.live_api.send_text(message.author.display_name,named_message)
                # wait for first chunk
                while not self.buffer:
                    await asyncio.sleep(0.1)
                self.current_message = await message.channel.send(self.buffer)
                
                await self.live_api.generation_complete.wait()
                
                # print("TESTLOG : (in LLM.py) Generation complete.\n")
                # Final edit to ensure complete message is sent
                # Not written in receive_responses(API.py) because receive_responses process both voice and text when generation complete
                await self.handle_text_chunk("",is_final=True)
    
    @app_commands.command()
    async def join(self,interaction: discord.Interaction):
        if interaction.user.voice:
            # TEST TOOL: Save to wave.
            # import wave
            # vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            # wave_file = wave.open('test.wav', 'wb')
            # vc.listen(voice_recv.WaveSink('test.wav'))
            
            # Listen
            def callback(user, data: voice_recv.VoiceData):
                """get voice data callback"""
                if (user.id != self.bot.user.id):
                    # print(f"Send pcm to bridge from {user} time: {time.time()}")
                    # TODO send pcm data to LLM voice input
                    pass
            vc = await interaction.user.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(voice_recv.BasicSink(callback))
            
            # Play
            # TODO  get voice, and play voice to voice channel
            
            await interaction.response.send_message("Connected to voice channel",ephemeral=True)
        else:
            await interaction.response.send_message("User did't in voice channel",ephemeral=True)

    @app_commands.command()
    async def leave(self,interaction: discord.Interaction):
        if len(self.bot.voice_clients)>0:
            for voice_client in self.bot.voice_clients:
                await voice_client.disconnect()
            await interaction.response.send_message("Disconnect to voice channel",ephemeral=True)
        else:
            await interaction.response.send_message("Bot did't in voice channel",ephemeral=True)

async def setup(bot):
    await bot.add_cog(LLM(bot))