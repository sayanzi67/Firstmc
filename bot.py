import os
import re
import io

import discord
from discord.ext import commands
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_CHANNEL_ID = int(os.getenv("AI_CHANNEL_ID", "0"))

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing")

ai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

SYSTEM_PROMPT = """
أنت Firstmc AI، مساعد ذكي متخصص في Minecraft وSkript وPlugins وDiscord والبرمجة.

أنت تعمل داخل روم مخصص للذكاء الاصطناعي.

القواعد:

1. افهم كلام المستخدم الطبيعي بدون الحاجة إلى أوامر محددة.
2. إذا قال المستخدم "سوي" أو "اعمل" أو "اكتب" أو "أنشئ"، افهم المطلوب ونفذه.
3. إذا كان المستخدم يريد Skript، أنشئ Skript جاهزاً للعمل.
4. إذا طلب المستخدم تعديل سكربت، أعد كتابة النسخة كاملة بعد التعديل.
5. إذا طلب إصلاح خطأ، حلل الخطأ وأعطِ الحل والكود المصحح.
6. إذا طلب شرحاً، اشرح له بدلاً من إنشاء ملف.
7. إذا طلب Plugin Java، يمكنك إنشاء ملفات المشروع المطلوبة.
8. تحدث بلغة المستخدم نفسها.
9. إذا كتب المستخدم بالعربية، استخدم العربية الفصحى الواضحة.
10. لا تستخدم اللهجة إلا إذا طلب المستخدم ذلك.
11. كن مختصراً وعملياً.
12. لا تخترع معلومات تقنية غير مؤكدة.
13. عند الحاجة إلى معلومات حديثة، وضح أن المعلومات تحتاج إلى التحقق من مصدر حديث.

عند إنشاء ملف Skript يجب استخدام هذا التنسيق بالضبط:

<SKRIPT filename="اسم_الملف.sk">
كود السكربت هنا
</SKRIPT>

لا تضع Markdown داخل وسم SKRIPT.
"""

def extract_skript(text):
    pattern = r'<SKRIPT\s+filename="([^"]+)">\s*(.*?)\s*</SKRIPT>'

    match = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    filename = os.path.basename(match.group(1))
    code = match.group(2).strip()

    if not filename.endswith(".sk"):
        filename += ".sk"

    return filename, code


@bot.event
async def on_ready():
    print("=" * 40)
    print(f"Logged in as: {bot.user}")
    print(f"AI Channel: {AI_CHANNEL_ID}")
    print("Firstmc AI is online")
    print("=" * 40)


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.channel.id != AI_CHANNEL_ID:
        return

    prompt = message.content.strip()

    if not prompt:
        return

    async with message.channel.typing():

        try:
            response = ai.responses.create(
                model="gpt-5",
                instructions=SYSTEM_PROMPT,
                input=prompt
            )

            answer = response.output_text.strip()

            skript = extract_skript(answer)

            if skript:
                filename, code = skript

                file_data = io.BytesIO(
                    code.encode("utf-8")
                )

                discord_file = discord.File(
                    file_data,
                    filename=filename
                )

                clean_answer = re.sub(
                    r'<SKRIPT\s+filename="[^"]+">.*?</SKRIPT>',
                    '',
                    answer,
                    flags=re.IGNORECASE | re.DOTALL
                ).strip()

                if clean_answer:
                    await message.reply(
                        clean_answer,
                        file=discord_file,
                        mention_author=False
                    )
                else:
                    await message.reply(
                        "تم إنشاء السكربت وإرفاقه لك.",
                        file=discord_file,
                        mention_author=False
                    )

                return

            if len(answer) <= 1900:

                await message.reply(
                    answer,
                    mention_author=False
                )

            else:

                chunks = [
                    answer[i:i + 1900]
                    for i in range(0, len(answer), 1900)
                ]

                for chunk in chunks:
                    await message.channel.send(chunk)

        except Exception as error:

            print("ERROR:", repr(error))

            await message.reply(
                "حدث خطأ أثناء معالجة طلبك.",
                mention_author=False
            )


bot.run(DISCORD_TOKEN)
