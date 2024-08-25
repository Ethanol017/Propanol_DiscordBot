import discord
from discord import app_commands
from discord.ext import commands
import subprocess
import re
class ARK(commands.GroupCog,name="ark"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    def ark_command(self,command:list):
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT)
            decoded_output = output.decode('utf-8')
            cleaned_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', decoded_output)
            print(cleaned_output)
            return cleaned_output
        except subprocess.CalledProcessError as e:
            error_output = e.output.decode('utf-8')
            cleaned_error_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', error_output)
            print(f"Command failed with error {e.returncode}: {cleaned_error_output}")
            return f"Command failed with error {e.returncode}: {cleaned_error_output}"

    @app_commands.command(name="start")
    async def start(self, interaction: discord.Interaction) -> None:
        """ /ark start """
        await interaction.response.send_message("Start server")
        command = ['sudo', 'arkmanager','start',"@main"]
        self.ark_command(command)

    @app_commands.command(name="stop")
    async def stop(self, interaction: discord.Interaction) -> None:
        """ /ark stop """
        await interaction.response.send_message("Stop server")
        command = ['sudo', 'arkmanager','stop',"@main"]
        self.ark_command(command)

    @app_commands.command(name="status")
    async def status(self, interaction: discord.Interaction) -> None:
        """ /ark status """
        await interaction.response.send_message("Server status",ephemeral=True)
        command = ['sudo', 'arkmanager','status',"@main"]
        staus =  self.ark_command(command)
        await interaction.followup.send(staus,ephemeral=True)

    @app_commands.command(name="restart")
    async def restart(self, interaction: discord.Interaction) -> None:
        """ /ark restart """
        await interaction.response.send_message("Restart server")
        command = ['sudo', 'arkmanager','restart',"@main"]
        self.ark_command(command)

async def setup(bot):
    await bot.add_cog(ARK(bot))
