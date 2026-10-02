import os
import re
import io
import asyncio
import requests
import discord

from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AI_CHANNEL_ID = int(os.getenv("AI_CHANNEL_ID", "1555286306182139915"))

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing")


# =========================
# GROQ SETTINGS
# =========================

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MODEL = "openai/gpt-oss-120b"


# =========================
# AI SYSTEM PROMPT
# =========================

SYSTEM_PROMPT = r"""
You are Firstmc AI, the official AI assistant for FirstMC.

You are a general-purpose AI assistant.
You can help with:
- Minecraft
- Paper
- Spigot
- Bukkit
- Fabric
- Forge
- Skript
- Java plugins
- Python
- JavaScript
- HTML
- CSS
- YAML
- JSON
- Discord bots
- Linux
- Termux
- Git
- GitHub
- Railway
- Hosting
- Programming
- General questions

IMPORTANT:

1. Always answer in the same language as the user.
2. If the user speaks Arabic, answer in Arabic.
3. If the user speaks English, answer in English.
4. Keep normal answers clear and reasonably concise.
5. Do not invent facts, plugins, URLs, versions, commands, APIs, or features.
6. If information may have changed recently, use web search when available.
7. If the user asks you to find an EXISTING plugin, do NOT create one.
8. If the user asks you to CREATE a plugin, create the plugin.
9. If the user asks to fix code, return the complete corrected code when practical.
10. Preserve the user's requested filenames.
11. Never expose API keys, tokens, passwords, or secrets.

FIRSTMC CONTEXT:

Minecraft server:
FirstMC

Main server focus:
BoxPvP + SMP + FFA

Common server software:
Paper

Current Minecraft version:
1.21.11

Java:
21

Common plugins:
Skript
WorldEdit
FAWE
WorldGuard
LuckPerms
TAB
Multiverse-Core
Essentials
Geyser
DeluxeMenus
Citizens
ZNPCsPlus
DecentHolograms
AdvancedBanZ
CombatLog
PlayerKits

When giving Minecraft code, prefer compatibility with Paper 1.21.x and Java 21 unless the user specifies otherwise.

SKRIPT FILES:

If the user asks for a Skript file, return it using this exact wrapper:

<SKRIPT filename="example.sk">
PASTE COMPLETE SKRIPT HERE
</SKRIPT>

Example:

<SKRIPT filename="spawn.sk">
command /spawn:
    trigger:
        teleport player to spawn
</SKRIPT>

Do not put Markdown code fences around the SKRIPT wrapper.

JAVA PLUGINS:

If the user asks for a Java plugin, provide complete project files when needed.

Use this style:

<FILE path="src/main/java/com/firstmc/example/Main.java">
COMPLETE FILE
</FILE>

<FILE path="src/main/resources/plugin.yml">
COMPLETE FILE
</FILE>

<FILE path="pom.xml">
COMPLETE FILE
</FILE>

Do not invent missing dependencies.

OTHER FILES:

You may use:

<FILE path="filename.py">
CODE
</FILE>

<FILE path="filename.js">
CODE
</FILE>

<FILE path="filename.yml">
CODE
</FILE>

<FILE path="filename.json">
CODE
</FILE>

<FILE path="filename.html">
CODE
</FILE>

<FILE path="filename.css">
CODE
</FILE>

When multiple files are requested, provide all required files.

PLUGIN SEARCH:

If the user asks:
"find a plugin"
"give me a plugin"
"what plugin does this"
"دورلي بلوقن"
"ابحث عن بلوقن"

Treat it as a request for an existing plugin.

Do not silently create a replacement plugin.

If web search results are available:
- give the real plugin name
- explain what it does
- give compatibility information
- provide the official website/download page when known
- do not invent URLs

PLUGIN CREATION:

If the user explicitly says:
"make a plugin"
"create a plugin"
"برمجلي بلوقن"
"سوي لي بلوقن"

Then create the plugin.

CODE FIXING:

If the user gives broken code:
- identify the problem briefly
- provide the corrected complete code
- do not return only a tiny fragment if the complete file can be provided

MINECRAFT COMMANDS:

Commands should be shown in code blocks.

Do not use unnecessary decoration.

DISCORD:

The bot is intended to operate inside a dedicated Discord AI channel.

Do not require slash commands for normal AI conversations.

The user can simply write natural language.

SAFETY:

Do not help with harmful, illegal, dangerous, or abusive activity.

Do not claim that you performed an action if you only generated instructions.

Always be honest about what you can and cannot do.
"""


# =========================
# DISCORD
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# FILE EXTRACTION
# =========================

def extract_skript(text):
    pattern = r'<SKRIPT\s+filename="([^"]+)"\s*>(.*?)</SKRIPT>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    if not matches:
        return None

    filename, content = matches[0]

    filename = os.path.basename(filename)

    if not filename.endswith(".sk"):
        filename += ".sk"

    return filename, content.strip()


def extract_files(text):
    pattern = r'<FILE\s+path="([^"]+)"\s*>(.*?)</FILE>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    files = []

    for path, content in matches:
        path = path.strip().replace("\\", "/")

        # Prevent dangerous filesystem paths
        path = path.replace("../", "")
        path = path.lstrip("/")

        if not path:
            continue

        files.append(
            (
                path,
                content.strip()
            )
        )

    return files


# =========================
# GROQ API
# =========================

def ask_groq(messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 12000
    }

    response = requests.post(
        GROQ_URL,
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        try:
            error_data = response.json()
        except Exception:
            error_data = response.text

        raise RuntimeError(
            f"Groq API error {response.status_code}: {error_data}"
        )

    data = response.json()

    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError("Groq returned no choices.")

    content = choices[0].get("message", {}).get("content")

    if not content:
        raise RuntimeError("Groq returned an empty response.")

    return content


async def ask_ai(user_message, history=None):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if history:
        messages.extend(history[-10:])

    messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    return await asyncio.to_thread(
        ask_groq,
        messages
    )


# =========================
# DISCORD MESSAGE CHUNKING
# =========================

async def send_chunks(channel, text):
    if not text:
        return

    # Discord message limit
    chunks = []

    while len(text) > 1900:
        split_at = text.rfind("\n", 0, 1900)

        if split_at <= 0:
            split_at = 1900

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    if text:
        chunks.append(text)

    for chunk in chunks:
        await channel.send(chunk)


# =========================
# SEND GENERATED FILE
# =========================

async def send_file_content(
    channel,
    filename,
    content,
    description=None
):

    data = content.encode("utf-8")

    file = discord.File(
        io.BytesIO(data),
        filename=filename
    )

    if description:
        await channel.send(
            content=description,
            file=file
        )
    else:
        await channel.send(
            file=file
        )


# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"AI Channel: {AI_CHANNEL_ID}")
    print(f"Groq Model: {MODEL}")
    print("Web search: Groq built-in tools available")
    print("Firstmc AI V4 online")
    print("=" * 50)


# =========================
# MESSAGE HANDLER
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.channel.id != AI_CHANNEL_ID:
        return

    user_text = message.content.strip()

    if not user_text:
        return

    async with message.channel.typing():

        try:

            response = await ask_ai(
                user_text
            )

            # =========================
            # SKRIPT
            # =========================

            skript = extract_skript(response)

            if skript:

                filename, content = skript

                clean_response = re.sub(
                    r'<SKRIPT\s+filename="[^"]+"\s*>.*?</SKRIPT>',
                    '',
                    response,
                    flags=re.DOTALL | re.IGNORECASE
                ).strip()

                if clean_response:
                    await send_chunks(
                        message.channel,
                        clean_response
                    )

                await send_file_content(
                    message.channel,
                    filename,
                    content,
                    f"📄 `{filename}`"
                )

                return

            # =========================
            # OTHER FILES
            # =========================

            files = extract_files(response)

            if files:

                clean_response = re.sub(
                    r'<FILE\s+path="[^"]+"\s*>.*?</FILE>',
                    '',
                    response,
                    flags=re.DOTALL | re.IGNORECASE
                ).strip()

                if clean_response:
                    await send_chunks(
                        message.channel,
                        clean_response
                    )

                for path, content in files:

                    filename = os.path.basename(path)

                    await send_file_content(
                        message.channel,
                        filename,
                        content,
                        f"📄 `{path}`"
                    )

                return

            # =========================
            # NORMAL RESPONSE
            # =========================

            await send_chunks(
                message.channel,
                response
            )

        except Exception as e:

            print(
                f"[ERROR] {type(e).__name__}: {e}"
            )

            await message.channel.send(
                "❌ صار خطأ أثناء معالجة طلبك. "
                "شوف Railway Logs لمعرفة الخطأ."
            )

    await bot.process_commands(message)


# =========================
# RUN
# =========================

bot.run(DISCORD_TOKEN)
