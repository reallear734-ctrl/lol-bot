import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import re
import database as db

LINE_EMOJI = {"탑": "🛡️", "정글": "🌲", "미드": "⚡", "원딜": "🏹", "서폿": "💊"}

LANE_ALIAS = {
    "ㅌ": "탑",
    "ㅈㄱ": "정글",
    "ㅁㄷ": "미드",
    "ㅇㄷ": "원딜",
    "ㅅㅍ": "서폿",
    "top": "탑",
    "jg": "정글",
    "jgl": "정글",
    "jungle": "정글",
    "mid": "미드",
    "middle": "미드",
    "ad": "원딜",
    "adc": "원딜",
    "bot": "원딜",
    "sup": "서폿",
    "supp": "서폿",
    "support": "서폿",
    "서포터": "서폿",
    "서포트": "서폿",
}

def normalize_lane(lane: str) -> str:
    lane = lane.strip()
    if lane.lower() in LANE_ALIAS:
        return LANE_ALIAS[lane.lower()]
    if lane in LANE_ALIAS:
        return LANE_ALIAS[lane]
    return lane

def normalize_tier(tier: str) -> str:
    tier = tier.strip()
    tier = re.sub(r'\(.*?\)', '', tier)
    return tier.strip()

# 티어 패턴: 영문자(1~3) + 숫자(0~2) 형태 ex) P1, D4, M40, G1, E3, C
TIER_PATTERN = re.compile(r'^[A-Za-z]{1,3}\d{0,2}$')

def find_tier_index(tokens: list[str]) -> int:
    """
    토큰 목록에서 '티어/티어' 패턴이 있는 인덱스 반환
    슬래시 기준으로 양쪽이 티어 패턴이면 그게 티어 토큰
    """
    for i, token in enumerate(tokens):
        # 슬래시 주변 공백 제거 후 확인
        t = re.sub(r'\s*/\s*', '/', token)
        if '/' in t:
            parts = t.split('/', 1)
            left = re.sub(r'\(.*?\)', '', parts[0]).strip()
            right = re.sub(r'\(.*?\)', '', parts[1]).strip()
            if TIER_PATTERN.match(left) and TIER_PATTERN.match(right):
                return i
    return -1

def parse_team_input(raw: str) -> list[dict]:
    """
    입력 형식: 닉네임(띄어쓰기 가능) 최고티어/현재티어 주라인/희망라인1 희망라인2...
    티어 패턴(ex: P1/D4)을 자동 감지해서 그 앞을 전부 닉네임으로 처리
    따옴표 불필요
    """
    players = []
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) != 5:
        raise ValueError(f"팀원이 5명이어야 해요. (현재 {len(lines)}명 입력됨)")

    for line in lines:
        # 슬래시 주변 공백 제거
        line = re.sub(r'\s*/\s*', '/', line)
        tokens = line.split()

        # 티어 토큰 위치 찾기
        tier_idx = find_tier_index(tokens)
        if tier_idx == -1:
            raise ValueError(
                f"티어를 찾을 수 없어요: '{line}'\n"
                f"형식: 닉네임 최고티어/현재티어 주라인/희망라인 희망라인2\n"
                f"예시: 별 뜨는 밤에#kr1 P1/D4 서폿/원딜 정글"
            )
        if tier_idx == 0:
            raise ValueError(f"닉네임이 없어요: '{line}'")

        # 닉네임: 티어 앞 토큰 전부
        name = " ".join(tokens[:tier_idx])

        # 티어 파싱
        tier_part = tokens[tier_idx]
        tier_split = tier_part.split("/", 1)
        peak_tier = normalize_tier(tier_split[0])
        current_tier = normalize_tier(tier_split[1])

        # 라인 파싱
        remaining = tokens[tier_idx + 1:]
        if not remaining:
            raise ValueError(f"라인 정보가 없어요: '{line}'")

        lane_part = remaining[0]
        if "/" not in lane_part:
            raise ValueError(
                f"'{lane_part}' — 라인 형식: 주라인/희망라인 (예: 서폿/원딜)"
            )
        lane_split = lane_part.split("/", 1)
        main_lane = normalize_lane(lane_split[0])
        prefer_lanes = [normalize_lane(l) for l in [lane_split[1]] + remaining[1:]]

        players.append({
            "name": name,
            "peak_tier": peak_tier,
            "current_tier": current_tier,
            "main_lane": main_lane,
            "prefer_lanes": prefer_lanes,
        })

    return players


def make_team_embed(game_id: str, blue: list, red: list, author: discord.User) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ 내전 등록 완료",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Game ID: {game_id} | 등록자: {author.display_name}")

    def team_str(players):
        rows = []
        for p in players:
            emoji = LINE_EMOJI.get(p["main_lane"], "•")
            prefer = " / ".join(p["prefer_lanes"])
            rows.append(
                f"{emoji} **{p['name']}**\n"
                f"　티어: `{p['peak_tier']}` / `{p['current_tier']}`\n"
                f"　주라인: {p['main_lane']} │ 희망: {prefer}"
            )
        return "\n\n".join(rows)

    embed.add_field(name="🔵 블루팀", value=team_str(blue), inline=False)
    embed.add_field(name="🔴 레드팀", value=team_str(red), inline=False)
    embed.add_field(
        name="📌 결과 입력",
        value=f"`/결과입력` 으로 결과를 입력해주세요\nGame ID: `{game_id}`",
        inline=False
    )
    return embed


class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="내전등록", description="블루/레드 5:5 내전 팀을 등록합니다.")
    @app_commands.describe(
        blue_team="블루팀 5명 (Shift+Enter로 줄바꿈) 예: 별 뜨는 밤에#kr1 P1/D4 서폿/원딜 정글",
        red_team="레드팀 5명 (Shift+Enter로 줄바꿈) 예: 별 뜨는 밤에#kr1 P1/D4 서폿/원딜 정글"
    )
    async def register_game(self, interaction: discord.Interaction, blue_team: str, red_team: str):
        await interaction.response.defer(ephemeral=False)

        try:
            blue = parse_team_input(blue_team)
            red = parse_team_input(red_team)
        except ValueError as e:
            await interaction.followup.send(f"❌ 입력 오류\n{e}", ephemeral=True)
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
