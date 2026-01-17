import asyncio
import json
import os
import signal
import threading
import time
import discord
from discord import app_commands
from discord.ext import commands
import subprocess
import re
from mcstatus import JavaServer

class MCServer(commands.GroupCog,name="mc"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.server_process = None
        self.current_running_server = None


    def read_output(self,pipe):
        with open("logs/mc_output.log", "w") as f:
            for line in iter(pipe.readline, ''):
                if line:
                    # print(line, end='')
                    f.write(line)
                    f.flush()
                else:
                    break
    
    async def servers_autocomplete(self,interaction: discord.Interaction, current: str):
        with open('data/MCServer.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        guild_id = interaction.guild_id
        servers = [server for server in data.get(str(guild_id), {}).keys() if current.lower() in server.lower()]
        servers.remove("last_used")
        
        last_used = data.get(str(guild_id), {}).get("last_used")
        # print(last_used)
        if last_used and last_used in servers:
            servers.remove(last_used)
            servers = [last_used] + servers
        # print(server for server in servers if current.lower() in server.lower()) # test
        return [app_commands.Choice(name=server, value=server) for server in servers if current.lower() in server.lower()]
        

    @app_commands.command(name="start")
    async def start(self, interaction: discord.Interaction, server: str) -> None:
        
        with open('data/MCServer.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data = data.get(str(interaction.guild_id), {}).get(server)
            
        if self.server_process is not None and self.server_process.poll() is None:
            await interaction.response.send_message(f"已運行伺服器:{self.current_running_server}",ephemeral=True)
            return
        elif data:
            await interaction.response.send_message(f"{server} 伺服器啟動中...")
        else:
            await interaction.response.send_message("伺服器不存在或發生錯誤", ephemeral=True)
            return
        
        # record last_used
        with open('data/MCServer.json', 'r+', encoding='utf-8') as f:
            all_data = json.load(f)
            all_data[str(interaction.guild_id)]["last_used"] = server
            f.seek(0)
            json.dump(all_data, f, ensure_ascii=False, indent=4)
            f.truncate()

        env = os.environ.copy()
        if "env" in data:
            env.update(data["env"])
        try:
            self.server_process = subprocess.Popen(
                ["/bin/bash", data["start_path"]],
                cwd= os.path.dirname(data["start_path"]),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                preexec_fn=os.setsid
            )
            self.current_running_server = server
        except Exception as e:
            await interaction.followup.send(f"伺服器啟動失敗，<@754674664986378301> 錯誤：{e}")
            return
        
        print(f"運行伺服器{server} pid : {self.server_process.pid}")
        threading.Thread(target=self.read_output, args=(self.server_process.stdout,), daemon=True).start()
        
    start.autocomplete('server')(servers_autocomplete)

    @app_commands.command(name="stop")
    async def stop(self, interaction: discord.Interaction) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            await interaction.response.send_message("關閉伺服器中...")
            try:
                self.server_process.stdin.write("stop\n")
                self.server_process.stdin.flush()
            except Exception as e:
                print("Error sending stop command:", e)
                pass
            
            await asyncio.sleep(10)
            
            try:
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as e:
                print("Error killing process group:", e)
            self.server_process = None
            self.current_running_server = None
            print("伺服器已關閉")
            await interaction.edit_original_response(content="伺服器已關閉")
        else:
            if self.server_process is not None:
                self.server_process = None
                self.current_running_server = None
                await interaction.response.send_message("伺服器先前已意外停止或崩潰")
            else:
                await interaction.response.send_message("伺服器並未啟動")
            
    @app_commands.command(name="restart")
    async def restart(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("重啟伺服器中...",ephemeral=True)
        
        await self.stop(interaction)
        await self.start(interaction)

    def get_server_port(self, server_dir):
        try:
            with open(os.path.join(server_dir, "server.properties"), "r", encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("server-port="):
                        return int(line.strip().split("=")[1])
        except Exception:
            pass
        return 25565

    @app_commands.command(name="status")
    async def status(self, interaction: discord.Interaction) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            server_name = self.current_running_server if self.current_running_server else "未知伺服器"
            
            # 獲取配置以找到路徑
            try:
                with open('data/MCServer.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 嘗試獲取伺服器配置，如果找不到則使用空字典
                    guild_data = data.get(str(interaction.guild_id), {})
                    server_config = guild_data.get(server_name)
            except Exception as e:
                print(f"Error reading config: {e}")
                server_config = None

            if not server_config:
                await interaction.response.send_message(f"目前 {server_name} 伺服器正在運行，但無法讀取詳細配置。", ephemeral=True)
                return

            await interaction.response.defer()

            start_path = server_config["start_path"]
            server_dir = os.path.dirname(start_path)
            port = self.get_server_port(server_dir)
            
            try:
                server = await JavaServer.async_lookup(f"127.0.0.1:{port}")
                status = await server.async_status()
                
                embed = discord.Embed(title=f"Minecraft Server Status: {server_name}", color=discord.Color.green())
                embed.add_field(name="狀態", value="🟢 線上 (Online)", inline=True)
                embed.add_field(name="版本", value=status.version.name, inline=True)
                embed.add_field(name="人數", value=f"{status.players.online}/{status.players.max}", inline=True)
                embed.add_field(name="延遲", value=f"{status.latency:.2f}ms", inline=True)
                
                if status.players.sample:
                    player_names = [p.name for p in status.players.sample]
                    # 避免列表過長
                    if len(player_names) > 10:
                        player_str = ", ".join(player_names[:10]) + f" and {len(player_names)-10} more..."
                    else:
                        player_str = ", ".join(player_names)
                    embed.add_field(name="線上玩家", value=player_str, inline=False)
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                # print(e)
                embed = discord.Embed(title=f"Minecraft Server Status: {server_name}", color=discord.Color.orange())
                embed.add_field(name="狀態", value="🟡 啟動中或無法連線 (Starting/Unreachable)", inline=True)
                embed.add_field(name="詳細資訊", value=f"進程正在運行 (PID: {self.server_process.pid})，但無法 ping 到伺服器。\n可能正在啟動中。", inline=False)
                await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message("🔴 目前無伺服器啟動", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MCServer(bot))
