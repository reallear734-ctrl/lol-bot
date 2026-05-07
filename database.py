import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Firebase 초기화
def init_firebase():
    if not firebase_admin._apps:
        firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if not firebase_json:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT 환경변수가 없어요!")
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()


# ───────────────────────────────────────────
# 경기 저장
# ───────────────────────────────────────────
def save_game(game_data: dict) -> str:
    """경기 결과를 Firestore에 저장하고 game_id 반환"""
    ref = db.collection("games").document()
    game_data["game_id"] = ref.id
    ref.set(game_data)
    return ref.id


# ───────────────────────────────────────────
# 전체 경기 목록 조회
# ───────────────────────────────────────────
def get_all_games(guild_id: str) -> list:
    """특정 서버의 모든 경기 조회 (최신순)"""
    docs = (
        db.collection("games")
        .where("guild_id", "==", guild_id)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


# ───────────────────────────────────────────
# 특정 게임 조회
# ───────────────────────────────────────────
def get_game(game_id: str) -> dict | None:
    doc = db.collection("games").document(game_id).get()
    return doc.to_dict() if doc.exists else None


# ───────────────────────────────────────────
# 경기 결과 업데이트 (승팀 기록)
# ───────────────────────────────────────────
def update_game_result(game_id: str, winner: str) -> bool:
    """winner: 'blue' or 'red'"""
    ref = db.collection("games").document(game_id)
    if not ref.get().exists:
        return False
    ref.update({"winner": winner, "status": "completed"})

    # 플레이어 통계 업데이트
    game = ref.get().to_dict()
    winning_team = game["blue_team"] if winner == "blue" else game["red_team"]
    losing_team = game["red_team"] if winner == "blue" else game["blue_team"]

    for player in winning_team:
        update_player_stats(game["guild_id"], player["name"], win=True)
    for player in losing_team:
        update_player_stats(game["guild_id"], player["name"], win=False)

    return True


# ───────────────────────────────────────────
# 플레이어 통계
# ───────────────────────────────────────────
def update_player_stats(guild_id: str, player_name: str, win: bool):
    ref = db.collection("players").document(f"{guild_id}_{player_name}")
    doc = ref.get()

    if doc.exists:
        data = doc.to_dict()
        data["wins"] = data.get("wins", 0) + (1 if win else 0)
        data["losses"] = data.get("losses", 0) + (0 if win else 1)
        data["total"] = data["wins"] + data["losses"]
        data["winrate"] = round(data["wins"] / data["total"] * 100, 1)
        ref.set(data)
    else:
        ref.set({
            "guild_id": guild_id,
            "name": player_name,
            "wins": 1 if win else 0,
            "losses": 0 if win else 1,
            "total": 1,
            "winrate": 100.0 if win else 0.0,
        })


def get_player_stats(guild_id: str, player_name: str) -> dict | None:
    doc = db.collection("players").document(f"{guild_id}_{player_name}").get()
    return doc.to_dict() if doc.exists else None


def get_leaderboard(guild_id: str, limit: int = 10) -> list:
    """승률 기준 상위 플레이어 (최소 3판 이상)"""
    docs = (
        db.collection("players")
        .where("guild_id", "==", guild_id)
        .where("total", ">=", 3)
        .order_by("total")  # winrate 복합 인덱스 필요 시 total 먼저
        .stream()
    )
    players = [doc.to_dict() for doc in docs]
    players.sort(key=lambda x: x["winrate"], reverse=True)
    return players[:limit]
