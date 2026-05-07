import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 로그인 완료!")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 커맨드 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 커맨드 동기화 실패: {e}")

# Cog 로드
async def load_cogs():
    await bot.load_extension("cogs.game")
    await bot.load_extension("cogs.stats")

import asyncio

async def main():
    await load_cogs()
    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
