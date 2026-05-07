import discord
from discord.ext import commands
from discord import app_commands
import database as db

TIER_EMOJI = {
    "아이언": "🩶", "브론즈": "🟤", "실버": "⚪",
    "골드": "🟡", "플래티넘": "🟢", "에메랄드": "💚",
    "다이아": "💎", "마스터": "🔮", "그마": "👑", "챌린저": "🏆"
}


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # /전적조회
    # ─────────────────────────────────────────
    @app_commands.command(name="전적조회", description="특정 플레이어의 내전 전적을 조회합니다.")
    @app_commands.describe(player_name="조회할 닉네임")
    async def player_stats(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()

        stats = db.get_player_stats(str(interaction.guild_id), player_name)
        if not stats:
            await interaction.followup.send(f"❌ `{player_name}` 님의 전적이 없어요. (완료된 경기가 있어야 집계돼요)", ephemeral=True)
            return

        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total = stats.get("total", 0)
        winrate = stats.get("winrate", 0.0)

        # 승률에 따른 색상
        if winrate >= 60:
            color = 0x2ecc71
        elif winrate >= 50:
            color = 0x3498db
        elif winrate >= 40:
            color = 0xe67e22
        else:
            color = 0xe74c3c

        bar_filled = int(winrate / 10)
        bar = "🟦" * bar_filled + "⬛" * (10 - bar_filled)

        embed = discord.Embed(
            title=f"🎮 {player_name} 님의 내전 전적",
            color=color
        )
        embed.add_field(name="총 경기", value=f"**{total}판**", inline=True)
        embed.add_field(name="승 / 패", value=f"**{wins}승 {losses}패**", inline=True)
        embed.add_field(name="승률", value=f"**{winrate}%**", inline=True)
        embed.add_field(name="승률 그래프", value=bar, inline=False)

        await interaction.followup.send(embed=embed)

    # ─────────────────────────────────────────
    # /리더보드
    # ─────────────────────────────────────────
    @app_commands.command(name="리더보드", description="내전 승률 리더보드를 확인합니다. (최소 3판 이상)")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        players = db.get_leaderboard(str(interaction.guild_id), limit=10)
        if not players:
            await interaction.followup.send("아직 리더보드 데이터가 없어요. (3판 이상 플레이어부터 집계)", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 내전 승률 리더보드",
            description="최소 3판 이상 참여자 기준",
            color=0xf1c40f
        )

        medals = ["🥇", "🥈", "🥉"]
        rows = []
        for i, p in enumerate(players):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            rows.append(
                f"{medal} **{p['name']}** — {p['winrate']}% ({p['wins']}승 {p['losses']}패 / {p['total']}판)"
            )

        embed.description = "\n".join(rows)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
