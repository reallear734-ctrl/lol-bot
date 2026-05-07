import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import database as db

TIER_ORDER = ["아이언", "브론즈", "실버", "골드", "플래티넘", "에메랄드", "다이아", "마스터", "그마", "챌린저"]
LINES = ["탑", "정글", "미드", "원딜", "서포터"]
LINE_EMOJI = {"탑": "🛡️", "정글": "🌲", "미드": "⚡", "원딜": "🏹", "서포터": "💊"}

def parse_team_input(raw: str) -> list[dict]:
    """
    입력 형식: 각 줄에 '닉네임 티어 라인'
    예시:
    홍길동 다이아 탑
    김철수 골드 정글
    """
    players = []
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) != 5:
        raise ValueError(f"팀원이 5명이어야 해요. (현재 {len(lines)}명 입력됨)")
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"'{line}' — 형식: 닉네임 티어 라인")
        name, tier, position = parts[0], parts[1], parts[2]
        if tier not in TIER_ORDER:
            raise ValueError(f"'{tier}'은 올바른 티어가 아니에요.\n가능한 티어: {', '.join(TIER_ORDER)}")
        if position not in LINES:
            raise ValueError(f"'{position}'은 올바른 라인이 아니에요.\n가능한 라인: {', '.join(LINES)}")
        players.append({"name": name, "tier": tier, "line": position})
    return players


def make_team_embed(game_id: str, blue: list, red: list, author: discord.User) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ 내전 등록 완료",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Game ID: {game_id} | 등록자: {author.display_name}")

    def team_str(players):
        return "\n".join(
            f"{LINE_EMOJI.get(p['line'], '•')} **{p['name']}** — {p['tier']} / {p['line']}"
            for p in players
        )

    embed.add_field(name="🔵 블루팀", value=team_str(blue), inline=True)
    embed.add_field(name="🔴 레드팀", value=team_str(red), inline=True)
    embed.add_field(
        name="결과 입력",
        value=f"`/결과입력 game_id:{game_id} winner:블루` 또는 `레드`",
        inline=False
    )
    return embed


class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # /내전등록
    # ─────────────────────────────────────────
    @app_commands.command(name="내전등록", description="블루/레드 5:5 내전 팀을 등록합니다.")
    @app_commands.describe(
        blue_team="블루팀 5명 (줄바꿈으로 구분, 형식: 닉네임 티어 라인)",
        red_team="레드팀 5명 (줄바꿈으로 구분, 형식: 닉네임 티어 라인)"
    )
    async def register_game(self, interaction: discord.Interaction, blue_team: str, red_team: str):
        await interaction.response.defer(ephemeral=False)

        try:
            blue = parse_team_input(blue_team)
            red = parse_team_input(red_team)
        except ValueError as e:
            await interaction.followup.send(f"❌ 입력 오류: {e}", ephemeral=True)
            return

        game_data = {
            "guild_id": str(interaction.guild_id),
            "blue_team": blue,
            "red_team": red,
            "winner": None,
            "status": "pending",
            "registered_by": str(interaction.user.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        game_id = db.save_game(game_data)
        embed = make_team_embed(game_id, blue, red, interaction.user)
        await interaction.followup.send(embed=embed)

    # ─────────────────────────────────────────
    # /결과입력
    # ─────────────────────────────────────────
    @app_commands.command(name="결과입력", description="내전 경기 결과를 입력합니다.")
    @app_commands.describe(
        game_id="경기 ID (/내전등록 후 발급됨)",
        winner="승리팀 선택"
    )
    @app_commands.choices(winner=[
        app_commands.Choice(name="🔵 블루팀 승리", value="blue"),
        app_commands.Choice(name="🔴 레드팀 승리", value="red"),
    ])
    async def input_result(self, interaction: discord.Interaction, game_id: str, winner: str):
        await interaction.response.defer()

        success = db.update_game_result(game_id, winner)
        if not success:
            await interaction.followup.send(f"❌ Game ID `{game_id}`를 찾을 수 없어요.", ephemeral=True)
            return

        game = db.get_game(game_id)
        winner_label = "🔵 블루팀" if winner == "blue" else "🔴 레드팀"

        embed = discord.Embed(
            title=f"🏆 결과 입력 완료 — {winner_label} 승리!",
            color=0x3498db if winner == "blue" else 0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Game ID", value=f"`{game_id}`", inline=True)
        embed.add_field(name="승리팀", value=winner_label, inline=True)
        embed.set_footer(text=f"입력자: {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    # ─────────────────────────────────────────
    # /최근경기
    # ─────────────────────────────────────────
    @app_commands.command(name="최근경기", description="최근 내전 경기 목록을 확인합니다.")
    async def recent_games(self, interaction: discord.Interaction):
        await interaction.response.defer()

        games = db.get_all_games(str(interaction.guild_id))
        if not games:
            await interaction.followup.send("아직 등록된 경기가 없어요!", ephemeral=True)
            return

        embed = discord.Embed(title="📋 최근 내전 기록", color=0x2ecc71)
        for g in games[:8]:
            status = g.get("status", "pending")
            if status == "completed":
                winner = "🔵 블루" if g.get("winner") == "blue" else "🔴 레드"
                status_str = f"{winner} 승리"
            else:
                status_str = "⏳ 결과 미입력"

            ts = g.get("timestamp", "")[:10]
            embed.add_field(
                name=f"`{g['game_id'][:8]}...` — {ts}",
                value=status_str,
                inline=False
            )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GameCog(bot))
