import os
import re
import io
import asyncio
import requests
import discord

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# SETTINGS
# =========================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

AI_CHANNEL_ID = int(os.getenv("AI_CHANNEL_ID", "0"))

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "openrouter/free"


# =========================================================
# CHECK ENV
# =========================================================

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is missing")

if not AI_CHANNEL_ID:
    raise RuntimeError("AI_CHANNEL_ID is missing")


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are Firstmc AI.

You are a general purpose AI assistant inside Discord.

RULES:

- Reply in the same language as the user.
- Arabic user = Arabic response.
- English user = English response.
- Do not require commands.
- Understand normal natural language.
- Be direct and useful.
- Do not use Discord embeds.
- Normal responses should be normal Discord text.

MINECRAFT:

You can help with:

Paper
Spigot
Bukkit
Purpur
Fabric
Forge
NeoForge
Skript
Java plugins
WorldGuard
WorldEdit
FAWE
LuckPerms
TAB
Essentials
Multiverse
DeluxeMenus
Geyser
Citizens
ZNPCsPlus
PvP
BoxPvP
SMP
FFA
server configuration
commands
permissions
optimization

EXISTING PLUGIN:

If the user asks for an existing plugin:
- Do not invent one.
- Use web search results when available.
- Give the real plugin name.
- Give compatibility information when available.
- Give the official website/download page when available.

PLUGIN CREATION:

If the user asks to CREATE a plugin:
- Generate the complete plugin.
- Include all required Java files.
- Include plugin.yml.
- Include pom.xml when appropriate.
- Make it compatible with the requested Minecraft/Paper version.

SKRIPT:

When creating a Skript file, use:

<SKRIPT filename="example.sk">
COMPLETE SKRIPT
</SKRIPT>

The bot converts this into a downloadable .sk file.

CODE FIXING:

If the user sends broken code:
- Find the problem.
- Fix it.
- Return the complete corrected file.
- Do not return only a small fragment when a complete file is needed.

GENERAL:

You are not limited to Minecraft.
You can answer general questions too.

Do not claim you searched the internet unless search results were actually provided.
"""


# =========================================================
# SEARCH
# =========================================================

SEARCH_WORDS = [
    "ابحث",
    "دور",
    "دورلي",
    "وين",
    "موقع",
    "رابط",
    "تحميل",
    "بلوقن",
    "بلجن",
    "استضافة",
    "هوست",
    "إصدار",
    "نسخة",
    "متوافق",
    "متوافقة",
    "آخر",
    "احدث",
    "أحدث",
    "جديد",
    "اليوم",
    "الآن",
    "حاليا",
    "حالياً",
    "plugin",
    "plugins",
    "download",
    "website",
    "hosting",
    "host",
    "latest",
    "current",
    "new",
    "compatible",
    "version",
]


def should_search(text):

    text = text.lower()

    for word in SEARCH_WORDS:
        if word.lower() in text:
            return True

    return False


def web_search(query):

    if not BRAVE_API_KEY:
        print("WEB SEARCH DISABLED: BRAVE_API_KEY missing")
        return []

    try:

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY
            },
            params={
                "q": query,
                "count": 6
            },
            timeout=10
        )

        print("BRAVE STATUS:", response.status_code)

        if response.status_code != 200:
            print("BRAVE RESPONSE:", response.text[:2000])
            return []

        data = response.json()

        results = []

        for item in data.get("web", {}).get("results", [])[:6]:

            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", "")
            })

        print("SEARCH RESULTS:", len(results))

        return results

    except Exception as e:

        print("BRAVE ERROR:", repr(e))

        return []


# =========================================================
# OPENROUTER
# =========================================================

def ask_ai_sync(user_message, search_results=None):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


    # Add search results
    if search_results:

        search_text = ""

        for result in search_results:

            search_text += (
                f"TITLE: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"DESCRIPTION: {result['description']}\n\n"
            )

        messages.append({
            "role": "system",
            "content":
                "These are current web search results. "
                "Use them when relevant.\n\n"
                + search_text
        })


    messages.append({
        "role": "user",
        "content": user_message
    })


    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4000
    }


    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://firstmc.ai",
        "X-Title": "Firstmc AI"
    }


    print("=" * 60)
    print("OPENROUTER REQUEST")
    print("MODEL:", MODEL)
    print("=" * 60)


    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=90
        )


        print("OPENROUTER STATUS:", response.status_code)

        print(
            "OPENROUTER RAW RESPONSE:",
            response.text[:5000]
        )


        # HTTP ERROR
        if response.status_code != 200:

            raise RuntimeError(
                f"OpenRouter HTTP {response.status_code}: "
                f"{response.text[:1500]}"
            )


        try:

            data = response.json()

        except Exception:

            raise RuntimeError(
                "OpenRouter returned invalid JSON:\n"
                + response.text[:1500]
            )


        # ERROR OBJECT
        if "error" in data:

            error = data["error"]

            raise RuntimeError(
                "OpenRouter API error: "
                + str(error)
            )


        # CHECK CHOICES
        choices = data.get("choices")

        if not choices:

            raise RuntimeError(
                "OpenRouter returned no choices:\n"
                + str(data)[:2000]
            )


        message = choices[0].get("message", {})

        content = message.get("content")


        if content is None:

            raise RuntimeError(
                "OpenRouter returned NULL content:\n"
                + str(data)[:2000]
            )


        content = str(content).strip()


        if not content:

            raise RuntimeError(
                "OpenRouter returned EMPTY content:\n"
                + str(data)[:2000]
            )


        print("OPENROUTER SUCCESS")

        return content


    except requests.exceptions.Timeout:

        raise RuntimeError(
            "OpenRouter request timed out after 90 seconds."
        )


    except requests.exceptions.ConnectionError as e:

        raise RuntimeError(
            "Could not connect to OpenRouter: "
            + str(e)
        )


async def ask_ai(user_message, search_results=None):

    return await asyncio.to_thread(
        ask_ai_sync,
        user_message,
        search_results
    )


# =========================================================
# SKRIPT
# =========================================================

def extract_skript(text):

    pattern = (
        r'<SKRIPT\s+filename="([^"]+)"\s*>'
        r'(.*?)'
        r'</SKRIPT>'
    )

    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if not matches:
        return None

    filename, code = matches[0]

    filename = filename.strip()

    if not filename.endswith(".sk"):
        filename += ".sk"

    return filename, code.strip()


# =========================================================
# LONG MESSAGE
# =========================================================

async def send_long_message(channel, text):

    chunks = []

    while text:

        chunks.append(text[:1900])

        text = text[1900:]


    for chunk in chunks:

        await channel.send(chunk)


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print("=" * 60)

    print("FIRSTMC AI V5 ONLINE")

    print("Bot:", bot.user)

    print("AI Channel:", AI_CHANNEL_ID)

    print("Provider: OpenRouter")

    print("Model:", MODEL)

    print(
        "Web Search:",
        "ON" if BRAVE_API_KEY else "OFF"
    )

    channel = bot.get_channel(AI_CHANNEL_ID)

    if channel:

        print(
            "AI CHANNEL FOUND:",
            channel.name
        )

        permissions = channel.permissions_for(
            channel.guild.me
        )

        print(
            "SEND:",
            permissions.send_messages
        )

        print(
            "VIEW:",
            permissions.view_channel
        )

        print(
            "HISTORY:",
            permissions.read_message_history
        )

        print(
            "ATTACH:",
            permissions.attach_files
        )

    else:

        print(
            "WARNING: AI CHANNEL NOT FOUND"
        )

    print("=" * 60)


# =========================================================
# MESSAGE
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return


    if message.channel.id != AI_CHANNEL_ID:
        return


    text = message.content.strip()

    if not text:
        return


    print("=" * 60)

    print(
        "USER:",
        message.author
    )

    print(
        "MESSAGE:",
        text
    )

    print("=" * 60)


    try:

        async with message.channel.typing():

            # SEARCH
            search_results = []

            if should_search(text):

                print("SEARCH REQUEST")

                search_results = await asyncio.to_thread(
                    web_search,
                    text
                )


            # AI
            answer = await ask_ai(
                text,
                search_results
            )


            # SKRIPT
            skript = extract_skript(answer)


            if skript:

                filename, code = skript


                clean_answer = re.sub(
                    r'<SKRIPT\s+filename="[^"]+"\s*>'
                    r'.*?'
                    r'</SKRIPT>',
                    "",
                    answer,
                    flags=re.IGNORECASE | re.DOTALL
                ).strip()


                if clean_answer:

                    await send_long_message(
                        message.channel,
                        clean_answer
                    )


                file = discord.File(
                    io.BytesIO(
                        code.encode("utf-8")
                    ),
                    filename=filename
                )


                await message.channel.send(
                    file=file
                )


                print(
                    "FILE SENT:",
                    filename
                )


            else:

                await send_long_message(
                    message.channel,
                    answer
                )


    except Exception as e:

        print("=" * 60)

        print("FIRSTMC AI ERROR")

        print(
            "TYPE:",
            type(e).__name__
        )

        print(
            "ERROR:",
            str(e)
        )

        print(
            "REPR:",
            repr(e)
        )

        print("=" * 60)


        # Send the REAL error temporarily
        try:

            await message.channel.send(
                "❌ **AI Error**\n"
                f"```text\n"
                f"{type(e).__name__}: "
                f"{str(e)[:1500]}"
                f"\n```"
            )

        except Exception as discord_error:

            print(
                "DISCORD SEND ERROR:",
                repr(discord_error)
            )


# =========================================================
# RUN
# =========================================================

print("Starting Firstmc AI V5...")

bot.run(DISCORD_TOKEN)
