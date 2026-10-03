# =============================================================================
#  MPS TEAM MANAGER
#  Bot de Discord para gerenciamento de time de MPS (futebol no Roblox).
#  Arquivo único: tudo (banco, comandos, painéis, imagens) está neste main.py.
# =============================================================================

# >>> ÚNICO LUGAR QUE VOCÊ PRECISA EDITAR PARA O BOT FUNCIONAR <<<
TOKEN = "MTU1NTc2NzgyNjY3MTczMDY4OA.G2HosM.WU7Bb_bHie5_bOrNI25KMtS21PgS7Y8nq71VYQ"

# ==============================
# IMPORTS
# ==============================
import asyncio
import io
import json
import logging
import re
import sqlite3
import sys
import threading
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Awaitable, Callable, Optional

import discord
from discord import app_commands
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont

# ==============================
# CONFIGURAÇÕES
# ==============================

# Arquivo do banco SQLite (criado automaticamente na primeira execução).
DB_PATH = "mps_team.db"

# Opcional: coloque aqui o ID do seu servidor para os comandos aparecerem
# instantaneamente durante os testes. Deixe None para registrar globalmente.
GUILD_DE_TESTE: Optional[int] = None

# Padrões de configuração (cada servidor pode sobrescrever tudo pelo /config).
DEFAULT_CONFIG = {
    "team_name": "",            # vazio = usa o nome do servidor
    "color": "#3B82F6",
    "footer": "",
    "logo_url": "",
    "tz_offset": "-3",          # fuso em horas (Brasília = -3)
    "w_goal": "3",
    "w_assist": "2",
    "w_win": "3",
    "w_mvp": "10",
    "rank_d": "0",
    "rank_c": "50",
    "rank_b": "120",
    "rank_a": "250",
    "rank_s": "450",
    "log_channel": "",
    "results_channel": "",
    "calendar_channel": "",
    "ranking_channel": "",
    "admin_role": "",
    "player_role": "",
    "lineup_formation": "4-3-3",
    "lineup_avatars": "1",
    "lineup_numbers": "1",
    "calendar_message_id": "",
    "ranking_message_id": "",
}

SUCCESS_COLOR = 0x2ECC71
ERROR_COLOR = 0xE74C3C
WARN_COLOR = 0xF1C40F
NEUTRAL_COLOR = 0x95A5A6

STATUS_LABELS = {
    "ativo": "🟢 Ativo",
    "reserva": "🟡 Reserva",
    "suspenso": "🔴 Suspenso",
    "inativo": "⚫ Inativo",
}

RANKS = ["D", "C", "B", "A", "S"]
RANK_COLORS = {"D": 0x95A5A6, "C": 0xCD7F32, "B": 0x3B82F6, "A": 0x9B59B6, "S": 0xF1C40F}
RANK_ICONS = {"D": "⚪", "C": "🟤", "B": "🔵", "A": "🟣", "S": "🟡"}

POSITION_NAMES = {
    "GOL": "Goleiro",
    "ZAG": "Zagueiro",
    "LD": "Lateral direito",
    "LE": "Lateral esquerdo",
    "VOL": "Volante",
    "MC": "Meio-campista",
    "MEI": "Meia atacante",
    "PD": "Ponta direita",
    "PE": "Ponta esquerda",
    "SA": "Segundo atacante",
    "ATA": "Atacante",
}
POSITION_LINE = {"GOL": 0, "ZAG": 1, "LE": 1, "LD": 1, "VOL": 2, "MC": 2, "MEI": 2,
                 "PE": 3, "PD": 3, "SA": 3, "ATA": 3}
POSITION_ALIASES = {
    "GK": "GOL", "GOLEIRO": "GOL", "ZG": "ZAG", "ZAGUEIRO": "ZAG", "DEF": "ZAG",
    "LAT": "LD", "LATD": "LD", "LATE": "LE", "VOLANTE": "VOL", "MEIO": "MC",
    "MEIA": "MEI", "MD": "MC", "ME": "MC", "CA": "ATA", "ATACANTE": "ATA",
    "CENTROAVANTE": "ATA", "PTD": "PD", "PTE": "PE", "SEG": "SA",
}

# Cada formação é uma lista de linhas (do goleiro até o ataque); cada linha
# lista as posições "ideais" dos slots, da esquerda para a direita.
FORMATIONS = {
    "4-3-3": [["GOL"], ["LE", "ZAG", "ZAG", "LD"], ["MC", "VOL", "MEI"], ["PE", "ATA", "PD"]],
    "4-4-2": [["GOL"], ["LE", "ZAG", "ZAG", "LD"], ["MC", "VOL", "MEI", "MC"], ["SA", "ATA"]],
    "3-5-2": [["GOL"], ["ZAG", "ZAG", "ZAG"], ["LE", "VOL", "MC", "MEI", "LD"], ["SA", "ATA"]],
    "5-3-2": [["GOL"], ["LE", "ZAG", "ZAG", "ZAG", "LD"], ["MC", "VOL", "MEI"], ["SA", "ATA"]],
}

# Conquistas: (código, emoji, nome, descrição, métrica, meta)
ACHIEVEMENTS = [
    ("gol_1", "⚽", "Primeiro gol", "Marque o seu primeiro gol", "goals", 1),
    ("gol_10", "⚽", "10 gols", "Alcance 10 gols", "goals", 10),
    ("gol_25", "⚽", "25 gols", "Alcance 25 gols", "goals", 25),
    ("gol_50", "⚽", "50 gols", "Alcance 50 gols", "goals", 50),
    ("gol_100", "💯", "100 gols", "Alcance 100 gols", "goals", 100),
    ("hattrick", "🎩", "Hat-trick", "Marque 3 gols na mesma partida", "best_match_goals", 3),
    ("ass_10", "🅰️", "10 assistências", "Alcance 10 assistências", "assists", 10),
    ("ass_25", "🅰️", "25 assistências", "Alcance 25 assistências", "assists", 25),
    ("mvp_1", "🏅", "Primeiro MVP", "Seja o MVP de uma partida", "mvps", 1),
    ("mvp_5", "🏅", "5 MVPs", "Seja o MVP em 5 partidas", "mvps", 5),
    ("vit_10", "🏆", "10 vitórias", "Participe de 10 vitórias", "wins", 10),
    ("vit_25", "🏆", "25 vitórias", "Participe de 25 vitórias", "wins", 25),
    ("seq_5", "🔥", "5 vitórias seguidas", "Vença 5 partidas seguidas", "streak", 5),
    ("jogos_50", "🏟️", "50 jogos", "Dispute 50 partidas", "games", 50),
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("mps")

# ==============================
# BANCO DE DADOS
# ==============================

_db_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    guild_id INTEGER PRIMARY KEY,
    name TEXT,
    joined_at TEXT
);
CREATE TABLE IF NOT EXISTS config (
    guild_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    number INTEGER NOT NULL DEFAULT 0,
    position TEXT NOT NULL DEFAULT 'ATA',
    status TEXT NOT NULL DEFAULT 'ativo',
    rank_override TEXT,
    joined_at TEXT,
    updated_at TEXT,
    UNIQUE (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS player_stats (
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    games INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    mvps INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0,
    rank TEXT NOT NULL DEFAULT 'D',
    updated_at TEXT,
    PRIMARY KEY (guild_id, player_id)
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    game_id INTEGER,
    opponent TEXT NOT NULL,
    our_score INTEGER NOT NULL,
    opp_score INTEGER NOT NULL,
    result TEXT NOT NULL,
    played_date TEXT NOT NULL,
    played_time TEXT,
    competition TEXT,
    mvp_player_id INTEGER,
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS match_players (
    match_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    PRIMARY KEY (match_id, player_id)
);
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    match_id INTEGER,
    amount INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'partida',
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS assists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    match_id INTEGER,
    amount INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'partida',
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS mvps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    match_id INTEGER,
    amount INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'partida',
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    opponent TEXT NOT NULL,
    game_date TEXT NOT NULL,
    game_time TEXT,
    competition TEXT,
    location TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    match_id INTEGER,
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS lineups (
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    position TEXT NOT NULL,
    added_at TEXT,
    PRIMARY KEY (guild_id, player_id)
);
CREATE TABLE IF NOT EXISTS presence_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL UNIQUE,
    game_id INTEGER,
    title TEXT,
    embeds_json TEXT,
    links_json TEXT,
    is_open INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS presence_responses (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    response TEXT NOT NULL,
    updated_at TEXT,
    PRIMARY KEY (event_id, user_id)
);
CREATE TABLE IF NOT EXISTS achievements (
    guild_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    unlocked_at TEXT,
    PRIMARY KEY (guild_id, player_id, code)
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    category TEXT,
    action TEXT,
    details TEXT,
    before_data TEXT,
    after_data TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_players_guild ON players (guild_id, status);
CREATE INDEX IF NOT EXISTS idx_goals_player ON goals (player_id);
CREATE INDEX IF NOT EXISTS idx_assists_player ON assists (player_id);
CREATE INDEX IF NOT EXISTS idx_mvps_player ON mvps (player_id);
CREATE INDEX IF NOT EXISTS idx_goals_match ON goals (match_id);
CREATE INDEX IF NOT EXISTS idx_assists_match ON assists (match_id);
CREATE INDEX IF NOT EXISTS idx_matches_guild ON matches (guild_id, played_date);
CREATE INDEX IF NOT EXISTS idx_games_guild ON games (guild_id, status, game_date);
CREATE INDEX IF NOT EXISTS idx_logs_guild ON logs (guild_id, id);
"""


def init_db(path: Optional[str] = None) -> None:
    """Cria (se necessário) o banco SQLite e todas as tabelas."""
    global _conn
    with _db_lock:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        _conn.executescript(SCHEMA)
        _conn.commit()


def db_exec(sql: str, params: tuple = ()) -> int:
    with _db_lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur.lastrowid


def db_all(sql: str, params: tuple = ()) -> list:
    with _db_lock:
        return _conn.execute(sql, params).fetchall()


def db_one(sql: str, params: tuple = ()):
    with _db_lock:
        return _conn.execute(sql, params).fetchone()


@contextmanager
def db_tx():
    """Transação atômica: tudo dentro do bloco é salvo junto ou nada é salvo."""
    with _db_lock:
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback()
            raise


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ----- configuração por servidor ------------------------------------------------

def cfg_get(gid: int, key: str) -> str:
    row = db_one("SELECT value FROM config WHERE guild_id=? AND key=?", (gid, key))
    if row is not None and row["value"] is not None:
        return row["value"]
    return DEFAULT_CONFIG.get(key, "")


def cfg_set(gid: int, key: str, value: Any) -> None:
    db_exec(
        "INSERT INTO config (guild_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
        (gid, key, "" if value is None else str(value)),
    )


def cfg_int(gid: int, key: str) -> Optional[int]:
    v = cfg_get(gid, key)
    try:
        return int(v) if str(v).strip() else None
    except (TypeError, ValueError):
        return None


def cfg_float(gid: int, key: str, default: float = 0.0) -> float:
    try:
        return float(str(cfg_get(gid, key)).replace(",", "."))
    except (TypeError, ValueError):
        return default


def ensure_guild(guild: discord.Guild) -> None:
    db_exec(
        "INSERT INTO guilds (guild_id, name, joined_at) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id) DO UPDATE SET name=excluded.name",
        (guild.id, guild.name, now_utc_iso()),
    )


# ==============================
# FUNÇÕES AUXILIARES
# ==============================

class UserError(Exception):
    """Erro 'esperado' (entrada inválida, falta de permissão etc.) mostrado ao usuário."""

    def __init__(self, message: str, title: str = "Não foi possível concluir"):
        super().__init__(message)
        self.title = title
        self.message = message


class NotStaff(app_commands.CheckFailure):
    """Usuário sem permissão administrativa."""


def trunc(text: Any, n: int, suffix: str = "…") -> str:
    s = "" if text is None else str(text)
    return s if len(s) <= n else s[: max(0, n - len(suffix))] + suffix


def fmt_num(x: float) -> str:
    try:
        if float(x) == int(float(x)):
            return str(int(float(x)))
        return f"{float(x):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def fmt_pct(x: float) -> str:
    return f"{int(round(x))}%"


def progress_bar(pct: float, size: int = 10) -> str:
    filled = max(0, min(size, int(round(pct / 100 * size))))
    return "▰" * filled + "▱" * (size - filled)


def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]


def team_name_of(gid: int) -> str:
    name = cfg_get(gid, "team_name").strip()
    if name:
        return name
    row = db_one("SELECT name FROM guilds WHERE guild_id=?", (gid,))
    return row["name"] if row and row["name"] else "MEU TIME"


def local_now(gid: int) -> datetime:
    off = max(-12.0, min(14.0, cfg_float(gid, "tz_offset", -3.0)))
    return datetime.now(timezone(timedelta(hours=off)))


def today_iso(gid: int) -> str:
    return local_now(gid).strftime("%Y-%m-%d")


def fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


COLOR_NAMES = {
    "azul": 0x3B82F6, "verde": 0x2ECC71, "vermelho": 0xE74C3C, "amarelo": 0xF1C40F,
    "roxo": 0x9B59B6, "laranja": 0xE67E22, "rosa": 0xEC4899, "preto": 0x111827,
    "branco": 0xFFFFFF, "cinza": 0x95A5A6, "dourado": 0xD4AF37, "ciano": 0x06B6D4,
}


def parse_color(text: Optional[str], default: Optional[int] = None) -> Optional[int]:
    if text is None or not str(text).strip():
        return default
    t = str(text).strip().lower()
    if t in COLOR_NAMES:
        return COLOR_NAMES[t]
    t = t.lstrip("#")
    if t.startswith("0x"):
        t = t[2:]
    if re.fullmatch(r"[0-9a-f]{6}", t):
        return int(t, 16)
    if re.fullmatch(r"[0-9a-f]{3}", t):
        return int("".join(c * 2 for c in t), 16)
    raise UserError("Cor inválida. Use um código hexadecimal (ex.: `#FFD700`) ou um nome "
                    "(azul, verde, vermelho, amarelo, roxo, laranja, rosa, dourado...).",
                    "Cor inválida")


def parse_date_br(text: str, gid: int) -> str:
    t = (text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try:
            datetime.strptime(t, "%Y-%m-%d")
            return t
        except ValueError:
            pass
    t = t.replace("-", "/").replace(".", "/")
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?", t)
    if not m:
        raise UserError("Use o formato `dd/mm/aaaa` (ex.: `02/10/2026`).", "Data inválida")
    day, month, y = int(m.group(1)), int(m.group(2)), m.group(3)
    year = local_now(gid).year if not y else (int(y) + 2000 if len(y) == 2 else int(y))
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        raise UserError("Essa data não existe no calendário.", "Data inválida")


def parse_time_br(text: str) -> str:
    t = (text or "").strip().lower().replace(" ", "").replace("h", ":")
    if t.endswith(":"):
        t += "00"
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", t)
    if not m:
        raise UserError("Use o formato `HH:MM` (ex.: `20:00` ou `20h30`).", "Horário inválido")
    hh, mm = int(m.group(1)), int(m.group(2) or 0)
    if hh > 23 or mm > 59:
        raise UserError("Esse horário não existe.", "Horário inválido")
    return f"{hh:02d}:{mm:02d}"


def parse_datetime_br(text: str, gid: int) -> tuple:
    """'02/10/2026 20:00' -> ('2026-10-02', '20:00'). O horário é opcional."""
    cleaned = re.sub(r"\b(às|as|ás|-|,)\b", " ", (text or "").replace(",", " "), flags=re.I)
    parts = cleaned.split()
    if not parts:
        raise UserError("Informe a data e o horário. Ex.: `02/10/2026 20:00`.", "Data inválida")
    date_iso = parse_date_br(parts[0], gid)
    time_str = parse_time_br(parts[1]) if len(parts) > 1 else ""
    return date_iso, time_str


def normalize_position(text: Optional[str]) -> Optional[str]:
    t = (text or "").strip().upper().replace(".", "")
    if t in POSITION_NAMES:
        return t
    return POSITION_ALIASES.get(t)


def calc_winrate(wins: int, draws: int, games: int) -> float:
    return ((wins * 3 + draws) / (games * 3) * 100) if games else 0.0


# ----- Embeds padronizados -------------------------------------------------------

def accent_color(gid: Optional[int]) -> int:
    if gid is None:
        return 0x3B82F6
    return parse_color(cfg_get(gid, "color"), 0x3B82F6) or 0x3B82F6


def make_embed(gid: Optional[int], title: Optional[str] = None, description: Optional[str] = None,
               color: Optional[int] = None, footer: bool = True) -> discord.Embed:
    emb = discord.Embed(title=trunc(title, 256) if title else None,
                        description=trunc(description, 4000) if description else None,
                        color=color if color is not None else accent_color(gid))
    if footer and gid is not None:
        text = cfg_get(gid, "footer").strip() or team_name_of(gid)
        emb.set_footer(text=trunc(text, 200))
    return emb


def success_embed(gid: Optional[int], title: str, description: str = "") -> discord.Embed:
    return make_embed(gid, f"✅ {title}", description, SUCCESS_COLOR)


def error_embed(gid: Optional[int], title: str, description: str = "") -> discord.Embed:
    return make_embed(gid, f"⛔ {title}", description, ERROR_COLOR)


def warn_embed(gid: Optional[int], title: str, description: str = "") -> discord.Embed:
    return make_embed(gid, f"⚠️ {title}", description, WARN_COLOR)


def info_embed(gid: Optional[int], title: str, description: str = "") -> discord.Embed:
    return make_embed(gid, title, description)


# ----- Permissões ------------------------------------------------------------------

def is_staff(user: Any) -> bool:
    """Administrador do servidor, dono, ou quem tem o cargo de administrador configurado."""
    if not isinstance(user, discord.Member):
        return False
    if user.guild.owner_id == user.id or user.guild_permissions.administrator:
        return True
    rid = cfg_int(user.guild.id, "admin_role")
    return bool(rid and any(r.id == rid for r in user.roles))


def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not is_staff(interaction.user):
            raise NotStaff()
        return True
    return app_commands.check(predicate)


def require_staff(interaction: discord.Interaction) -> None:
    """Verificação no backend (não confia apenas nos botões)."""
    if interaction.guild is None or not is_staff(interaction.user):
        raise UserError("Apenas administradores do time podem fazer isso.", "Sem permissão")


# ----- Respostas de interação ----------------------------------------------------

_MISSING = discord.utils.MISSING


async def respond(interaction: discord.Interaction, *, content: Optional[str] = None,
                  embed: Optional[discord.Embed] = None, embeds: Optional[list] = None,
                  view: Optional[discord.ui.View] = None, file: Optional[discord.File] = None,
                  ephemeral: bool = True, allowed_mentions: Optional[discord.AllowedMentions] = None):
    kwargs: dict = {"ephemeral": ephemeral}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if embeds is not None:
        kwargs["embeds"] = embeds
    if view is not None:
        kwargs["view"] = view
    if file is not None:
        kwargs["file"] = file
    if allowed_mentions is not None:
        kwargs["allowed_mentions"] = allowed_mentions
    if interaction.response.is_done():
        return await interaction.followup.send(**kwargs)
    await interaction.response.send_message(**kwargs)
    return None


async def edit_message(interaction: discord.Interaction, *, content: Any = _MISSING,
                       embed: Any = _MISSING, embeds: Any = _MISSING, view: Any = _MISSING,
                       attachments: Any = _MISSING):
    kwargs = {}
    for k, v in (("content", content), ("embed", embed), ("embeds", embeds),
                 ("view", view), ("attachments", attachments)):
        if v is not _MISSING:
            kwargs[k] = v
    if interaction.response.is_done():
        return await interaction.edit_original_response(**kwargs)
    return await interaction.response.edit_message(**kwargs)


async def handle_error(interaction: discord.Interaction, error: BaseException) -> None:
    """Tratamento central de erros: mensagens bonitas + registro nos logs."""
    original = getattr(error, "original", error)
    gid = interaction.guild_id
    if isinstance(original, UserError):
        embed = error_embed(gid, original.title, original.message)
    elif isinstance(error, NotStaff) or isinstance(original, NotStaff):
        embed = error_embed(gid, "Sem permissão",
                            "Este comando é exclusivo da administração do time. "
                            "Peça a um administrador ou configure o cargo em `/config`.")
    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = warn_embed(gid, "Calma aí!", f"Tente novamente em **{error.retry_after:.1f}s**.")
    elif isinstance(error, app_commands.NoPrivateMessage):
        embed = error_embed(gid, "Apenas em servidores", "Use este comando dentro de um servidor.")
    elif isinstance(original, discord.Forbidden):
        embed = error_embed(gid, "Permissão do bot insuficiente",
                            "O bot não tem permissão para fazer isso neste canal. "
                            "Verifique as permissões (Enviar mensagens, Inserir links, Anexar arquivos).")
    elif isinstance(original, discord.NotFound):
        return
    else:
        code = uuid.uuid4().hex[:8].upper()
        tb = "".join(traceback.format_exception(type(original), original, original.__traceback__))
        log.error("Erro inesperado [%s]: %s", code, tb)
        try:
            db_exec("INSERT INTO logs (guild_id, user_id, category, action, details, before_data, after_data, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (gid, getattr(interaction.user, "id", None), "Erro", f"Erro {code}",
                     trunc(tb, 3500), "", "", now_utc_iso()))
        except Exception:
            pass
        embed = error_embed(gid, "Algo deu errado",
                            f"Ocorreu um erro inesperado e ele foi registrado.\nCódigo do erro: `{code}`")
    try:
        await respond(interaction, embed=embed, ephemeral=True)
    except Exception:
        pass


# ----- Views/Modals base --------------------------------------------------------

class SafeView(discord.ui.View):
    """View com verificação de dono, permissão de staff e tratamento de erros."""

    def __init__(self, *, owner_id: Optional[int] = None, staff_only: bool = False,
                 timeout: Optional[float] = 300):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.staff_required = staff_only
        self._origin: Optional[discord.Interaction] = None

    def bind(self, interaction: discord.Interaction) -> "SafeView":
        self._origin = interaction
        return self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        gid = interaction.guild_id
        if self.owner_id and interaction.user.id != self.owner_id:
            await respond(interaction, embed=warn_embed(
                gid, "Este painel não é seu", "Execute o comando você mesmo para ter o seu painel."))
            return False
        if self.staff_required and not is_staff(interaction.user):
            await respond(interaction, embed=error_embed(
                gid, "Sem permissão", "Apenas administradores do time podem usar este painel."))
            return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        await handle_error(interaction, error)

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self._origin is not None:
            try:
                await self._origin.edit_original_response(view=self)
            except Exception:
                pass


class SafeModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await handle_error(interaction, error)


async def switch_view(interaction: discord.Interaction, old: Optional[discord.ui.View], *,
                      embed: Any = _MISSING, embeds: Any = _MISSING, content: Any = _MISSING,
                      view: Any = _MISSING) -> None:
    """Troca a view de uma mensagem encerrando a anterior (evita timeouts que sobrescrevem)."""
    if old is not None:
        old.stop()
    if isinstance(view, SafeView):
        view.bind(interaction)
    await edit_message(interaction, embed=embed, embeds=embeds, content=content, view=view)


class PagedView(SafeView):
    """Paginação genérica por botões para listas de embeds."""

    def __init__(self, pages: list, owner_id: Optional[int], *, timeout: float = 300):
        super().__init__(owner_id=owner_id, timeout=timeout)
        self.pages = pages or [discord.Embed(description="Nada para mostrar.")]
        self.index = 0
        if len(self.pages) <= 1:
            self.clear_items()
        else:
            self._sync()

    def current(self) -> discord.Embed:
        emb = self.pages[self.index].copy()
        base = emb.footer.text if emb.footer and emb.footer.text else ""
        tag = f"Página {self.index + 1}/{len(self.pages)}"
        emb.set_footer(text=f"{base} • {tag}" if base else tag)
        return emb

    def _sync(self) -> None:
        last = len(self.pages) - 1
        self.btn_first.disabled = self.btn_prev.disabled = self.index == 0
        self.btn_next.disabled = self.btn_last.disabled = self.index == last
        self.btn_label.label = f"{self.index + 1}/{len(self.pages)}"

    async def _go(self, interaction: discord.Interaction, index: int) -> None:
        self.index = max(0, min(len(self.pages) - 1, index))
        self._sync()
        await interaction.response.edit_message(embed=self.current(), view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_first(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, 0)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, self.index - 1)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def btn_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=0)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, self.index + 1)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, len(self.pages) - 1)


async def send_paged(interaction: discord.Interaction, pages: list, *, ephemeral: bool = False) -> None:
    view = PagedView(pages, interaction.user.id)
    emb = view.current()
    if len(view.pages) <= 1:
        await respond(interaction, embed=emb, ephemeral=ephemeral)
        return
    await respond(interaction, embed=emb, view=view, ephemeral=ephemeral)
    view.bind(interaction)


class UserPickView(SafeView):
    """Mostra um seletor de usuário e chama `callback(interaction, user)`."""

    def __init__(self, owner_id: int, callback: Callable[[discord.Interaction, discord.abc.User], Awaitable[None]],
                 *, placeholder: str = "Selecione o jogador", staff_only: bool = True):
        super().__init__(owner_id=owner_id, staff_only=staff_only, timeout=300)
        select = discord.ui.UserSelect(placeholder=placeholder, min_values=1, max_values=1)

        async def _cb(interaction: discord.Interaction):
            self._origin = None
            await callback(interaction, select.values[0])

        select.callback = _cb
        self.add_item(select)


class ConfirmView(SafeView):
    """Confirmação (sim/não) para ações destrutivas."""

    def __init__(self, owner_id: int, on_confirm: Callable[[discord.Interaction], Awaitable[None]],
                 *, confirm_label: str = "Confirmar", staff_only: bool = True):
        super().__init__(owner_id=owner_id, staff_only=staff_only, timeout=120)
        self._on_confirm = on_confirm
        self._done = False
        self.btn_ok.label = confirm_label

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger, emoji="✅")
    async def btn_ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._done:
            await respond(interaction, embed=warn_embed(interaction.guild_id, "Já processado"))
            return
        self._done = True
        self.stop()
        await self._on_confirm(interaction)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._done = True
        self.stop()
        await interaction.response.edit_message(
            embed=info_embed(interaction.guild_id, "Ação cancelada", "Nada foi alterado."), view=None)


def add_button(view: discord.ui.View, label: Optional[str], callback: Callable, *,
               style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: Optional[str] = None,
               row: Optional[int] = None, disabled: bool = False) -> discord.ui.Button:
    btn = discord.ui.Button(label=label, style=style, emoji=emoji, row=row, disabled=disabled)
    btn.callback = callback
    view.add_item(btn)
    return btn


def mention_list(user_ids: list, limit: int = 30) -> str:
    if not user_ids:
        return "—"
    shown = [f"<@{u}>" for u in user_ids[:limit]]
    extra = len(user_ids) - len(shown)
    text = " ".join(shown)
    return text + (f" +{extra}" if extra > 0 else "")


# ----- Cliente do bot ------------------------------------------------------------

class MPSBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        # Views persistentes (continuam funcionando depois de reiniciar o bot).
        self.add_view(PresencaView())
        self.add_view(TimePanelView())
        try:
            if GUILD_DE_TESTE:
                guild = discord.Object(id=GUILD_DE_TESTE)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            log.info("%d comandos slash sincronizados.", len(synced))
        except Exception:
            log.exception("Falha ao sincronizar os comandos slash.")


bot = MPSBot()
tree = bot.tree


# ==============================
# LOGS
# ==============================

def unix_ts(created_at: Optional[str]) -> int:
    try:
        return int(datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except (TypeError, ValueError):
        return int(datetime.now(timezone.utc).timestamp())


async def log_event(gid: Optional[int], actor_id: Optional[int], category: str, action: str, *,
                    before: str = "", after: str = "", details: str = "") -> None:
    """Grava o log no banco e, se configurado, envia ao canal de logs."""
    created = now_utc_iso()
    try:
        db_exec("INSERT INTO logs (guild_id, user_id, category, action, details, before_data, after_data, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (gid, actor_id, category, action, trunc(details, 1500), trunc(before, 1500),
                 trunc(after, 1500), created))
    except Exception:
        log.exception("Falha ao gravar log.")
        return
    if gid is None:
        return
    channel_id = cfg_int(gid, "log_channel")
    guild = bot.get_guild(gid)
    if not channel_id or guild is None:
        return
    channel = guild.get_channel(channel_id)
    if channel is None or not hasattr(channel, "send"):
        return
    emb = make_embed(gid, f"📜 {category} • {action}", color=NEUTRAL_COLOR)
    emb.add_field(name="Quem fez", value=f"<@{actor_id}>" if actor_id else "Sistema", inline=True)
    emb.add_field(name="Quando", value=f"<t:{unix_ts(created)}:F>", inline=True)
    if details:
        emb.add_field(name="Detalhes", value=trunc(details, 1000), inline=False)
    if before:
        emb.add_field(name="Dados anteriores", value=trunc(before, 1000), inline=True)
    if after:
        emb.add_field(name="Dados novos", value=trunc(after, 1000), inline=True)
    try:
        await channel.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())
    except Exception:
        log.warning("Não consegui enviar o log para o canal %s.", channel_id)


def build_log_pages(gid: int, limit: int = 120) -> list:
    rows = db_all("SELECT * FROM logs WHERE guild_id=? ORDER BY id DESC LIMIT ?", (gid, limit))
    if not rows:
        return [info_embed(gid, "📜 Registro de atividades", "Nenhuma atividade registrada ainda.")]
    pages = []
    groups = chunk(rows, 6)
    for group in groups:
        lines = []
        for r in group:
            who = f"<@{r['user_id']}>" if r["user_id"] else "Sistema"
            line = f"**{r['category']} • {r['action']}** — {who} — <t:{unix_ts(r['created_at'])}:R>"
            if r["before_data"] or r["after_data"]:
                line += f"\n└ `{trunc(r['before_data'] or '—', 70)}` ➜ `{trunc(r['after_data'] or '—', 70)}`"
            elif r["details"]:
                line += f"\n└ {trunc(r['details'], 110)}"
            lines.append(line)
        pages.append(info_embed(gid, "📜 Registro de atividades", "\n\n".join(lines)))
    return pages


# ==============================
# SISTEMA DE JOGADORES
# ==============================

def get_player(gid: int, user_id: int):
    return db_one("SELECT * FROM players WHERE guild_id=? AND user_id=?", (gid, user_id))


def get_player_by_id(pid: int):
    return db_one("SELECT * FROM players WHERE id=?", (pid,))


def require_player(gid: int, user_id: int, *, allow_inactive: bool = True):
    row = get_player(gid, user_id)
    if row is None:
        raise UserError(f"<@{user_id}> não está cadastrado no elenco. "
                        f"Cadastre com `/jogador adicionar` primeiro.", "Jogador não encontrado")
    if not allow_inactive and row["status"] == "inativo":
        raise UserError(f"**{row['name']}** está inativo. Reative-o com `/jogador editar` (status: ativo).",
                        "Jogador inativo")
    return row


def normalize_status(text: Optional[str]) -> str:
    t = (text or "").strip().lower()
    aliases = {"active": "ativo", "reserve": "reserva", "suspended": "suspenso", "inactive": "inativo"}
    t = aliases.get(t, t)
    if t not in STATUS_LABELS:
        raise UserError("Status inválido. Use: **ativo**, **reserva**, **suspenso** ou **inativo**.",
                        "Status inválido")
    return t


def validate_player_name(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    if not (2 <= len(n) <= 32):
        raise UserError("O nome do jogador precisa ter entre 2 e 32 caracteres.", "Nome inválido")
    return n


def validate_number(value: Any) -> int:
    try:
        n = int(str(value).strip().lstrip("#"))
    except (TypeError, ValueError):
        raise UserError("O número da camisa deve ser um número inteiro entre 0 e 99.", "Número inválido")
    if not (0 <= n <= 99):
        raise UserError("O número da camisa deve estar entre 0 e 99.", "Número inválido")
    return n


def number_conflict(gid: int, number: int, exclude_player_id: Optional[int] = None):
    return db_one("SELECT * FROM players WHERE guild_id=? AND number=? AND status!='inativo' AND id!=?",
                  (gid, number, exclude_player_id or -1))


def player_snapshot(row) -> str:
    if row is None:
        return "—"
    return (f"{row['name']} • #{row['number']} • {row['position']} • "
            f"{STATUS_LABELS.get(row['status'], row['status'])}")


def add_player(gid: int, user_id: int, name: str, number: int, position: str, status: str = "ativo"):
    """Cadastra um jogador. Se ele já existir inativo, reativa preservando as estatísticas."""
    name = validate_player_name(name)
    number = validate_number(number)
    position = normalize_position(position)
    if position is None:
        raise UserError("Posição inválida. Use: " + ", ".join(POSITION_NAMES) + ".", "Posição inválida")
    status = normalize_status(status)
    existing = get_player(gid, user_id)
    if existing is not None and existing["status"] != "inativo":
        raise UserError(f"**{existing['name']}** já está no elenco. Use `/jogador editar` para alterar os dados.",
                        "Jogador já cadastrado")
    if status != "inativo":
        clash = number_conflict(gid, number, existing["id"] if existing else None)
        if clash is not None:
            raise UserError(f"O número **{number}** já é usado por **{clash['name']}**. "
                            f"Escolha outro número.", "Número em uso")
    now = now_utc_iso()
    if existing is not None:
        db_exec("UPDATE players SET name=?, number=?, position=?, status=?, updated_at=? WHERE id=?",
                (name, number, position, status, now, existing["id"]))
        row = get_player_by_id(existing["id"])
        return row, True
    pid = db_exec("INSERT INTO players (guild_id, user_id, name, number, position, status, joined_at, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?)", (gid, user_id, name, number, position, status, now, now))
    refresh_player_stats(gid, [pid])
    return get_player_by_id(pid), False


def edit_player(gid: int, user_id: int, *, name: Optional[str] = None, number: Any = None,
                position: Optional[str] = None, status: Optional[str] = None):
    before = require_player(gid, user_id)
    new_name = validate_player_name(name) if name is not None else before["name"]
    new_number = validate_number(number) if number is not None else before["number"]
    if position is not None:
        new_pos = normalize_position(position)
        if new_pos is None:
            raise UserError("Posição inválida. Use: " + ", ".join(POSITION_NAMES) + ".", "Posição inválida")
    else:
        new_pos = before["position"]
    new_status = normalize_status(status) if status is not None else before["status"]
    if new_status != "inativo":
        clash = number_conflict(gid, new_number, before["id"])
        if clash is not None:
            raise UserError(f"O número **{new_number}** já é usado por **{clash['name']}**.", "Número em uso")
    with db_tx() as c:
        c.execute("UPDATE players SET name=?, number=?, position=?, status=?, updated_at=? WHERE id=?",
                  (new_name, new_number, new_pos, new_status, now_utc_iso(), before["id"]))
        if new_status in ("suspenso", "inativo"):
            c.execute("DELETE FROM lineups WHERE guild_id=? AND player_id=?", (gid, before["id"]))
    return before, get_player_by_id(before["id"])


def remove_player(gid: int, user_id: int):
    """Remover = marcar como inativo. Estatísticas e histórico são preservados."""
    before = require_player(gid, user_id)
    if before["status"] == "inativo":
        raise UserError(f"**{before['name']}** já está inativo.", "Jogador já inativo")
    with db_tx() as c:
        c.execute("UPDATE players SET status='inativo', updated_at=? WHERE id=?", (now_utc_iso(), before["id"]))
        c.execute("DELETE FROM lineups WHERE guild_id=? AND player_id=?", (gid, before["id"]))
    return before, get_player_by_id(before["id"])


def list_players(gid: int, status: Optional[str] = None, include_inactive: bool = True) -> list:
    if status:
        return db_all("SELECT * FROM players WHERE guild_id=? AND status=? ORDER BY number, name", (gid, status))
    if include_inactive:
        return db_all("SELECT * FROM players WHERE guild_id=? ORDER BY CASE status WHEN 'ativo' THEN 0 "
                      "WHEN 'reserva' THEN 1 WHEN 'suspenso' THEN 2 ELSE 3 END, number, name", (gid,))
    return db_all("SELECT * FROM players WHERE guild_id=? AND status!='inativo' ORDER BY number, name", (gid,))


def build_roster_pages(gid: int, status: Optional[str] = None) -> list:
    players = list_players(gid, status)
    title = "👥 Elenco" + (f" • {STATUS_LABELS[status]}" if status else "")
    if not players:
        return [info_embed(gid, title, "Nenhum jogador cadastrado ainda.\nUse `/jogador adicionar` para começar.")]
    pages = []
    for group in chunk(players, 12):
        lines = []
        for p in group:
            st = stats_row(gid, p["id"])
            lines.append(f"`#{p['number']:>2}` **{p['name']}** • {p['position']} • "
                         f"Rank **{st['rank']}** • {STATUS_LABELS[p['status']]}")
        pages.append(info_embed(gid, title, "\n".join(lines)))
    return pages


class PlayerModal(SafeModal):
    """Cadastro/edição de jogador (usado pelo painel administrativo)."""

    def __init__(self, gid: int, target: discord.abc.User, existing=None):
        super().__init__(title="Editar jogador" if existing else "Adicionar jogador", timeout=600)
        self.target = target
        self.existing = existing
        self.f_name = discord.ui.TextInput(label="Nome", max_length=32, min_length=2,
                                           default=existing["name"] if existing else getattr(target, "display_name", target.name)[:32])
        self.f_number = discord.ui.TextInput(label="Número da camisa (0-99)", max_length=2,
                                             default=str(existing["number"]) if existing else None)
        self.f_pos = discord.ui.TextInput(label="Posição (GOL, ZAG, LD, LE, VOL...)", max_length=5,
                                          default=existing["position"] if existing else "ATA")
        self.f_status = discord.ui.TextInput(label="Status (ativo/reserva/suspenso/inativo)", max_length=10,
                                             default=existing["status"] if existing else "ativo")
        for item in (self.f_name, self.f_number, self.f_pos, self.f_status):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        if self.existing:
            before, after = edit_player(gid, self.target.id, name=self.f_name.value, number=self.f_number.value,
                                        position=self.f_pos.value, status=self.f_status.value)
            await log_event(gid, interaction.user.id, "Jogadores", "Jogador editado",
                            before=player_snapshot(before), after=player_snapshot(after))
            emb = success_embed(gid, "Jogador atualizado", f"<@{self.target.id}> foi atualizado.")
            emb.add_field(name="Antes", value=player_snapshot(before), inline=False)
            emb.add_field(name="Agora", value=player_snapshot(after), inline=False)
        else:
            row, reactivated = add_player(gid, self.target.id, self.f_name.value, self.f_number.value,
                                          self.f_pos.value, self.f_status.value)
            await log_event(gid, interaction.user.id, "Jogadores",
                            "Jogador reativado" if reactivated else "Jogador adicionado", after=player_snapshot(row))
            emb = success_embed(gid, "Jogador reativado" if reactivated else "Jogador cadastrado",
                                f"<@{self.target.id}> agora faz parte do elenco.")
            emb.add_field(name="Ficha", value=player_snapshot(row), inline=False)
        await respond(interaction, embed=emb)


# ----- Comandos /jogador --------------------------------------------------------------

POSITION_CHOICES = [app_commands.Choice(name=f"{k} — {v}", value=k) for k, v in POSITION_NAMES.items()]
STATUS_CHOICES = [app_commands.Choice(name=v.split(" ", 1)[1], value=k) for k, v in STATUS_LABELS.items()]

jogador_group = app_commands.Group(name="jogador", description="Gerencia o elenco do time", guild_only=True)


@jogador_group.command(name="adicionar", description="Cadastra um jogador no elenco (administração).")
@app_commands.describe(usuario="Usuário do Discord", numero="Número da camisa (0-99)", posicao="Posição em campo",
                       nome="Nome do jogador (padrão: apelido no servidor)", status="Status do jogador")
@app_commands.choices(posicao=POSITION_CHOICES, status=STATUS_CHOICES)
@staff_only()
async def jogador_adicionar(interaction: discord.Interaction, usuario: discord.Member, numero: app_commands.Range[int, 0, 99],
                            posicao: app_commands.Choice[str], nome: Optional[app_commands.Range[str, 2, 32]] = None,
                            status: Optional[app_commands.Choice[str]] = None):
    gid = interaction.guild_id
    row, reactivated = add_player(gid, usuario.id, nome or usuario.display_name[:32], numero, posicao.value,
                                  status.value if status else "ativo")
    await log_event(gid, interaction.user.id, "Jogadores", "Jogador reativado" if reactivated else "Jogador adicionado",
                    after=player_snapshot(row))
    emb = success_embed(gid, "Jogador reativado" if reactivated else "Jogador cadastrado",
                        f"{usuario.mention} agora faz parte do elenco." +
                        ("\nAs estatísticas anteriores foram preservadas." if reactivated else ""))
    emb.set_thumbnail(url=usuario.display_avatar.url)
    emb.add_field(name="Nome", value=row["name"], inline=True)
    emb.add_field(name="Camisa", value=f"#{row['number']}", inline=True)
    emb.add_field(name="Posição", value=f"{row['position']} ({POSITION_NAMES[row['position']]})", inline=True)
    emb.add_field(name="Status", value=STATUS_LABELS[row["status"]], inline=True)
    await respond(interaction, embed=emb)


@jogador_group.command(name="editar", description="Edita os dados de um jogador (administração).")
@app_commands.describe(usuario="Jogador a editar", nome="Novo nome", numero="Novo número da camisa",
                       posicao="Nova posição", status="Novo status")
@app_commands.choices(posicao=POSITION_CHOICES, status=STATUS_CHOICES)
@staff_only()
async def jogador_editar(interaction: discord.Interaction, usuario: discord.Member,
                         nome: Optional[app_commands.Range[str, 2, 32]] = None,
                         numero: Optional[app_commands.Range[int, 0, 99]] = None,
                         posicao: Optional[app_commands.Choice[str]] = None,
                         status: Optional[app_commands.Choice[str]] = None):
    gid = interaction.guild_id
    if nome is None and numero is None and posicao is None and status is None:
        raise UserError("Informe pelo menos um campo para alterar (nome, número, posição ou status).",
                        "Nada para editar")
    before, after = edit_player(gid, usuario.id, name=nome, number=numero,
                                position=posicao.value if posicao else None, status=status.value if status else None)
    await log_event(gid, interaction.user.id, "Jogadores", "Jogador editado",
                    before=player_snapshot(before), after=player_snapshot(after))
    emb = success_embed(gid, "Jogador atualizado", f"Os dados de {usuario.mention} foram atualizados.")
    emb.add_field(name="Antes", value=player_snapshot(before), inline=False)
    emb.add_field(name="Agora", value=player_snapshot(after), inline=False)
    await respond(interaction, embed=emb)


@jogador_group.command(name="remover", description="Remove um jogador do elenco (vira inativo, mantém o histórico).")
@app_commands.describe(usuario="Jogador a remover")
@staff_only()
async def jogador_remover(interaction: discord.Interaction, usuario: discord.Member):
    gid = interaction.guild_id
    before, after = remove_player(gid, usuario.id)
    await log_event(gid, interaction.user.id, "Jogadores", "Jogador removido (inativo)",
                    before=player_snapshot(before), after=player_snapshot(after))
    await respond(interaction, embed=success_embed(
        gid, "Jogador removido do elenco",
        f"**{before['name']}** foi marcado como **inativo**.\n"
        f"Todas as estatísticas e o histórico de partidas foram preservados."))


@jogador_group.command(name="listar", description="Lista os jogadores do elenco.")
@app_commands.describe(status="Filtrar por status")
@app_commands.choices(status=STATUS_CHOICES)
async def jogador_listar(interaction: discord.Interaction, status: Optional[app_commands.Choice[str]] = None):
    pages = build_roster_pages(interaction.guild_id, status.value if status else None)
    await send_paged(interaction, pages)


tree.add_command(jogador_group)


# ==============================
# SISTEMA DE RANK
# ==============================

STATS_SQL = """
SELECT p.id AS pid, p.name, p.rank_override,
  COALESCE((SELECT SUM(amount) FROM goals    WHERE player_id=p.id), 0) AS goals,
  COALESCE((SELECT SUM(amount) FROM assists  WHERE player_id=p.id), 0) AS assists,
  COALESCE((SELECT SUM(amount) FROM mvps     WHERE player_id=p.id), 0) AS mvps,
  (SELECT COUNT(*) FROM match_players mp WHERE mp.player_id=p.id) AS games,
  (SELECT COUNT(*) FROM match_players mp JOIN matches m ON m.id=mp.match_id
     WHERE mp.player_id=p.id AND m.result='V') AS wins,
  (SELECT COUNT(*) FROM match_players mp JOIN matches m ON m.id=mp.match_id
     WHERE mp.player_id=p.id AND m.result='E') AS draws,
  (SELECT COUNT(*) FROM match_players mp JOIN matches m ON m.id=mp.match_id
     WHERE mp.player_id=p.id AND m.result='D') AS losses
FROM players p WHERE p.guild_id=?
"""


def rank_weights(gid: int) -> dict:
    return {"goals": cfg_float(gid, "w_goal", 3), "assists": cfg_float(gid, "w_assist", 2),
            "wins": cfg_float(gid, "w_win", 3), "mvps": cfg_float(gid, "w_mvp", 10)}


def rank_thresholds(gid: int) -> dict:
    return {r: cfg_float(gid, f"rank_{r.lower()}", float(DEFAULT_CONFIG[f"rank_{r.lower()}"])) for r in RANKS}


def calc_score(stats: dict, weights: dict) -> float:
    return round(stats["goals"] * weights["goals"] + stats["assists"] * weights["assists"]
                 + stats["wins"] * weights["wins"] + stats["mvps"] * weights["mvps"], 2)


def rank_for_score(score: float, thresholds: dict) -> str:
    for r in reversed(RANKS):
        if score >= thresholds[r]:
            return r
    return "D"


def refresh_player_stats(gid: int, player_ids: Optional[list] = None) -> list:
    """Recalcula estatísticas, pontuação e Rank a partir do histórico (ledger).
    Retorna a lista de mudanças de Rank [{name, old, new, score}]."""
    weights, thresholds = rank_weights(gid), rank_thresholds(gid)
    rows = db_all(STATS_SQL, (gid,))
    if player_ids is not None:
        wanted = set(player_ids)
        rows = [r for r in rows if r["pid"] in wanted]
    changes = []
    now = now_utc_iso()
    with db_tx() as c:
        for r in rows:
            st = {k: max(0, r[k]) for k in ("goals", "assists", "mvps", "games", "wins", "draws", "losses")}
            score = calc_score(st, weights)
            rank = r["rank_override"] if r["rank_override"] in RANKS else rank_for_score(score, thresholds)
            old = c.execute("SELECT rank FROM player_stats WHERE guild_id=? AND player_id=?", (gid, r["pid"])).fetchone()
            c.execute(
                "INSERT INTO player_stats (guild_id, player_id, games, wins, draws, losses, goals, assists, mvps, score, rank, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(guild_id, player_id) DO UPDATE SET "
                "games=excluded.games, wins=excluded.wins, draws=excluded.draws, losses=excluded.losses, "
                "goals=excluded.goals, assists=excluded.assists, mvps=excluded.mvps, score=excluded.score, "
                "rank=excluded.rank, updated_at=excluded.updated_at",
                (gid, r["pid"], st["games"], st["wins"], st["draws"], st["losses"], st["goals"], st["assists"],
                 st["mvps"], score, rank, now))
            if old is not None and old["rank"] != rank:
                changes.append({"pid": r["pid"], "name": r["name"], "old": old["rank"], "new": rank, "score": score})
    return changes


def stats_row(gid: int, pid: int) -> dict:
    """Estatísticas + derivadas (calculadas automaticamente)."""
    row = db_one("SELECT * FROM player_stats WHERE guild_id=? AND player_id=?", (gid, pid))
    if row is None:
        refresh_player_stats(gid, [pid])
        row = db_one("SELECT * FROM player_stats WHERE guild_id=? AND player_id=?", (gid, pid))
    d = dict(row)
    g = d["games"]
    d["gpg"] = d["goals"] / g if g else 0.0
    d["apg"] = d["assists"] / g if g else 0.0
    d["participations"] = d["goals"] + d["assists"]
    d["winrate"] = calc_winrate(d["wins"], d["draws"], g)
    return d


# ----- Conquistas ------------------------------------------------------------------------

def get_metrics(gid: int, pid: int) -> dict:
    st = stats_row(gid, pid)
    results = [r["result"] for r in db_all(
        "SELECT m.result FROM match_players mp JOIN matches m ON m.id=mp.match_id "
        "WHERE mp.player_id=? ORDER BY m.played_date, m.id", (pid,))]
    best, cur = 0, 0
    for res in results:
        cur = cur + 1 if res == "V" else 0
        best = max(best, cur)
    row = db_one("SELECT MAX(s) AS best FROM (SELECT SUM(amount) AS s FROM goals WHERE player_id=? "
                 "AND match_id IS NOT NULL GROUP BY match_id)", (pid,))
    return {"goals": st["goals"], "assists": st["assists"], "mvps": st["mvps"], "wins": st["wins"],
            "games": st["games"], "streak": best, "best_match_goals": (row["best"] or 0) if row else 0}


def sync_achievements(gid: int, pid: int) -> list:
    """Concede conquistas atingidas e revoga as que não são mais válidas. Retorna as novas."""
    metrics = get_metrics(gid, pid)
    have = {r["code"] for r in db_all("SELECT code FROM achievements WHERE guild_id=? AND player_id=?", (gid, pid))}
    new = []
    with db_tx() as c:
        for code, emoji, name, desc, metric, target in ACHIEVEMENTS:
            ok = metrics.get(metric, 0) >= target
            if ok and code not in have:
                c.execute("INSERT OR IGNORE INTO achievements (guild_id, player_id, code, unlocked_at) VALUES (?,?,?,?)",
                          (gid, pid, code, now_utc_iso()))
                new.append((code, emoji, name, desc, metric, target))
            elif not ok and code in have:
                c.execute("DELETE FROM achievements WHERE guild_id=? AND player_id=? AND code=?", (gid, pid, code))
    return new


async def after_stats_change(gid: int, player_ids: list, actor_id: Optional[int], reason: str = "") -> tuple:
    """Recalcula Rank/conquistas após qualquer alteração e registra nos logs."""
    changes = refresh_player_stats(gid, player_ids)
    unlocked = {}
    for pid in player_ids:
        new = sync_achievements(gid, pid)
        if new:
            unlocked[pid] = new
    for ch in changes:
        await log_event(gid, actor_id, "Rank", "Alteração de Rank", before=f"{ch['name']}: Rank {ch['old']}",
                        after=f"{ch['name']}: Rank {ch['new']} ({fmt_num(ch['score'])} pts)", details=reason)
    for pid, lst in unlocked.items():
        p = get_player_by_id(pid)
        await log_event(gid, actor_id, "Conquistas", "Conquista desbloqueada",
                        details=f"{p['name'] if p else pid}: " + ", ".join(f"{a[1]} {a[2]}" for a in lst))
    return changes, unlocked


def describe_unlocks(unlocked: dict) -> str:
    lines = []
    for pid, lst in unlocked.items():
        p = get_player_by_id(pid)
        lines.append(f"**{p['name'] if p else pid}**: " + ", ".join(f"{a[1]} {a[2]}" for a in lst))
    return "\n".join(lines)


# ----- Ranking (individual dos jogadores) ----------------------------------------------

RANK_KINDS = {
    "geral": ("Geral (pontuação)", "score"),
    "gols": ("Artilharia (gols)", "goals"),
    "assistencias": ("Assistências", "assists"),
    "vitorias": ("Vitórias", "wins"),
    "mvp": ("MVPs", "mvps"),
}


def ranking_rows(gid: int, kind: str, include_inactive: bool = False) -> list:
    sql = ("SELECT p.id AS pid, p.user_id, p.name, p.number, p.position, p.status, "
           "COALESCE(s.games,0) AS games, COALESCE(s.wins,0) AS wins, COALESCE(s.draws,0) AS draws, "
           "COALESCE(s.losses,0) AS losses, COALESCE(s.goals,0) AS goals, COALESCE(s.assists,0) AS assists, "
           "COALESCE(s.mvps,0) AS mvps, COALESCE(s.score,0) AS score, COALESCE(s.rank,'D') AS rank "
           "FROM players p LEFT JOIN player_stats s ON s.player_id=p.id AND s.guild_id=p.guild_id "
           "WHERE p.guild_id=?")
    if not include_inactive:
        sql += " AND p.status!='inativo'"
    rows = [dict(r) for r in db_all(sql, (gid,))]
    key = RANK_KINDS.get(kind, RANK_KINDS["geral"])[1]
    rows.sort(key=lambda r: (-r[key], -r["score"], -r["goals"], r["name"].lower()))
    return rows


def ranking_line(pos: int, r: dict, kind: str) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"**{pos}.**")
    main = {"geral": f"**{fmt_num(r['score'])} pts**", "gols": f"**{r['goals']} gols**",
            "assistencias": f"**{r['assists']} assist.**", "vitorias": f"**{r['wins']} vitórias**",
            "mvp": f"**{r['mvps']} MVPs**"}[kind]
    return (f"{medal} **{r['name']}** · Rank {RANK_ICONS[r['rank']]} **{r['rank']}** · {fmt_num(r['score'])} pts"
            f"{'' if kind == 'geral' else ' · ' + main}\n"
            f"└ ⚽ {r['goals']} · 🅰️ {r['assists']} · ✅ {r['wins']} · 🏅 {r['mvps']}")


def build_ranking_pages(gid: int, kind: str = "geral", per_page: int = 8) -> list:
    rows = ranking_rows(gid, kind)
    title = f"🏆 Ranking de Jogadores • {RANK_KINDS[kind][0]}"
    if not rows:
        return [info_embed(gid, title, "Nenhum jogador no ranking ainda.\nCadastre jogadores com `/jogador adicionar`.")]
    pages = []
    pos = 1
    for group in chunk(rows, per_page):
        lines = []
        for r in group:
            lines.append(ranking_line(pos, r, kind))
            pos += 1
        emb = info_embed(gid, title, "\n\n".join(lines))
        emb.set_footer(text="Ranking individual • atualizado automaticamente a cada 60 min • inativos ocultos")
        pages.append(emb)
    return pages


class RankingView(SafeView):
    def __init__(self, gid: int, owner_id: int, kind: str):
        super().__init__(owner_id=owner_id, timeout=300)
        self.gid, self.kind, self.index = gid, kind, 0
        self.pages = build_ranking_pages(gid, kind)
        self._build()

    def current(self) -> discord.Embed:
        emb = self.pages[self.index].copy()
        base = emb.footer.text or ""
        emb.set_footer(text=f"{base} • Página {self.index + 1}/{len(self.pages)}" if base
                       else f"Página {self.index + 1}/{len(self.pages)}")
        return emb

    def _build(self) -> None:
        self.clear_items()
        sel = discord.ui.Select(
            placeholder="Filtrar ranking…", row=0,
            options=[discord.SelectOption(label=v[0], value=k, default=(k == self.kind),
                                          emoji={"geral": "🏆", "gols": "⚽", "assistencias": "🅰️",
                                                 "vitorias": "✅", "mvp": "🏅"}[k])
                     for k, v in RANK_KINDS.items()])
        sel.callback = self._on_select
        self.add_item(sel)
        last = len(self.pages) - 1
        if last > 0:
            add_button(self, None, self._prev, emoji="◀️", style=discord.ButtonStyle.primary, row=1,
                       disabled=self.index == 0)
            add_button(self, f"{self.index + 1}/{len(self.pages)}", self._noop, row=1, disabled=True)
            add_button(self, None, self._next, emoji="▶️", style=discord.ButtonStyle.primary, row=1,
                       disabled=self.index == last)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def _on_select(self, interaction: discord.Interaction):
        self.kind = interaction.data["values"][0]
        self.index = 0
        self.pages = build_ranking_pages(self.gid, self.kind)
        self._build()
        await interaction.response.edit_message(embed=self.current(), view=self)

    async def _prev(self, interaction: discord.Interaction):
        self.index = max(0, self.index - 1)
        self._build()
        await interaction.response.edit_message(embed=self.current(), view=self)

    async def _next(self, interaction: discord.Interaction):
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._build()
        await interaction.response.edit_message(embed=self.current(), view=self)


@tree.command(name="ranking", description="Mostra o ranking individual dos jogadores.")
@app_commands.describe(tipo="Tipo de ranking (padrão: geral por pontuação)")
@app_commands.choices(tipo=[app_commands.Choice(name=v[0], value=k) for k, v in RANK_KINDS.items()])
@app_commands.guild_only()
async def cmd_ranking(interaction: discord.Interaction, tipo: Optional[app_commands.Choice[str]] = None):
    view = RankingView(interaction.guild_id, interaction.user.id, tipo.value if tipo else "geral")
    await respond(interaction, embed=view.current(), view=view, ephemeral=False)
    view.bind(interaction)


async def refresh_ranking_board(guild: discord.Guild) -> None:
    """Atualiza (ou cria) a mensagem fixa do ranking no canal configurado."""
    gid = guild.id
    channel_id = cfg_int(gid, "ranking_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None or not hasattr(channel, "send"):
        return
    emb = build_ranking_pages(gid, "geral", per_page=10)[0].copy()
    emb.set_footer(text="Atualizado automaticamente a cada 60 minutos")
    emb.timestamp = datetime.now(timezone.utc)
    msg_id = cfg_int(gid, "ranking_message_id")
    try:
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=emb)
                return
            except discord.NotFound:
                pass
        msg = await channel.send(embed=emb)
        cfg_set(gid, "ranking_message_id", msg.id)
    except (discord.Forbidden, discord.HTTPException):
        log.warning("Sem permissão para atualizar o ranking no canal %s (servidor %s).", channel_id, gid)


@tasks.loop(minutes=60)
async def rank_update_loop():
    """Atualização automática do Rank de todos os jogadores a cada 60 minutos."""
    for guild in list(bot.guilds):
        try:
            changes = refresh_player_stats(guild.id)
            for pid in [r["id"] for r in db_all("SELECT id FROM players WHERE guild_id=?", (guild.id,))]:
                sync_achievements(guild.id, pid)
            for ch in changes:
                await log_event(guild.id, None, "Rank", "Alteração de Rank (automática)",
                                before=f"{ch['name']}: Rank {ch['old']}",
                                after=f"{ch['name']}: Rank {ch['new']} ({fmt_num(ch['score'])} pts)")
            await refresh_ranking_board(guild)
        except Exception:
            log.exception("Falha na atualização horária do Rank (servidor %s).", guild.id)


@rank_update_loop.before_loop
async def _before_rank_loop():
    await bot.wait_until_ready()


# ----- /gol e /assistencia (somente administração) -------------------------------------------

LEDGER_TABLES = {"goals": "goals", "assists": "assists", "mvps": "mvps"}
STAT_LABELS = {"goals": ("⚽", "Gols"), "assists": ("🅰️", "Assistências"), "mvps": ("🏅", "MVPs")}


async def apply_manual_stat(gid: int, actor_id: int, player, stat: str, delta: int) -> dict:
    """Ajuste manual auditável (ledger). Nunca deixa o total ficar negativo."""
    if stat not in LEDGER_TABLES or delta == 0:
        raise UserError("Operação inválida.", "Operação inválida")
    if player["status"] == "inativo":
        raise UserError(f"**{player['name']}** está inativo. Reative-o antes de alterar estatísticas.", "Jogador inativo")
    before = stats_row(gid, player["id"])
    if before[stat] + delta < 0:
        raise UserError(f"**{player['name']}** possui apenas **{before[stat]}** {STAT_LABELS[stat][1].lower()}. "
                        f"Não é possível remover {abs(delta)}.", "Valor inválido")
    db_exec(f"INSERT INTO {LEDGER_TABLES[stat]} (guild_id, player_id, match_id, amount, source, created_by, created_at) "
            f"VALUES (?,?,NULL,?,?,?,?)", (gid, player["id"], delta, "manual", actor_id, now_utc_iso()))
    changes, unlocked = await after_stats_change(gid, [player["id"]], actor_id, "Ajuste manual")
    after = stats_row(gid, player["id"])
    emoji, label = STAT_LABELS[stat]
    await log_event(gid, actor_id, "Estatísticas", f"{label} {'adicionados' if delta > 0 else 'removidos'}",
                    before=f"{player['name']}: {before[stat]} {label.lower()} (Rank {before['rank']})",
                    after=f"{player['name']}: {after[stat]} {label.lower()} (Rank {after['rank']})",
                    details=f"Ajuste de {delta:+d}")
    guild = bot.get_guild(gid)
    if guild:
        await refresh_ranking_board(guild)
    return {"before": before, "after": after, "changes": changes, "unlocked": unlocked}


def manual_stat_embed(gid: int, player, stat: str, delta: int, res: dict) -> discord.Embed:
    emoji, label = STAT_LABELS[stat]
    verb = "adicionado(s)" if delta > 0 else "removido(s)"
    emb = success_embed(gid, f"{label} atualizados",
                        f"{emoji} **{abs(delta)}** {label.lower()} {verb} para **{player['name']}**.")
    b, a = res["before"], res["after"]
    emb.add_field(name=label, value=f"{b[stat]} ➜ **{a[stat]}**", inline=True)
    emb.add_field(name="Pontuação", value=f"{fmt_num(b['score'])} ➜ **{fmt_num(a['score'])}**", inline=True)
    emb.add_field(name="Rank", value=f"{b['rank']} ➜ **{a['rank']}**", inline=True)
    if res["unlocked"]:
        emb.add_field(name="🏆 Conquistas desbloqueadas", value=describe_unlocks(res["unlocked"]), inline=False)
    return emb


def _manual_cooldown_key(i: discord.Interaction):
    return (i.guild_id, i.user.id)


@tree.command(name="gol", description="Adiciona gols a um jogador (administração).")
@app_commands.describe(jogador="Jogador que fez o(s) gol(s)", amount="Quantidade de gols (1 a 10)")
@app_commands.guild_only()
@staff_only()
@app_commands.checks.cooldown(1, 4.0, key=_manual_cooldown_key)
async def cmd_gol(interaction: discord.Interaction, jogador: discord.Member, amount: app_commands.Range[int, 1, 10] = 1):
    gid = interaction.guild_id
    player = require_player(gid, jogador.id)
    res = await apply_manual_stat(gid, interaction.user.id, player, "goals", amount)
    await respond(interaction, embed=manual_stat_embed(gid, player, "goals", amount, res), ephemeral=False)


@tree.command(name="assistencia", description="Adiciona assistências a um jogador (administração).")
@app_commands.describe(jogador="Jogador que deu a(s) assistência(s)", amount="Quantidade de assistências (1 a 10)")
@app_commands.guild_only()
@staff_only()
@app_commands.checks.cooldown(1, 4.0, key=_manual_cooldown_key)
async def cmd_assistencia(interaction: discord.Interaction, jogador: discord.Member,
                          amount: app_commands.Range[int, 1, 10] = 1):
    gid = interaction.guild_id
    player = require_player(gid, jogador.id)
    res = await apply_manual_stat(gid, interaction.user.id, player, "assists", amount)
    await respond(interaction, embed=manual_stat_embed(gid, player, "assists", amount, res), ephemeral=False)


# ==============================
# SISTEMA DE RESULTADOS
# ==============================

RESULT_LABELS = {"V": ("🏆 VITÓRIA", SUCCESS_COLOR, "Vitória", "✅"),
                 "E": ("🤝 EMPATE", WARN_COLOR, "Empate", "➖"),
                 "D": ("❌ DERROTA", ERROR_COLOR, "Derrota", "❌")}


def result_code(our: int, opp: int) -> str:
    return "V" if our > opp else ("E" if our == opp else "D")


class ResultDraft:
    """Rascunho de um resultado enquanto o administrador monta gols/assistências/MVP."""

    def __init__(self, opponent: str, our: int, opp: int, date_iso: str, time_str: str, competition: str):
        self.opponent, self.our, self.opp = opponent, our, opp
        self.date_iso, self.time_str, self.competition = date_iso, time_str, competition
        self.participants: list = []
        self.goals: dict = {}
        self.assists: dict = {}
        self.goal_log: list = []
        self.assist_log: list = []
        self.mvp: Optional[int] = None

    @property
    def result(self) -> str:
        return result_code(self.our, self.opp)

    def total_goals(self) -> int:
        return sum(self.goals.values())

    def total_assists(self) -> int:
        return sum(self.assists.values())


def lineup_player_ids(gid: int) -> list:
    return [r["player_id"] for r in db_all(
        "SELECT l.player_id FROM lineups l JOIN players p ON p.id=l.player_id "
        "WHERE l.guild_id=? AND p.status IN ('ativo','reserva') ORDER BY l.added_at, l.rowid", (gid,))]


def confirmed_player_ids(gid: int) -> list:
    ev = db_one("SELECT id FROM presence_events WHERE guild_id=? ORDER BY id DESC LIMIT 1", (gid,))
    if ev is None:
        return []
    return [r["id"] for r in db_all(
        "SELECT p.id FROM presence_responses r JOIN players p ON p.user_id=r.user_id AND p.guild_id=? "
        "WHERE r.event_id=? AND r.response='vou' AND p.status IN ('ativo','reserva') ORDER BY p.number", (gid, ev["id"]))]


def commit_result(gid: int, actor_id: int, d: ResultDraft, game_id: Optional[int] = None) -> int:
    """Grava a partida e todo o histórico (gols, assistências, MVP) em uma única transação."""
    participants = list(dict.fromkeys(
        d.participants + list(d.goals) + list(d.assists) + ([d.mvp] if d.mvp else [])))
    if not participants:
        raise UserError("Selecione pelo menos um jogador que atuou na partida.", "Elenco vazio")
    now = now_utc_iso()
    with db_tx() as c:
        dup = c.execute(
            "SELECT id FROM matches WHERE guild_id=? AND lower(opponent)=lower(?) AND our_score=? AND opp_score=? "
            "AND played_date=? AND created_at >= datetime('now','-3 minutes')",
            (gid, d.opponent, d.our, d.opp, d.date_iso)).fetchone()
        if dup is not None:
            raise UserError("Este mesmo resultado já foi registrado há instantes. "
                            "Verifique com `/historico` para não duplicar.", "Resultado duplicado")
        cur = c.execute(
            "INSERT INTO matches (guild_id, game_id, opponent, our_score, opp_score, result, played_date, played_time, "
            "competition, mvp_player_id, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, game_id, d.opponent, d.our, d.opp, d.result, d.date_iso, d.time_str, d.competition,
             d.mvp, actor_id, now))
        mid = cur.lastrowid
        for pid in participants:
            c.execute("INSERT OR IGNORE INTO match_players (match_id, player_id) VALUES (?,?)", (mid, pid))
        for pid, n in d.goals.items():
            if n > 0:
                c.execute("INSERT INTO goals (guild_id, player_id, match_id, amount, source, created_by, created_at) "
                          "VALUES (?,?,?,?,?,?,?)", (gid, pid, mid, n, "partida", actor_id, now))
        for pid, n in d.assists.items():
            if n > 0:
                c.execute("INSERT INTO assists (guild_id, player_id, match_id, amount, source, created_by, created_at) "
                          "VALUES (?,?,?,?,?,?,?)", (gid, pid, mid, n, "partida", actor_id, now))
        if d.mvp:
            c.execute("INSERT INTO mvps (guild_id, player_id, match_id, amount, source, created_by, created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (gid, d.mvp, mid, 1, "partida", actor_id, now))
        # Integração com o calendário: marca o jogo agendado como disputado.
        if game_id is None:
            g = c.execute("SELECT id FROM games WHERE guild_id=? AND status='scheduled' AND lower(opponent)=lower(?) "
                          "AND game_date<=? ORDER BY game_date DESC LIMIT 1", (gid, d.opponent, d.date_iso)).fetchone()
            game_id = g["id"] if g else None
        if game_id is not None:
            c.execute("UPDATE games SET status='played', match_id=? WHERE id=? AND guild_id=?", (mid, game_id, gid))
            c.execute("UPDATE matches SET game_id=? WHERE id=?", (game_id, mid))
    return mid


def delete_match(gid: int, match_id: int) -> tuple:
    """Exclui um resultado revertendo todas as estatísticas ligadas a ele."""
    m = db_one("SELECT * FROM matches WHERE id=? AND guild_id=?", (match_id, gid))
    if m is None:
        raise UserError("Esse resultado não existe mais.", "Resultado não encontrado")
    pids = [r["player_id"] for r in db_all("SELECT player_id FROM match_players WHERE match_id=?", (match_id,))]
    with db_tx() as c:
        for table in ("goals", "assists", "mvps"):
            c.execute(f"DELETE FROM {table} WHERE match_id=?", (match_id,))
        c.execute("DELETE FROM match_players WHERE match_id=?", (match_id,))
        c.execute("UPDATE games SET status='scheduled', match_id=NULL WHERE match_id=? AND guild_id=?", (match_id, gid))
        c.execute("DELETE FROM matches WHERE id=?", (match_id,))
    return m, pids


def match_breakdown(match_id: int) -> dict:
    goals = db_all("SELECT p.name, SUM(g.amount) AS n FROM goals g JOIN players p ON p.id=g.player_id "
                   "WHERE g.match_id=? GROUP BY g.player_id HAVING n>0 ORDER BY n DESC, p.name", (match_id,))
    assists = db_all("SELECT p.name, SUM(a.amount) AS n FROM assists a JOIN players p ON p.id=a.player_id "
                     "WHERE a.match_id=? GROUP BY a.player_id HAVING n>0 ORDER BY n DESC, p.name", (match_id,))
    m = db_one("SELECT mvp_player_id FROM matches WHERE id=?", (match_id,))
    mvp = get_player_by_id(m["mvp_player_id"]) if m and m["mvp_player_id"] else None
    return {"goals": [(r["name"], r["n"]) for r in goals], "assists": [(r["name"], r["n"]) for r in assists],
            "mvp": mvp["name"] if mvp else None}


def build_result_embed(gid: int, match_id: int) -> discord.Embed:
    m = db_one("SELECT * FROM matches WHERE id=? AND guild_id=?", (match_id, gid))
    if m is None:
        return error_embed(gid, "Resultado não encontrado")
    title, color, _, _ = RESULT_LABELS[m["result"]]
    bd = match_breakdown(match_id)
    team = team_name_of(gid).upper()
    emb = make_embed(gid, title, f"## {team} {m['our_score']} × {m['opp_score']} {m['opponent'].upper()}", color)
    if bd["goals"]:
        emb.add_field(name="⚽ GOLS", value=trunc("\n".join(f"{n} — {q}" for n, q in bd["goals"]), 1000), inline=True)
    attributed = sum(q for _, q in bd["goals"])
    if attributed < m["our_score"]:
        emb.add_field(name="⚽ Sem autor registrado", value=str(m["our_score"] - attributed), inline=True)
    if bd["assists"]:
        emb.add_field(name="🅰️ ASSISTÊNCIAS", value=trunc("\n".join(f"{n} — {q}" for n, q in bd["assists"]), 1000),
                      inline=True)
    if bd["mvp"]:
        emb.add_field(name="🏅 MVP", value=bd["mvp"], inline=False)
    info = [f"📅 {fmt_date(m['played_date'])}" + (f" • 🕐 {m['played_time']}" if m["played_time"] else "")]
    if m["competition"]:
        info.append(f"🏆 {m['competition']}")
    emb.add_field(name="\u200b", value="\n".join(info), inline=False)
    return emb


class ResultBuilder(SafeView):
    """Interface guiada: elenco ➜ gols ➜ assistências ➜ MVP ➜ revisão. Sem digitar nada."""

    STAGES = ["elenco", "gols", "assist", "mvp", "revisao"]
    STAGE_TITLES = {"elenco": "1/5 • Quem jogou?", "gols": "2/5 • Gols", "assist": "3/5 • Assistências",
                    "mvp": "4/5 • MVP da partida", "revisao": "5/5 • Revisão"}

    def __init__(self, gid: int, owner_id: int, draft: ResultDraft, game_id: Optional[int] = None):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=900)
        self.gid, self.d, self.game_id = gid, draft, game_id
        self.stage = "elenco"
        self.finished = False
        self.render()

    # ----- helpers de estado -----
    def players(self) -> list:
        return [p for p in (get_player_by_id(pid) for pid in self.d.participants) if p is not None]

    def set_participants(self, ids: list) -> None:
        self.d.participants = list(dict.fromkeys(ids))
        keep = set(self.d.participants)
        self.d.goals = {k: v for k, v in self.d.goals.items() if k in keep}
        self.d.assists = {k: v for k, v in self.d.assists.items() if k in keep}
        self.d.goal_log = [x for x in self.d.goal_log if x in keep]
        self.d.assist_log = [x for x in self.d.assist_log if x in keep]
        if self.d.mvp not in keep:
            self.d.mvp = None

    def _names(self, mapping: dict) -> str:
        if not mapping:
            return "—"
        parts = []
        for pid, n in mapping.items():
            p = get_player_by_id(pid)
            parts.append(f"{p['name'] if p else pid} ×{n}")
        return trunc(", ".join(parts), 1000)

    # ----- embed -----
    def embed(self) -> discord.Embed:
        d, gid = self.d, self.gid
        label, color, _, _ = RESULT_LABELS[d.result]
        emb = make_embed(gid, f"📝 Registrar resultado • {self.STAGE_TITLES[self.stage]}", color=color)
        extra = f"📅 {fmt_date(d.date_iso)}" + (f" • 🕐 {d.time_str}" if d.time_str else "")
        if d.competition:
            extra += f" • 🏆 {d.competition}"
        emb.description = f"## {team_name_of(gid).upper()} {d.our} × {d.opp} {d.opponent.upper()}\n{label} • {extra}"
        names = ", ".join(p["name"] for p in self.players()) or "Nenhum jogador selecionado"
        emb.add_field(name=f"👥 Jogaram ({len(d.participants)})", value=trunc(names, 1000), inline=False)
        emb.add_field(name=f"⚽ Gols ({d.total_goals()}/{d.our})", value=self._names(d.goals), inline=True)
        emb.add_field(name=f"🅰️ Assistências ({d.total_assists()}/{d.our})", value=self._names(d.assists), inline=True)
        mvp = get_player_by_id(d.mvp) if d.mvp else None
        emb.add_field(name="🏅 MVP", value=mvp["name"] if mvp else "—", inline=True)
        hints = {
            "elenco": "Selecione no menu quem atuou, ou use os atalhos (escalação atual / confirmados).",
            "gols": "Cada jogador escolhido no menu soma **+1 gol**. Escolha de novo para somar mais.",
            "assist": "Cada jogador escolhido no menu soma **+1 assistência**.",
            "mvp": "Escolha o melhor jogador da partida (ou continue sem MVP).",
            "revisao": "Confira tudo e confirme. Rank, conquistas e histórico serão atualizados.",
        }
        emb.add_field(name="➡️ Próximo passo", value=hints[self.stage], inline=False)
        return emb

    # ----- componentes -----
    def render(self) -> None:
        self.clear_items()
        stage = self.stage
        if stage == "elenco":
            sel = discord.ui.UserSelect(placeholder="Quem atuou na partida? (até 25)", min_values=1,
                                        max_values=25, row=0)

            async def on_users(interaction: discord.Interaction):
                ids, skipped = [], []
                for m in sel.values:
                    p = get_player(self.gid, m.id)
                    if p is None or p["status"] not in ("ativo", "reserva"):
                        skipped.append(getattr(m, "display_name", m.name))
                    else:
                        ids.append(p["id"])
                self.set_participants(ids)
                self.render()
                await interaction.response.edit_message(embed=self.embed(), view=self)
                if skipped:
                    await interaction.followup.send(embed=warn_embed(
                        self.gid, "Alguns usuários foram ignorados",
                        "Não estão cadastrados como **ativo/reserva**: " + ", ".join(skipped)), ephemeral=True)

            sel.callback = on_users
            self.add_item(sel)
            add_button(self, "Usar escalação atual", self._use_lineup, emoji="📋", row=1)
            add_button(self, "Usar confirmados", self._use_confirmed, emoji="✅", row=1)
            add_button(self, "Próximo", self._next, emoji="➡️", style=discord.ButtonStyle.primary, row=1)
        elif stage in ("gols", "assist"):
            players = self.players()[:25]
            if players:
                opts = [discord.SelectOption(label=trunc(p["name"], 100), value=str(p["id"]),
                                             description=f"#{p['number']} • {p['position']}") for p in players]
                sel = discord.ui.Select(
                    placeholder="Quem fez gol? (cada escolha soma +1)" if stage == "gols"
                    else "Quem deu assistência? (cada escolha soma +1)",
                    min_values=1, max_values=len(opts), options=opts, row=0)

                async def on_pick(interaction: discord.Interaction, sel=sel):
                    picked = [int(v) for v in sel.values]
                    store = self.d.goals if self.stage == "gols" else self.d.assists
                    logl = self.d.goal_log if self.stage == "gols" else self.d.assist_log
                    total = sum(store.values())
                    if total + len(picked) > self.d.our:
                        raise UserError(f"O time marcou **{self.d.our}** gol(s); não é possível registrar "
                                        f"mais do que isso ({total} já registrado(s)).", "Limite do placar")
                    for pid in picked:
                        store[pid] = store.get(pid, 0) + 1
                        logl.append(pid)
                    self.render()
                    await interaction.response.edit_message(embed=self.embed(), view=self)

                sel.callback = on_pick
                self.add_item(sel)
            add_button(self, "Desfazer último", self._undo, emoji="↩️", row=1)
            add_button(self, "Zerar", self._clear, emoji="🧹", row=1)
            add_button(self, "Voltar", self._back, emoji="⬅️", row=1)
            add_button(self, "Próximo", self._next, emoji="➡️", style=discord.ButtonStyle.primary, row=1)
        elif stage == "mvp":
            players = self.players()[:25]
            if players:
                opts = [discord.SelectOption(label=trunc(p["name"], 100), value=str(p["id"]),
                                             description=f"#{p['number']} • {p['position']}",
                                             default=(p["id"] == self.d.mvp)) for p in players]
                sel = discord.ui.Select(placeholder="Escolha o MVP da partida", min_values=1, max_values=1,
                                        options=opts, row=0)

                async def on_mvp(interaction: discord.Interaction, sel=sel):
                    self.d.mvp = int(sel.values[0])
                    self.render()
                    await interaction.response.edit_message(embed=self.embed(), view=self)

                sel.callback = on_mvp
                self.add_item(sel)
            add_button(self, "Sem MVP", self._no_mvp, emoji="🚫", row=1)
            add_button(self, "Voltar", self._back, emoji="⬅️", row=1)
            add_button(self, "Próximo", self._next, emoji="➡️", style=discord.ButtonStyle.primary, row=1)
        else:  # revisão
            add_button(self, "Confirmar e registrar", self._confirm, emoji="✅", style=discord.ButtonStyle.success, row=0)
            add_button(self, "Voltar", self._back, emoji="⬅️", row=0)
        add_button(self, "Cancelar", self._cancel, emoji="✖️", style=discord.ButtonStyle.danger,
                   row=2 if stage != "revisao" else 0)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.render()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    # ----- ações -----
    async def _use_lineup(self, interaction: discord.Interaction):
        ids = lineup_player_ids(self.gid)
        if not ids:
            raise UserError("Não há escalação montada. Use `/escalar` ou selecione os jogadores manualmente.",
                            "Sem escalação")
        self.set_participants(ids[:25])
        await self._refresh(interaction)

    async def _use_confirmed(self, interaction: discord.Interaction):
        ids = confirmed_player_ids(self.gid)
        if not ids:
            raise UserError("Nenhum jogador confirmou presença no último aviso de jogo.", "Sem confirmados")
        self.set_participants(ids[:25])
        await self._refresh(interaction)

    async def _next(self, interaction: discord.Interaction):
        if self.stage == "elenco" and not self.d.participants:
            raise UserError("Selecione pelo menos um jogador que atuou na partida.", "Elenco vazio")
        self.stage = self.STAGES[min(len(self.STAGES) - 1, self.STAGES.index(self.stage) + 1)]
        await self._refresh(interaction)

    async def _back(self, interaction: discord.Interaction):
        self.stage = self.STAGES[max(0, self.STAGES.index(self.stage) - 1)]
        await self._refresh(interaction)

    async def _undo(self, interaction: discord.Interaction):
        store = self.d.goals if self.stage == "gols" else self.d.assists
        logl = self.d.goal_log if self.stage == "gols" else self.d.assist_log
        if logl:
            pid = logl.pop()
            store[pid] = store.get(pid, 0) - 1
            if store[pid] <= 0:
                store.pop(pid, None)
        await self._refresh(interaction)

    async def _clear(self, interaction: discord.Interaction):
        if self.stage == "gols":
            self.d.goals.clear()
            self.d.goal_log.clear()
        else:
            self.d.assists.clear()
            self.d.assist_log.clear()
        await self._refresh(interaction)

    async def _no_mvp(self, interaction: discord.Interaction):
        self.d.mvp = None
        self.stage = "revisao"
        await self._refresh(interaction)

    async def _cancel(self, interaction: discord.Interaction):
        self.finished = True
        self.stop()
        await interaction.response.edit_message(
            embed=info_embed(self.gid, "Registro cancelado", "Nenhum dado foi salvo."), view=None)

    def validate(self) -> None:
        d = self.d
        if not d.participants:
            raise UserError("Selecione pelo menos um jogador que atuou na partida.", "Elenco vazio")
        if d.total_goals() > d.our:
            raise UserError("A soma dos gols dos jogadores é maior que o placar do time.", "Gols inconsistentes")
        if d.total_assists() > d.our:
            raise UserError("A quantidade de assistências não pode passar do número de gols do time.",
                            "Assistências inconsistentes")

    async def _confirm(self, interaction: discord.Interaction):
        require_staff(interaction)
        if self.finished:
            raise UserError("Este resultado já foi processado.", "Já registrado")
        self.validate()
        self.finished = True
        self.stop()
        gid, d = self.gid, self.d
        await interaction.response.edit_message(embed=info_embed(gid, "⏳ Registrando resultado…"), view=None)
        try:
            mid = commit_result(gid, interaction.user.id, d, self.game_id)
        except Exception:
            self.finished = False
            raise
        pids = list(dict.fromkeys(d.participants + list(d.goals) + list(d.assists) + ([d.mvp] if d.mvp else [])))
        changes, unlocked = await after_stats_change(gid, pids, interaction.user.id, f"Resultado vs {d.opponent}")
        await log_event(gid, interaction.user.id, "Resultados", "Resultado registrado",
                        after=f"{team_name_of(gid)} {d.our} × {d.opp} {d.opponent} ({fmt_date(d.date_iso)})",
                        details=f"Partida #{mid} • {len(pids)} jogadores")
        result_embed = build_result_embed(gid, mid)
        extras = []
        if changes:
            extras.append("📈 **Mudanças de Rank**\n" + "\n".join(
                f"{c['name']}: {c['old']} ➜ **{c['new']}**" for c in changes))
        if unlocked:
            extras.append("🏆 **Conquistas desbloqueadas**\n" + describe_unlocks(unlocked))
        if extras:
            result_embed.add_field(name="\u200b", value=trunc("\n\n".join(extras), 1000), inline=False)
        await interaction.edit_original_response(embed=success_embed(
            gid, "Resultado registrado",
            f"Partida **#{mid}** salva. Estatísticas, Rank e histórico foram atualizados."), view=None)
        guild = interaction.guild
        sent_channel_ids = set()
        results_channel = guild.get_channel(cfg_int(gid, "results_channel") or 0) if guild else None
        targets = [interaction.channel]
        if results_channel is not None and results_channel.id != getattr(interaction.channel, "id", None):
            targets.append(results_channel)
        for ch in targets:
            try:
                await ch.send(embed=result_embed)
                sent_channel_ids.add(ch.id)
            except Exception:
                log.warning("Não consegui enviar o resultado no canal %s.", getattr(ch, "id", "?"))
        if not sent_channel_ids:
            await interaction.followup.send(embed=result_embed, ephemeral=True)
        if guild:
            await refresh_ranking_board(guild)
            await refresh_calendar_board(guild)


async def start_result_flow(interaction: discord.Interaction, adversario: str, nosso: int, deles: int,
                            data: Optional[str], horario: Optional[str], competicao: Optional[str],
                            mvp_user: Optional[discord.abc.User] = None) -> None:
    require_staff(interaction)
    gid = interaction.guild_id
    adversario = re.sub(r"\s+", " ", adversario.strip())
    if not adversario:
        raise UserError("Informe o nome do adversário.", "Adversário inválido")
    if not (0 <= nosso <= 99 and 0 <= deles <= 99):
        raise UserError("Os placares devem estar entre 0 e 99.", "Placar inválido")
    date_iso = parse_date_br(data, gid) if data and data.strip() else today_iso(gid)
    time_str = parse_time_br(horario) if horario and horario.strip() else ""
    if not list_players(gid, include_inactive=False):
        raise UserError("Cadastre pelo menos um jogador com `/jogador adicionar` antes de registrar partidas.",
                        "Elenco vazio")
    draft = ResultDraft(adversario, nosso, deles, date_iso, time_str, (competicao or "").strip())
    lineup = lineup_player_ids(gid)[:25]
    draft.participants = list(lineup)
    if mvp_user is not None:
        p = get_player(gid, mvp_user.id)
        if p is None or p["status"] not in ("ativo", "reserva"):
            raise UserError(f"{mvp_user.mention} não é um jogador ativo/reserva e não pode ser MVP.", "MVP inválido")
        if p["id"] not in draft.participants:
            draft.participants.append(p["id"])
        draft.mvp = p["id"]
    view = ResultBuilder(gid, interaction.user.id, draft)
    await respond(interaction, embed=view.embed(), view=view)
    view.bind(interaction)


@tree.command(name="result", description="Registra o resultado de uma partida (administração).")
@app_commands.describe(adversario="Nome do time adversário", nosso_placar="Gols do seu time",
                       adversario_placar="Gols do adversário", data="Data (dd/mm/aaaa) — padrão: hoje",
                       horario="Horário (HH:MM)", competicao="Nome da competição", mvp="MVP da partida (opcional)")
@app_commands.guild_only()
@staff_only()
@app_commands.checks.cooldown(1, 3.0, key=_manual_cooldown_key)
async def cmd_result(interaction: discord.Interaction, adversario: app_commands.Range[str, 1, 60],
                     nosso_placar: app_commands.Range[int, 0, 99], adversario_placar: app_commands.Range[int, 0, 99],
                     data: Optional[app_commands.Range[str, 1, 12]] = None,
                     horario: Optional[app_commands.Range[str, 1, 8]] = None,
                     competicao: Optional[app_commands.Range[str, 1, 60]] = None,
                     mvp: Optional[discord.Member] = None):
    await start_result_flow(interaction, adversario, nosso_placar, adversario_placar, data, horario, competicao, mvp)


class ResultStartModal(SafeModal):
    """Versão em modal do /result, usada pelo painel administrativo."""

    def __init__(self):
        super().__init__(title="Registrar resultado", timeout=600)
        self.f_opp = discord.ui.TextInput(label="Adversário", max_length=60)
        self.f_our = discord.ui.TextInput(label="Nosso placar", max_length=2, placeholder="Ex.: 5")
        self.f_their = discord.ui.TextInput(label="Placar do adversário", max_length=2, placeholder="Ex.: 2")
        self.f_dt = discord.ui.TextInput(label="Data e horário (opcional)", required=False, max_length=20,
                                         placeholder="dd/mm/aaaa HH:MM (padrão: hoje)")
        self.f_comp = discord.ui.TextInput(label="Competição (opcional)", required=False, max_length=60)
        for item in (self.f_opp, self.f_our, self.f_their, self.f_dt, self.f_comp):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            our, their = int(self.f_our.value.strip()), int(self.f_their.value.strip())
        except ValueError:
            raise UserError("Os placares precisam ser números inteiros.", "Placar inválido")
        data = horario = None
        if self.f_dt.value.strip():
            data, horario = parse_datetime_br(self.f_dt.value, interaction.guild_id)
        await start_result_flow(interaction, self.f_opp.value, our, their, data, horario, self.f_comp.value)


# ----- Histórico de resultados ------------------------------------------------------------

def match_block(m, compact: bool = False) -> str:
    _, _, res_name, emoji = RESULT_LABELS[m["result"]]
    bd = match_breakdown(m["id"])
    lines = [f"{emoji} **vs {m['opponent']}** — **{m['our_score']} × {m['opp_score']}** ({res_name})",
             f"📅 {fmt_date(m['played_date'])}" + (f" · 🕐 {m['played_time']}" if m["played_time"] else "")
             + (f" · 🏆 {m['competition']}" if m["competition"] else "")]
    if not compact:
        if bd["goals"]:
            lines.append("⚽ " + trunc(", ".join(f"{n} ({q})" if q > 1 else n for n, q in bd["goals"]), 200))
        if bd["assists"]:
            lines.append("🅰️ " + trunc(", ".join(f"{n} ({q})" if q > 1 else n for n, q in bd["assists"]), 200))
        if bd["mvp"]:
            lines.append(f"🏅 MVP: **{bd['mvp']}**")
    return "\n".join(lines)


def build_history_pages(gid: int, per_page: int = 4) -> list:
    matches = db_all("SELECT * FROM matches WHERE guild_id=? ORDER BY played_date DESC, id DESC LIMIT 120", (gid,))
    if not matches:
        return [info_embed(gid, "📜 Histórico de resultados",
                           "Nenhuma partida registrada ainda.\nUse `/result` para registrar o primeiro resultado.")]
    pages = []
    for group in chunk(matches, per_page):
        pages.append(info_embed(gid, "📜 Histórico de resultados", "\n\n".join(match_block(m) for m in group)))
    return pages


@tree.command(name="historico", description="Mostra o histórico de resultados do time.")
@app_commands.guild_only()
async def cmd_historico(interaction: discord.Interaction):
    await send_paged(interaction, build_history_pages(interaction.guild_id))


# ==============================
# CALENDÁRIO
# ==============================

def get_game(gid: int, game_id: int):
    return db_one("SELECT * FROM games WHERE id=? AND guild_id=?", (game_id, gid))


def upcoming_games(gid: int, limit: int = 50) -> list:
    return db_all("SELECT * FROM games WHERE guild_id=? AND status='scheduled' AND game_date>=? "
                  "ORDER BY game_date, COALESCE(game_time,''), id LIMIT ?", (gid, today_iso(gid), limit))


def format_game(g, with_id: bool = False) -> str:
    head = f"🆚 **{g['opponent']}**" + (f" `#{g['id']}`" if with_id else "")
    when = f"📅 {fmt_date(g['game_date'])}" + (f" · 🕐 {g['game_time']}" if g["game_time"] else " · 🕐 a definir")
    lines = [head, when]
    if g["competition"]:
        lines.append(f"🏆 {g['competition']}")
    if g["location"]:
        lines.append(f"📍 {g['location']}")
    if g["notes"]:
        lines.append(f"📝 {trunc(g['notes'], 160)}")
    return "\n".join(lines)


def build_calendar_pages(gid: int, per_page: int = 4, with_id: bool = False) -> list:
    games = upcoming_games(gid)
    title = "📅 Próximos jogos"
    if not games:
        return [info_embed(gid, title, "Nenhum jogo agendado no momento.\nA administração pode adicionar com `/jogo adicionar`.")]
    return [info_embed(gid, title, "\n\n".join(format_game(g, with_id) for g in group))
            for group in chunk(games, per_page)]


@tree.command(name="calendario", description="Mostra os próximos jogos do time.")
@app_commands.guild_only()
async def cmd_calendario(interaction: discord.Interaction):
    await send_paged(interaction, build_calendar_pages(interaction.guild_id))


async def refresh_calendar_board(guild: discord.Guild) -> None:
    """Mantém uma mensagem de calendário sempre atualizada no canal configurado."""
    gid = guild.id
    channel_id = cfg_int(gid, "calendar_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None or not hasattr(channel, "send"):
        return
    emb = build_calendar_pages(gid, per_page=8)[0].copy()
    emb.timestamp = datetime.now(timezone.utc)
    msg_id = cfg_int(gid, "calendar_message_id")
    try:
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=emb)
                return
            except discord.NotFound:
                pass
        msg = await channel.send(embed=emb)
        cfg_set(gid, "calendar_message_id", msg.id)
    except (discord.Forbidden, discord.HTTPException):
        log.warning("Sem permissão para atualizar o calendário no canal %s.", channel_id)


def save_game(gid: int, actor_id: int, data: dict, game_id: Optional[int] = None):
    opp = re.sub(r"\s+", " ", (data["opponent"] or "").strip())
    if not opp:
        raise UserError("Informe o nome do adversário.", "Adversário inválido")
    if game_id is None:
        gid_new = db_exec(
            "INSERT INTO games (guild_id, opponent, game_date, game_time, competition, location, notes, status, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?, 'scheduled', ?, ?)",
            (gid, opp, data["date"], data["time"], data["competition"], data["location"], data["notes"],
             actor_id, now_utc_iso()))
        return None, get_game(gid, gid_new)
    before = get_game(gid, game_id)
    if before is None:
        raise UserError("Esse jogo não existe mais.", "Jogo não encontrado")
    db_exec("UPDATE games SET opponent=?, game_date=?, game_time=?, competition=?, location=?, notes=? "
            "WHERE id=? AND guild_id=?",
            (opp, data["date"], data["time"], data["competition"], data["location"], data["notes"], game_id, gid))
    return before, get_game(gid, game_id)


def game_snapshot(g) -> str:
    if g is None:
        return "—"
    return (f"{g['opponent']} • {fmt_date(g['game_date'])} {g['game_time'] or ''} • "
            f"{g['competition'] or 'sem competição'} • {g['location'] or 'sem local'}")


class GamePostView(SafeView):
    """Botão exibido após cadastrar um jogo: publica o aviso com confirmação de presença."""

    def __init__(self, owner_id: int, game_id: int):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.game_id = game_id

    @discord.ui.button(label="Publicar aviso com presença", emoji="📣", style=discord.ButtonStyle.success)
    async def btn_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        require_staff(interaction)
        gid = interaction.guild_id
        game = get_game(gid, self.game_id)
        if game is None:
            raise UserError("Esse jogo não existe mais.", "Jogo não encontrado")
        channel = interaction.channel
        msg = await post_game_announcement(interaction.guild, channel, game, interaction.user.id)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=success_embed(
            gid, "Aviso publicado", f"O aviso de jogo foi enviado em {channel.mention}: {msg.jump_url}"), ephemeral=True)


class GameModal(SafeModal):
    def __init__(self, gid: int, game=None):
        super().__init__(title="Editar jogo" if game else "Adicionar jogo", timeout=600)
        self.game = game
        default_dt = None
        if game is not None:
            default_dt = f"{fmt_date(game['game_date'])} {game['game_time'] or ''}".strip()
        self.f_opp = discord.ui.TextInput(label="Adversário", max_length=60, default=game["opponent"] if game else None)
        self.f_dt = discord.ui.TextInput(label="Data e horário", max_length=20, default=default_dt,
                                         placeholder="dd/mm/aaaa HH:MM  (ex.: 02/10/2026 20:00)")
        self.f_comp = discord.ui.TextInput(label="Competição", required=False, max_length=60,
                                           default=game["competition"] if game and game["competition"] else None)
        self.f_loc = discord.ui.TextInput(label="Canal / local", required=False, max_length=80,
                                          default=game["location"] if game and game["location"] else None,
                                          placeholder="Ex.: Servidor privado, canal de voz #jogos")
        self.f_notes = discord.ui.TextInput(label="Observações", required=False, max_length=300,
                                            style=discord.TextStyle.paragraph,
                                            default=game["notes"] if game and game["notes"] else None)
        for item in (self.f_opp, self.f_dt, self.f_comp, self.f_loc, self.f_notes):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        date_iso, time_str = parse_datetime_br(self.f_dt.value, gid)
        data = {"opponent": self.f_opp.value, "date": date_iso, "time": time_str,
                "competition": self.f_comp.value.strip(), "location": self.f_loc.value.strip(),
                "notes": self.f_notes.value.strip()}
        before, after = save_game(gid, interaction.user.id, data, self.game["id"] if self.game else None)
        await log_event(gid, interaction.user.id, "Calendário", "Jogo editado" if before else "Jogo adicionado",
                        before=game_snapshot(before) if before else "", after=game_snapshot(after))
        emb = success_embed(gid, "Jogo atualizado" if before else "Jogo adicionado ao calendário", format_game(after, True))
        view = None if before else GamePostView(interaction.user.id, after["id"])
        await respond(interaction, embed=emb, view=view)
        if view is not None:
            view.bind(interaction)
        if interaction.guild:
            await refresh_calendar_board(interaction.guild)


class GameSelectView(SafeView):
    """Escolha de um jogo agendado para editar/remover."""

    def __init__(self, gid: int, owner_id: int, callback: Callable[[discord.Interaction, int], Awaitable[None]]):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=300)
        games = upcoming_games(gid, 25)
        if not games:
            self.empty = True
            return
        self.empty = False
        sel = discord.ui.Select(
            placeholder="Escolha o jogo…",
            options=[discord.SelectOption(label=trunc(f"{g['opponent']} • {fmt_date(g['game_date'])} {g['game_time'] or ''}".strip(), 100),
                                          value=str(g["id"]), description=trunc(g["competition"] or "Sem competição", 100))
                     for g in games])

        async def _cb(interaction: discord.Interaction):
            self._origin = None
            await callback(interaction, int(sel.values[0]))

        sel.callback = _cb
        self.add_item(sel)


async def ask_game_then(interaction: discord.Interaction, callback) -> None:
    view = GameSelectView(interaction.guild_id, interaction.user.id, callback)
    if view.empty:
        raise UserError("Não há jogos agendados. Adicione um com `/jogo adicionar`.", "Calendário vazio")
    await respond(interaction, embed=info_embed(interaction.guild_id, "📅 Selecione o jogo"), view=view)
    view.bind(interaction)


async def edit_game_flow(interaction: discord.Interaction, game_id: int) -> None:
    game = get_game(interaction.guild_id, game_id)
    if game is None:
        raise UserError("Esse jogo não existe mais.", "Jogo não encontrado")
    await interaction.response.send_modal(GameModal(interaction.guild_id, game))


async def remove_game_flow(interaction: discord.Interaction, game_id: int) -> None:
    gid = interaction.guild_id
    game = get_game(gid, game_id)
    if game is None:
        raise UserError("Esse jogo não existe mais.", "Jogo não encontrado")

    async def do_remove(inter: discord.Interaction):
        require_staff(inter)
        db_exec("DELETE FROM games WHERE id=? AND guild_id=?", (game_id, gid))
        await log_event(gid, inter.user.id, "Calendário", "Jogo removido", before=game_snapshot(game))
        await inter.response.edit_message(embed=success_embed(gid, "Jogo removido", f"**{game['opponent']}** saiu do calendário."), view=None)
        if inter.guild:
            await refresh_calendar_board(inter.guild)

    view = ConfirmView(interaction.user.id, do_remove, confirm_label="Remover jogo")
    await edit_message(interaction, embed=warn_embed(gid, "Remover este jogo?", format_game(game)), view=view)
    view.bind(interaction)


jogo_group = app_commands.Group(name="jogo", description="Gerencia o calendário de jogos", guild_only=True)


@jogo_group.command(name="adicionar", description="Adiciona um jogo ao calendário (abre um formulário).")
@staff_only()
async def jogo_adicionar(interaction: discord.Interaction):
    await interaction.response.send_modal(GameModal(interaction.guild_id))


@jogo_group.command(name="editar", description="Edita um jogo agendado.")
@staff_only()
async def jogo_editar(interaction: discord.Interaction):
    await ask_game_then(interaction, edit_game_flow)


@jogo_group.command(name="remover", description="Remove um jogo do calendário.")
@staff_only()
async def jogo_remover(interaction: discord.Interaction):
    await ask_game_then(interaction, remove_game_flow)


@jogo_group.command(name="listar", description="Lista os jogos agendados (com IDs).")
@staff_only()
async def jogo_listar(interaction: discord.Interaction):
    await send_paged(interaction, build_calendar_pages(interaction.guild_id, with_id=True), ephemeral=True)


tree.add_command(jogo_group)


# ==============================
# ESCALAÇÃO
# ==============================

MAX_LINEUP = 18


def lineup_entries(gid: int) -> list:
    rows = db_all(
        "SELECT l.position AS lineup_pos, p.id AS pid, p.user_id, p.name, p.number, p.position AS main_pos, p.status "
        "FROM lineups l JOIN players p ON p.id=l.player_id WHERE l.guild_id=? ORDER BY l.added_at, l.rowid", (gid,))
    out = []
    for r in rows:
        st = stats_row(gid, r["pid"])
        out.append({"pid": r["pid"], "user_id": r["user_id"], "name": r["name"], "number": r["number"],
                    "position": r["lineup_pos"], "rank": st["rank"]})
    return out


def set_lineup_player(gid: int, player, position: str) -> None:
    position = normalize_position(position)
    if position is None:
        raise UserError("Posição inválida. Use: " + ", ".join(POSITION_NAMES) + ".", "Posição inválida")
    if player["status"] not in ("ativo", "reserva"):
        raise UserError(f"**{player['name']}** está **{player['status']}** e não pode ser escalado. "
                        f"Apenas jogadores ativos ou reservas.", "Jogador indisponível")
    exists = db_one("SELECT 1 FROM lineups WHERE guild_id=? AND player_id=?", (gid, player["id"]))
    if exists is None:
        total = db_one("SELECT COUNT(*) AS n FROM lineups WHERE guild_id=?", (gid,))["n"]
        if total >= MAX_LINEUP:
            raise UserError(f"A escalação já possui {MAX_LINEUP} jogadores (titulares + reservas).", "Escalação cheia")
        db_exec("INSERT INTO lineups (guild_id, player_id, position, added_at) VALUES (?,?,?,?)",
                (gid, player["id"], position, now_utc_iso()))
    else:
        db_exec("UPDATE lineups SET position=? WHERE guild_id=? AND player_id=?", (position, gid, player["id"]))


def assign_slots(formation: str, entries: list) -> tuple:
    """Distribui os jogadores nos slots da formação (posição exata ➜ mesma linha ➜ qualquer)."""
    slots = []
    for li, tags in enumerate(FORMATIONS[formation]):
        for si, tag in enumerate(tags):
            slots.append({"line": li, "tag": tag, "x": (si + 1) / (len(tags) + 1), "entry": None})
    remaining = list(entries)
    for e in list(remaining):
        for s in slots:
            if s["entry"] is None and s["tag"] == e["position"]:
                s["entry"] = e
                remaining.remove(e)
                break
    for e in list(remaining):
        line = POSITION_LINE.get(e["position"], 2)
        for s in slots:
            if s["entry"] is None and s["line"] == line:
                s["entry"] = e
                remaining.remove(e)
                break
    for e in list(remaining):
        if e["position"] == "GOL":
            continue
        for s in slots:
            if s["entry"] is None and s["line"] != 0:
                s["entry"] = e
                remaining.remove(e)
                break
    return slots, remaining


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = True):
    names = (["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf"]
             if bold else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _circle_image(data: Optional[bytes], size: int, initial: str) -> Image.Image:
    """Avatar circular com bordas suavizadas (ou inicial do nome se não houver avatar)."""
    av = None
    if data:
        try:
            av = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            av = None
    if av is None:
        av = Image.new("RGBA", (size, size), (30, 41, 59, 255))
        ImageDraw.Draw(av).text((size / 2, size / 2), (initial or "?")[:1].upper(), font=_font(int(size * 0.5)),
                                fill=(226, 232, 240), anchor="mm")
    big = 4
    mask = Image.new("L", (size * big, size * big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * big - 1, size * big - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, (0, 0), mask)
    return out


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_w: int, size: int, bold: bool = True) -> tuple:
    while size > 14:
        f = _font(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return text, f
        size -= 2
    f = _font(14, bold)
    while len(text) > 3 and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…", f


def render_lineup_image(team: str, formation: str, slots: list, bench: list, show_avatars: bool,
                        show_numbers: bool, date_text: str, avatars: dict) -> bytes:
    """Desenha o campo, os jogadores (avatares/nomes/posições) e a formação em PNG."""
    W, H = 1000, 1400
    img = Image.new("RGB", (W, H), (15, 23, 42))
    d = ImageDraw.Draw(img)
    # Cabeçalho
    d.rectangle([0, 0, W, 150], fill=(17, 24, 39))
    d.rectangle([0, 146, W, 152], fill=(212, 175, 55))
    t, f = _fit_text(d, team.upper(), 600, 62)
    d.text((50, 62), t, font=f, fill=(255, 255, 255), anchor="lm")
    d.text((50, 112), f"ESCALAÇÃO  •  {date_text}", font=_font(26, False), fill=(212, 175, 55), anchor="lm")
    d.text((950, 62), formation, font=_font(70), fill=(255, 255, 255), anchor="rm")
    d.text((950, 112), "FORMAÇÃO", font=_font(24, False), fill=(148, 163, 184), anchor="rm")
    # Campo
    px0, py0, px1, py1 = 50, 185, 950, 1235
    bands = 14
    bh = (py1 - py0) / bands
    for i in range(bands):
        color = (36, 140, 66) if i % 2 == 0 else (31, 126, 59)
        d.rectangle([px0, py0 + i * bh, px1, py0 + (i + 1) * bh], fill=color)
    white = (240, 248, 240)
    cx, cy = (px0 + px1) // 2, (py0 + py1) // 2
    d.rectangle([px0, py0, px1, py1], outline=white, width=4)
    d.line([px0, cy, px1, cy], fill=white, width=4)
    d.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], outline=white, width=4)
    d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=white)
    d.rectangle([cx - 230, py1 - 190, cx + 230, py1], outline=white, width=4)
    d.rectangle([cx - 105, py1 - 70, cx + 105, py1], outline=white, width=4)
    d.arc([cx - 100, py1 - 130 - 100, cx + 100, py1 - 130 + 100], 218, 322, fill=white, width=4)
    d.ellipse([cx - 6, py1 - 130 - 6, cx + 6, py1 - 130 + 6], fill=white)
    d.rectangle([cx - 230, py0, cx + 230, py0 + 190], outline=white, width=4)
    d.rectangle([cx - 105, py0, cx + 105, py0 + 70], outline=white, width=4)
    d.arc([cx - 100, py0 + 130 - 100, cx + 100, py0 + 130 + 100], 38, 142, fill=white, width=4)
    d.ellipse([cx - 6, py0 + 130 - 6, cx + 6, py0 + 130 + 6], fill=white)
    # Jogadores
    n_lines = len(FORMATIONS[formation])
    y_bot, y_top = py1 - 125, py0 + 150
    size = 112
    for s in slots:
        x = int(px0 + s["x"] * (px1 - px0))
        y = int(y_bot - s["line"] * (y_bot - y_top) / max(1, n_lines - 1))
        e = s["entry"]
        if e is None:
            d.ellipse([x - size // 2, y - size // 2, x + size // 2, y + size // 2], outline=(255, 255, 255),
                      width=3)
            d.text((x, y), s["tag"], font=_font(30), fill=(255, 255, 255), anchor="mm")
            continue
        ring = RANK_COLORS.get(e["rank"], (255, 255, 255))
        ring_rgb = ((ring >> 16) & 255, (ring >> 8) & 255, ring & 255)
        d.ellipse([x - size // 2 - 7, y - size // 2 - 7, x + size // 2 + 7, y + size // 2 + 7], fill=ring_rgb)
        if show_avatars:
            av = _circle_image(avatars.get(e["pid"]), size, e["name"])
            img.paste(av, (x - size // 2, y - size // 2), av)
        else:
            d.ellipse([x - size // 2, y - size // 2, x + size // 2, y + size // 2], fill=(30, 41, 59))
            d.text((x, y), str(e["number"]) if show_numbers else e["name"][:1].upper(), font=_font(52),
                   fill=(255, 255, 255), anchor="mm")
        # etiqueta de posição
        tag_w = int(d.textlength(e["position"], font=_font(22))) + 22
        d.rounded_rectangle([x - size // 2 - 10, y - size // 2 - 14, x - size // 2 - 10 + tag_w, y - size // 2 + 16],
                            radius=10, fill=(17, 24, 39), outline=(255, 255, 255), width=2)
        d.text((x - size // 2 - 10 + tag_w / 2, y - size // 2 + 1), e["position"], font=_font(22),
               fill=(255, 255, 255), anchor="mm")
        # número da camisa
        if show_numbers:
            bx, by = x + size // 2 - 4, y + size // 2 - 8
            d.ellipse([bx - 24, by - 24, bx + 24, by + 24], fill=(212, 175, 55), outline=(17, 24, 39), width=3)
            d.text((bx, by), str(e["number"]), font=_font(26), fill=(17, 24, 39), anchor="mm")
        # nome
        name, nf = _fit_text(d, e["name"], 190, 28)
        tw = int(d.textlength(name, font=nf)) + 28
        ny = y + size // 2 + 28
        d.rounded_rectangle([x - tw / 2, ny - 18, x + tw / 2, ny + 18], radius=16, fill=(17, 24, 39))
        d.text((x, ny), name, font=nf, fill=(255, 255, 255), anchor="mm")
    # Rodapé: reservas
    d.rectangle([0, 1262, W, H], fill=(17, 24, 39))
    d.rectangle([0, 1262, W, 1266], fill=(212, 175, 55))
    d.text((50, 1296), "RESERVAS", font=_font(26), fill=(212, 175, 55), anchor="lm")
    if bench:
        names = "   •   ".join(f"{b['name']} ({b['position']})" for b in bench)
        line, y = "", 1336
        for word in names.split("   •   "):
            trial = word if not line else f"{line}   •   {word}"
            if d.textlength(trial, font=_font(24, False)) > 900 and line:
                d.text((50, y), line, font=_font(24, False), fill=(226, 232, 240), anchor="lm")
                line, y = word, y + 34
            else:
                line = trial
        if line and y < H - 10:
            d.text((50, y), line, font=_font(24, False), fill=(226, 232, 240), anchor="lm")
    else:
        d.text((50, 1336), "Nenhum reserva escalado", font=_font(24, False), fill=(148, 163, 184), anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def fetch_avatar_bytes(guild: Optional[discord.Guild], user_id: int) -> Optional[bytes]:
    user = guild.get_member(user_id) if guild else None
    user = user or bot.get_user(user_id)
    try:
        if user is None:
            user = await bot.fetch_user(user_id)
        return await user.display_avatar.replace(size=128, format="png").read()
    except Exception:
        return None


async def build_lineup_file(guild: discord.Guild, formation: Optional[str] = None) -> tuple:
    gid = guild.id
    formation = formation if formation in FORMATIONS else cfg_get(gid, "lineup_formation")
    if formation not in FORMATIONS:
        formation = "4-3-3"
    entries = lineup_entries(gid)
    slots, bench = assign_slots(formation, entries)
    show_avatars = cfg_get(gid, "lineup_avatars") != "0"
    avatars = {}
    if show_avatars:
        placed = [s["entry"] for s in slots if s["entry"]]
        results = await asyncio.gather(*(fetch_avatar_bytes(guild, e["user_id"]) for e in placed))
        avatars = {e["pid"]: data for e, data in zip(placed, results)}
    png = await asyncio.get_running_loop().run_in_executor(
        None, render_lineup_image, team_name_of(gid), formation, slots, bench, show_avatars,
        cfg_get(gid, "lineup_numbers") != "0", local_now(gid).strftime("%d/%m/%Y"), avatars)
    return discord.File(io.BytesIO(png), filename="escalacao.png"), formation, entries, bench


def lineup_embed(gid: int, formation: str, entries: list, bench: list) -> discord.Embed:
    emb = make_embed(gid, f"📋 Escalação • {formation}")
    if not entries:
        emb.description = "Nenhum jogador escalado ainda. Use `/escalar` para montar a escalação."
    else:
        emb.description = f"**{len(entries)}** jogador(es) escalado(s) • **{max(0, len(entries) - len(bench))}** em campo"
    emb.set_image(url="attachment://escalacao.png")
    return emb


async def send_lineup(interaction: discord.Interaction, formation: Optional[str] = None, *, ephemeral: bool = False) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
    file, formation, entries, bench = await build_lineup_file(interaction.guild, formation)
    await interaction.followup.send(embed=lineup_embed(interaction.guild_id, formation, entries, bench),
                                    file=file, ephemeral=ephemeral)


class PositionPickView(SafeView):
    def __init__(self, owner_id: int, callback: Callable[[discord.Interaction, str], Awaitable[None]],
                 placeholder: str = "Escolha a posição"):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=300)
        sel = discord.ui.Select(placeholder=placeholder, options=[
            discord.SelectOption(label=f"{k} — {v}", value=k) for k, v in POSITION_NAMES.items()])

        async def _cb(interaction: discord.Interaction):
            self._origin = None
            await callback(interaction, sel.values[0])

        sel.callback = _cb
        self.add_item(sel)


def lineup_panel_embed(gid: int) -> discord.Embed:
    entries = lineup_entries(gid)
    formation = cfg_get(gid, "lineup_formation")
    emb = make_embed(gid, "📋 Painel de escalação",
                     f"Formação atual: **{formation}**\nJogadores escalados: **{len(entries)}/{MAX_LINEUP}**")
    if entries:
        emb.add_field(name="Escalados", value=trunc("\n".join(
            f"`{e['position']:<3}` #{e['number']} **{e['name']}**" for e in entries), 1000), inline=False)
    return emb


class LineupPanelView(SafeView):
    def __init__(self, gid: int, owner_id: int, back: Optional[Callable] = None):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.gid = gid
        self.back = back
        sel = discord.ui.Select(placeholder="Formação…", row=0, options=[
            discord.SelectOption(label=f, value=f, default=(f == cfg_get(gid, "lineup_formation")))
            for f in FORMATIONS])
        sel.callback = self._on_formation
        self.add_item(sel)
        add_button(self, "Adicionar / alterar", self._add, emoji="➕", style=discord.ButtonStyle.success, row=1)
        add_button(self, "Remover", self._remove, emoji="➖", row=1)
        add_button(self, "Limpar", self._clear, emoji="🧹", style=discord.ButtonStyle.danger, row=1)
        add_button(self, "Importar confirmados", self._import, emoji="📥", row=1)
        add_button(self, "Ver imagem", self._image, emoji="🖼️", style=discord.ButtonStyle.primary, row=1)
        if back is not None:
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=2)

    async def _go_back(self, interaction: discord.Interaction):
        await self.back(interaction, self)

    async def _on_formation(self, interaction: discord.Interaction):
        require_staff(interaction)
        formation = interaction.data["values"][0]
        old = cfg_get(self.gid, "lineup_formation")
        cfg_set(self.gid, "lineup_formation", formation)
        await log_event(self.gid, interaction.user.id, "Escalação", "Formação alterada", before=old, after=formation)
        new_view = LineupPanelView(self.gid, self.owner_id, self.back)
        await switch_view(interaction, self, embed=lineup_panel_embed(self.gid), view=new_view)

    async def _add(self, interaction: discord.Interaction):
        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id, allow_inactive=False)

            async def chosen(i2: discord.Interaction, pos: str):
                require_staff(i2)
                set_lineup_player(self.gid, player, pos)
                await log_event(self.gid, i2.user.id, "Escalação", "Jogador escalado",
                                after=f"{player['name']} como {pos}")
                await i2.response.edit_message(embed=success_embed(
                    self.gid, "Escalação atualizada", f"**{player['name']}** escalado como **{pos}**."), view=None)

            view = PositionPickView(inter.user.id, chosen, f"Posição de {player['name']}"[:100])
            await inter.response.edit_message(embed=info_embed(self.gid, f"Posição de {player['name']}"), view=view)
            view.bind(inter)

        view = UserPickView(interaction.user.id, picked, placeholder="Quem será escalado?")
        await respond(interaction, embed=info_embed(self.gid, "Adicionar / alterar na escalação"), view=view)
        view.bind(interaction)

    async def _remove(self, interaction: discord.Interaction):
        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)
            n = db_one("SELECT COUNT(*) AS n FROM lineups WHERE guild_id=? AND player_id=?", (self.gid, player["id"]))["n"]
            if not n:
                raise UserError(f"**{player['name']}** não está na escalação.", "Fora da escalação")
            db_exec("DELETE FROM lineups WHERE guild_id=? AND player_id=?", (self.gid, player["id"]))
            await log_event(self.gid, inter.user.id, "Escalação", "Jogador removido da escalação", before=player["name"])
            await inter.response.edit_message(embed=success_embed(
                self.gid, "Removido da escalação", f"**{player['name']}** saiu da escalação."), view=None)

        view = UserPickView(interaction.user.id, picked, placeholder="Quem sai da escalação?")
        await respond(interaction, embed=info_embed(self.gid, "Remover da escalação"), view=view)
        view.bind(interaction)

    async def _clear(self, interaction: discord.Interaction):
        async def do_clear(inter: discord.Interaction):
            require_staff(inter)
            before = len(lineup_entries(self.gid))
            db_exec("DELETE FROM lineups WHERE guild_id=?", (self.gid,))
            await log_event(self.gid, inter.user.id, "Escalação", "Escalação limpa", before=f"{before} jogadores")
            await inter.response.edit_message(embed=success_embed(self.gid, "Escalação limpa"), view=None)

        view = ConfirmView(interaction.user.id, do_clear, confirm_label="Limpar escalação")
        await respond(interaction, embed=warn_embed(self.gid, "Limpar a escalação?",
                                                    "Todos os jogadores serão removidos da escalação."), view=view)
        view.bind(interaction)

    async def _import(self, interaction: discord.Interaction):
        require_staff(interaction)
        ids = confirmed_player_ids(self.gid)
        if not ids:
            raise UserError("Ninguém confirmou presença no último aviso de jogo.", "Sem confirmados")
        with db_tx() as c:
            c.execute("DELETE FROM lineups WHERE guild_id=?", (self.gid,))
            for pid in ids[:MAX_LINEUP]:
                p = get_player_by_id(pid)
                c.execute("INSERT INTO lineups (guild_id, player_id, position, added_at) VALUES (?,?,?,?)",
                          (self.gid, pid, p["position"], now_utc_iso()))
        await log_event(self.gid, interaction.user.id, "Escalação", "Escalação importada dos confirmados",
                        after=f"{min(len(ids), MAX_LINEUP)} jogadores")
        await switch_view(interaction, self, embed=lineup_panel_embed(self.gid),
                          view=LineupPanelView(self.gid, self.owner_id, self.back))

    async def _image(self, interaction: discord.Interaction):
        await send_lineup(interaction, ephemeral=True)


@tree.command(name="escalar", description="Monta a escalação (adiciona jogador/posição ou abre o painel).")
@app_commands.describe(jogador="Jogador a escalar", posicao="Posição em campo (padrão: a posição do jogador)")
@app_commands.rename(posicao="posição")
@app_commands.choices(posicao=POSITION_CHOICES)
@app_commands.guild_only()
@staff_only()
async def cmd_escalar(interaction: discord.Interaction, jogador: Optional[discord.Member] = None,
                      posicao: Optional[app_commands.Choice[str]] = None):
    gid = interaction.guild_id
    if jogador is None and posicao is not None:
        raise UserError("Informe também o jogador que ocupará essa posição.", "Jogador não informado")
    if jogador is not None:
        player = require_player(gid, jogador.id, allow_inactive=False)
        pos = posicao.value if posicao else player["position"]
        set_lineup_player(gid, player, pos)
        await log_event(gid, interaction.user.id, "Escalação", "Jogador escalado", after=f"{player['name']} como {pos}")
    view = LineupPanelView(gid, interaction.user.id)
    emb = lineup_panel_embed(gid)
    if jogador is not None:
        emb.title = f"✅ {player['name']} escalado como {pos}"
    await respond(interaction, embed=emb, view=view)
    view.bind(interaction)


@tree.command(name="escalação", description="Gera a imagem da escalação atual.")
@app_commands.describe(formacao="Pré-visualizar com outra formação (não altera a formação salva)")
@app_commands.choices(formacao=[app_commands.Choice(name=f, value=f) for f in FORMATIONS])
@app_commands.guild_only()
async def cmd_escalacao(interaction: discord.Interaction, formacao: Optional[app_commands.Choice[str]] = None):
    await send_lineup(interaction, formacao.value if formacao else None)


# ==============================
# PRESENÇA
# ==============================

PRESENCE_FIELD_NAME = "📋 Confirmação de presença"


def presence_lists(event_id: int) -> dict:
    out = {"vou": [], "nao": [], "talvez": []}
    for r in db_all("SELECT user_id, response FROM presence_responses WHERE event_id=? ORDER BY updated_at", (event_id,)):
        out.setdefault(r["response"], []).append(r["user_id"])
    return out


def presence_embeds(embeds_json: str, lists: dict, closed: bool = False) -> list:
    embeds = [discord.Embed.from_dict(d) for d in json.loads(embeds_json)]
    main = embeds[-1]
    kept = [f for f in main.fields if f.name != PRESENCE_FIELD_NAME]
    main.clear_fields()
    for f in kept:
        main.add_field(name=f.name, value=f.value, inline=f.inline)
    value = (f"✅ **{len(lists['vou'])}** confirmados\n❌ **{len(lists['nao'])}** não vão\n"
             f"🕐 **{len(lists['talvez'])}** talvez")
    if closed:
        value += "\n\n🔒 **Confirmação encerrada**"
    main.add_field(name=PRESENCE_FIELD_NAME, value=value, inline=False)
    return embeds


def pending_user_ids(gid: int, lists: dict) -> list:
    answered = set(lists["vou"]) | set(lists["nao"]) | set(lists["talvez"])
    return [r["user_id"] for r in db_all(
        "SELECT user_id FROM players WHERE guild_id=? AND status IN ('ativo','reserva') ORDER BY number", (gid,))
        if r["user_id"] not in answered]


class PresencaView(discord.ui.View):
    """Botões de presença (persistentes: continuam funcionando após reiniciar o bot)."""

    def __init__(self, closed: bool = False, links: Optional[list] = None):
        super().__init__(timeout=None)
        if closed:
            self.btn_vou.disabled = self.btn_nao.disabled = self.btn_talvez.disabled = True
            self.btn_fechar.disabled = True
        for label, url in (links or [])[:5]:
            self.add_item(discord.ui.Button(label=trunc(label, 80), url=url, style=discord.ButtonStyle.link, row=1))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        await handle_error(interaction, error)

    @staticmethod
    def _event(interaction: discord.Interaction):
        ev = db_one("SELECT * FROM presence_events WHERE message_id=?", (interaction.message.id,))
        if ev is None:
            raise UserError("Esta confirmação de presença não está mais registrada no banco de dados.",
                            "Confirmação não encontrada")
        return ev

    async def _answer(self, interaction: discord.Interaction, response: str) -> None:
        gid = interaction.guild_id
        ev = self._event(interaction)
        if not ev["is_open"]:
            raise UserError("O administrador já encerrou a confirmação de presença deste jogo.", "Confirmação encerrada")
        player = get_player(gid, interaction.user.id)
        if player is None or player["status"] == "inativo":
            raise UserError("Você não está cadastrado no elenco. Peça a um administrador para cadastrá-lo "
                            "com `/jogador adicionar`.", "Você não é jogador")
        if player["status"] == "suspenso":
            raise UserError("Jogadores suspensos não podem confirmar presença.", "Jogador suspenso")
        db_exec("INSERT INTO presence_responses (event_id, user_id, response, updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(event_id, user_id) DO UPDATE SET response=excluded.response, updated_at=excluded.updated_at",
                (ev["id"], interaction.user.id, response, now_utc_iso()))
        embeds = presence_embeds(ev["embeds_json"], presence_lists(ev["id"]))
        await interaction.response.edit_message(embeds=embeds)

    @discord.ui.button(label="Vou", emoji="✅", style=discord.ButtonStyle.success, custom_id="mps:pres:vou", row=0)
    async def btn_vou(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "vou")

    @discord.ui.button(label="Não vou", emoji="❌", style=discord.ButtonStyle.danger, custom_id="mps:pres:nao", row=0)
    async def btn_nao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "nao")

    @discord.ui.button(label="Talvez", emoji="🕐", style=discord.ButtonStyle.secondary, custom_id="mps:pres:talvez", row=0)
    async def btn_talvez(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "talvez")

    @discord.ui.button(label="Ver jogadores", emoji="👥", style=discord.ButtonStyle.primary,
                       custom_id="mps:pres:ver", row=0)
    async def btn_ver(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        ev = self._event(interaction)
        lists = presence_lists(ev["id"])
        emb = make_embed(gid, f"👥 {trunc(ev['title'] or 'Jogadores', 200)}")
        emb.add_field(name=f"✅ Confirmaram ({len(lists['vou'])})", value=trunc(mention_list(lists["vou"], 40), 1000), inline=False)
        emb.add_field(name=f"❌ Não vão ({len(lists['nao'])})", value=trunc(mention_list(lists["nao"], 40), 1000), inline=False)
        emb.add_field(name=f"🕐 Talvez ({len(lists['talvez'])})", value=trunc(mention_list(lists["talvez"], 40), 1000), inline=False)
        pending = pending_user_ids(gid, lists)
        emb.add_field(name=f"⏳ Ainda não responderam ({len(pending)})", value=trunc(mention_list(pending, 40), 1000), inline=False)
        if not ev["is_open"]:
            emb.set_footer(text="🔒 Confirmação encerrada")
        await respond(interaction, embed=emb, allowed_mentions=discord.AllowedMentions.none())

    @discord.ui.button(label="Encerrar", emoji="🔒", style=discord.ButtonStyle.secondary,
                       custom_id="mps:pres:fechar", row=0)
    async def btn_fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        require_staff(interaction)  # permissão verificada no backend
        gid = interaction.guild_id
        ev = self._event(interaction)
        if not ev["is_open"]:
            raise UserError("Esta confirmação já foi encerrada.", "Já encerrada")
        db_exec("UPDATE presence_events SET is_open=0 WHERE id=?", (ev["id"],))
        links = json.loads(ev["links_json"] or "[]")
        lists = presence_lists(ev["id"])
        await interaction.response.edit_message(embeds=presence_embeds(ev["embeds_json"], lists, closed=True),
                                                view=PresencaView(closed=True, links=links))
        await log_event(gid, interaction.user.id, "Presença", "Confirmação encerrada",
                        after=f"{ev['title']} • ✅{len(lists['vou'])} ❌{len(lists['nao'])} 🕐{len(lists['talvez'])}")


async def publish_message(guild: discord.Guild, channel: discord.abc.Messageable, *, embeds: list,
                          content: Optional[str] = None, links: Optional[list] = None, presence: bool = False,
                          game_id: Optional[int] = None, actor_id: Optional[int] = None,
                          allowed_mentions: Optional[discord.AllowedMentions] = None) -> discord.Message:
    """Envia um anúncio; se `presence` estiver ativo, registra a confirmação de presença."""
    links = links or []
    kwargs: dict = {"embeds": embeds}
    if content:
        kwargs["content"] = content
    if allowed_mentions is not None:
        kwargs["allowed_mentions"] = allowed_mentions
    if presence:
        base_json = json.dumps([e.to_dict() for e in embeds])
        kwargs["embeds"] = presence_embeds(base_json, {"vou": [], "nao": [], "talvez": []})
        kwargs["view"] = PresencaView(links=links)
    elif links:
        view = discord.ui.View(timeout=None)
        for label, url in links[:5]:
            view.add_item(discord.ui.Button(label=trunc(label, 80), url=url, style=discord.ButtonStyle.link))
        kwargs["view"] = view
    msg = await channel.send(**kwargs)
    if presence:
        db_exec("INSERT INTO presence_events (guild_id, channel_id, message_id, game_id, title, embeds_json, links_json, "
                "is_open, created_by, created_at) VALUES (?,?,?,?,?,?,?,1,?,?)",
                (guild.id, channel.id, msg.id, game_id, embeds[-1].title or "Jogo", base_json,
                 json.dumps(links), actor_id, now_utc_iso()))
    return msg


def game_description(gid: int, game: dict, presence: bool) -> str:
    lines = [f"**{team_name_of(gid)} x {game.get('opponent') or '???'}**", ""]
    if game.get("date"):
        lines.append(f"📅 {fmt_date(game['date'])}")
    lines.append(f"🕐 {game.get('time') or 'A definir'}")
    if game.get("competition"):
        lines.append(f"🏆 {game['competition']}")
    if game.get("location"):
        lines.append(f"📍 {game['location']}")
    if game.get("notes"):
        lines += ["", f"📝 {game['notes']}"]
    if presence:
        lines += ["", "Confirme sua presença:"]
    return "\n".join(lines)


async def post_game_announcement(guild: discord.Guild, channel: discord.abc.Messageable, game, actor_id: int):
    """Publica o 'aviso de jogo' do calendário já com confirmação de presença."""
    gid = guild.id
    data = {"opponent": game["opponent"], "date": game["game_date"], "time": game["game_time"],
            "competition": game["competition"], "location": game["location"], "notes": game["notes"]}
    emb = make_embed(gid, "🏆 JOGO MARCADO", game_description(gid, data, True), 0xF1C40F)
    logo = cfg_get(gid, "logo_url").strip()
    if logo.startswith("http"):
        emb.set_thumbnail(url=logo)
    mentions = ""
    pr = cfg_int(gid, "player_role")
    if pr:
        mentions = f"<@&{pr}>"
    msg = await publish_message(guild, channel, embeds=[emb], content=mentions or None, presence=True,
                                game_id=game["id"], actor_id=actor_id,
                                allowed_mentions=discord.AllowedMentions(roles=True))
    await log_event(gid, actor_id, "Presença", "Aviso de jogo publicado",
                    after=f"{game['opponent']} • {fmt_date(game['game_date'])} • {msg.jump_url}")
    return msg


# ==============================
# /SAY
# ==============================

SAY_TEMPLATES = {
    "aviso": ("📢 Aviso normal", "📢 AVISO", 0x3B82F6),
    "jogo": ("🏆 Aviso de jogo", "🏆 JOGO MARCADO", 0xF1C40F),
    "calendario": ("📅 Calendário", "📅 CALENDÁRIO DE JOGOS", 0x2ECC71),
    "convocacao": ("📋 Convocação", "📋 CONVOCAÇÃO", 0x9B59B6),
    "resultado": ("📊 Resultado", "📊 ÚLTIMO RESULTADO", 0xE67E22),
    "comunicado": ("📣 Comunicado", "📣 COMUNICADO", 0xE74C3C),
}


class SayDraft:
    def __init__(self, channel_id: Optional[int]):
        self.template = "aviso"
        self.channel_id = channel_id
        self.title = SAY_TEMPLATES["aviso"][1]
        self.description = ""
        self.color: int = SAY_TEMPLATES["aviso"][2]
        self.image = self.banner = self.thumbnail = self.footer = self.author = ""
        self.timestamp = False
        self.role_ids: list = []
        self.everyone = False
        self.links: list = []
        self.presence = True
        self.ping_users: list = []
        self.game: dict = {"opponent": "", "date": "", "time": "", "competition": "", "location": "",
                           "notes": "", "game_id": None}


def apply_say_template(gid: int, d: SayDraft, key: str) -> None:
    d.template = key
    d.title, d.color = SAY_TEMPLATES[key][1], SAY_TEMPLATES[key][2]
    d.description, d.ping_users = "", []
    if key == "jogo":
        if not d.game["opponent"]:
            ng = upcoming_games(gid, 1)
            if ng:
                g = ng[0]
                d.game = {"opponent": g["opponent"], "date": g["game_date"], "time": g["game_time"] or "",
                          "competition": g["competition"] or "", "location": g["location"] or "",
                          "notes": g["notes"] or "", "game_id": g["id"]}
        d.description = game_description(gid, d.game, d.presence) if d.game["opponent"] else \
            "Use o botão **Dados do jogo** para preencher adversário, data e horário."
    elif key == "calendario":
        games = upcoming_games(gid, 8)
        d.description = ("\n\n".join(format_game(g) for g in games) if games
                         else "Nenhum jogo agendado no momento.")
    elif key == "convocacao":
        ids = lineup_player_ids(gid) or [p["id"] for p in list_players(gid, "ativo")]
        players = [p for p in (get_player_by_id(i) for i in ids) if p]
        lines = ["Os seguintes jogadores estão **convocados**:", ""]
        lines += [f"`{p['position']:<3}` <@{p['user_id']}> #{p['number']}" for p in players] or ["_Nenhum jogador disponível._"]
        ng = upcoming_games(gid, 1)
        if ng:
            lines += ["", f"🆚 **{ng[0]['opponent']}** — 📅 {fmt_date(ng[0]['game_date'])}"
                          + (f" 🕐 {ng[0]['game_time']}" if ng[0]["game_time"] else "")]
        d.description = "\n".join(lines)
        d.ping_users = [p["user_id"] for p in players][:40]
    elif key == "resultado":
        m = db_one("SELECT * FROM matches WHERE guild_id=? ORDER BY played_date DESC, id DESC LIMIT 1", (gid,))
        if m:
            bd = match_breakdown(m["id"])
            lines = [f"## {team_name_of(gid).upper()} {m['our_score']} × {m['opp_score']} {m['opponent'].upper()}",
                     RESULT_LABELS[m["result"]][0]]
            if bd["goals"]:
                lines.append("⚽ " + ", ".join(f"{n} ({q})" if q > 1 else n for n, q in bd["goals"]))
            if bd["assists"]:
                lines.append("🅰️ " + ", ".join(f"{n} ({q})" if q > 1 else n for n, q in bd["assists"]))
            if bd["mvp"]:
                lines.append(f"🏅 MVP: **{bd['mvp']}**")
            lines.append(f"📅 {fmt_date(m['played_date'])}" + (f" • 🏆 {m['competition']}" if m["competition"] else ""))
            d.description = "\n".join(lines)
        else:
            d.description = "Nenhum resultado registrado ainda."


def valid_url(url: str, label: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://\S+$", u):
        raise UserError(f"O link de **{label}** precisa começar com `http://` ou `https://`.", "Link inválido")
    return u


def build_say_embeds(gid: int, d: SayDraft, preview: bool = False) -> list:
    main = discord.Embed(title=trunc(d.title, 256) or None, description=trunc(d.description, 4000) or None, color=d.color)
    if preview and not main.title and not main.description:
        main.description = "_Sem conteúdo ainda — use o botão **Conteúdo**._"
    if d.author:
        main.set_author(name=trunc(d.author, 256))
    footer = d.footer or cfg_get(gid, "footer").strip()
    if footer:
        main.set_footer(text=trunc(footer, 2000))
    if d.timestamp:
        main.timestamp = datetime.now(timezone.utc)
    if d.image:
        main.set_image(url=d.image)
    thumb = d.thumbnail or (cfg_get(gid, "logo_url").strip() if d.template == "jogo" else "")
    if thumb.startswith("http"):
        main.set_thumbnail(url=thumb)
    embeds = [main]
    if d.banner:
        embeds.insert(0, discord.Embed(color=d.color).set_image(url=d.banner))
    if d.template == "jogo" and d.presence:
        embeds = presence_embeds(json.dumps([e.to_dict() for e in embeds]), {"vou": [], "nao": [], "talvez": []})
    return embeds


class SayContentModal(SafeModal):
    def __init__(self, view: "SayBuilder"):
        super().__init__(title="Conteúdo do anúncio", timeout=600)
        self.v = view
        d = view.d
        self.f_title = discord.ui.TextInput(label="Título", required=False, max_length=256, default=d.title or None)
        self.f_desc = discord.ui.TextInput(label="Descrição", required=False, max_length=4000,
                                           style=discord.TextStyle.paragraph, default=d.description or None)
        self.f_color = discord.ui.TextInput(label="Cor (#hex ou nome)", required=False, max_length=20,
                                            default=f"#{d.color:06X}", placeholder="#FFD700, azul, verde...")
        self.f_author = discord.ui.TextInput(label="Autor", required=False, max_length=100, default=d.author or None)
        self.f_footer = discord.ui.TextInput(label="Rodapé", required=False, max_length=200, default=d.footer or None)
        for item in (self.f_title, self.f_desc, self.f_color, self.f_author, self.f_footer):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.v.d
        color = parse_color(self.f_color.value, d.color)
        d.title, d.description = self.f_title.value.strip(), self.f_desc.value.strip()
        d.color, d.author, d.footer = color, self.f_author.value.strip(), self.f_footer.value.strip()
        await self.v.refresh(interaction)


class SayImagesModal(SafeModal):
    def __init__(self, view: "SayBuilder"):
        super().__init__(title="Imagens do anúncio", timeout=600)
        self.v = view
        d = view.d
        self.f_image = discord.ui.TextInput(label="Imagem grande (URL)", required=False, max_length=500, default=d.image or None)
        self.f_banner = discord.ui.TextInput(label="Banner no topo (URL)", required=False, max_length=500, default=d.banner or None)
        self.f_thumb = discord.ui.TextInput(label="Thumbnail (URL)", required=False, max_length=500, default=d.thumbnail or None)
        for item in (self.f_image, self.f_banner, self.f_thumb):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.v.d
        d.image = valid_url(self.f_image.value, "imagem")
        d.banner = valid_url(self.f_banner.value, "banner")
        d.thumbnail = valid_url(self.f_thumb.value, "thumbnail")
        await self.v.refresh(interaction)


class SayLinksModal(SafeModal):
    def __init__(self, view: "SayBuilder"):
        super().__init__(title="Botões de link", timeout=600)
        self.v = view
        current = "\n".join(f"{a} | {b}" for a, b in view.d.links)
        self.f_links = discord.ui.TextInput(label="Um por linha: Texto | https://link", required=False, max_length=900,
                                            style=discord.TextStyle.paragraph, default=current or None,
                                            placeholder="Servidor do jogo | https://roblox.com/...")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        links = []
        for line in self.f_links.value.splitlines():
            if not line.strip():
                continue
            if "|" not in line:
                raise UserError(f"Linha inválida: `{trunc(line, 60)}`. Use `Texto | https://link`.", "Botão inválido")
            label, url = line.split("|", 1)
            label = label.strip()
            if not label:
                raise UserError("Todo botão precisa de um texto antes do `|`.", "Botão inválido")
            links.append((label[:80], valid_url(url, label)))
        if len(links) > 5:
            raise UserError("Máximo de 5 botões de link por anúncio.", "Botões demais")
        self.v.d.links = links
        await self.v.refresh(interaction)


class SayGameModal(SafeModal):
    def __init__(self, view: "SayBuilder"):
        super().__init__(title="Dados do jogo", timeout=600)
        self.v = view
        g = view.d.game
        dt = f"{fmt_date(g['date'])} {g['time']}".strip() if g["date"] else None
        self.f_opp = discord.ui.TextInput(label="Adversário", max_length=60, default=g["opponent"] or None)
        self.f_dt = discord.ui.TextInput(label="Data e horário", max_length=20, default=dt,
                                         placeholder="dd/mm/aaaa HH:MM  (ex.: 02/10/2026 20:00)")
        self.f_comp = discord.ui.TextInput(label="Competição", required=False, max_length=60, default=g["competition"] or None)
        self.f_loc = discord.ui.TextInput(label="Canal / local", required=False, max_length=80, default=g["location"] or None)
        self.f_notes = discord.ui.TextInput(label="Observações", required=False, max_length=300,
                                            style=discord.TextStyle.paragraph, default=g["notes"] or None)
        for item in (self.f_opp, self.f_dt, self.f_comp, self.f_loc, self.f_notes):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        gid = interaction.guild_id
        d = self.v.d
        date_iso, time_str = parse_datetime_br(self.f_dt.value, gid)
        old = d.game
        same = (old.get("game_id") and old["opponent"].lower() == self.f_opp.value.strip().lower()
                and old["date"] == date_iso and old["time"] == time_str)
        d.game = {"opponent": self.f_opp.value.strip(), "date": date_iso, "time": time_str,
                  "competition": self.f_comp.value.strip(), "location": self.f_loc.value.strip(),
                  "notes": self.f_notes.value.strip(), "game_id": old.get("game_id") if same else None}
        d.description = game_description(gid, d.game, d.presence)
        await self.v.refresh(interaction)


class SayBuilder(SafeView):
    """Construtor de anúncios com pré-visualização ao vivo."""

    def __init__(self, gid: int, owner_id: int, channel_id: Optional[int]):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=900)
        self.gid = gid
        self.d = SayDraft(channel_id)
        self.finished = False
        self.render()

    def summary(self) -> str:
        d = self.d
        ch = f"<#{d.channel_id}>" if d.channel_id else "_não escolhido_"
        roles = " ".join(f"<@&{r}>" for r in d.role_ids) or "—"
        extra = " + @everyone" if d.everyone else ""
        pres = ""
        if d.template == "jogo":
            pres = f"\n**Presença:** {'☑️ ativada' if d.presence else '⬜ desativada'}"
        return (f"**Modelo:** {SAY_TEMPLATES[d.template][0]}\n**Canal:** {ch}\n"
                f"**Menções:** {roles}{extra}{pres}\n_Pré-visualização abaixo:_")

    def render(self) -> None:
        self.clear_items()
        d = self.d
        sel = discord.ui.Select(placeholder="Modelo do anúncio", row=0, options=[
            discord.SelectOption(label=v[0].split(" ", 1)[1], value=k, emoji=v[0].split(" ", 1)[0], default=(k == d.template))
            for k, v in SAY_TEMPLATES.items()])
        sel.callback = self._on_template
        self.add_item(sel)
        chsel = discord.ui.ChannelSelect(placeholder="Canal de destino", row=1, min_values=1, max_values=1,
                                         channel_types=[discord.ChannelType.text, discord.ChannelType.news])
        chsel.callback = self._on_channel
        self.add_item(chsel)
        rsel = discord.ui.RoleSelect(placeholder="Cargos para mencionar (opcional)", row=2, min_values=0, max_values=5)
        rsel.callback = self._on_roles
        self.add_item(rsel)
        add_button(self, "Conteúdo", self._content, emoji="✏️", row=3)
        add_button(self, "Imagens", self._images, emoji="🖼️", row=3)
        add_button(self, "Links", self._links, emoji="🔗", row=3)
        add_button(self, "Timestamp", self._toggle_ts, emoji="🕒", row=3,
                   style=discord.ButtonStyle.success if d.timestamp else discord.ButtonStyle.secondary)
        add_button(self, "Enviar", self._send, emoji="📤", style=discord.ButtonStyle.success, row=4)
        add_button(self, "Cancelar", self._cancel, emoji="✖️", style=discord.ButtonStyle.danger, row=4)
        add_button(self, "@everyone", self._toggle_everyone, emoji="📢", row=4,
                   style=discord.ButtonStyle.success if d.everyone else discord.ButtonStyle.secondary)
        if d.template == "jogo":
            add_button(self, "Dados do jogo", self._game, emoji="📅", row=4)
            add_button(self, "Presença", self._toggle_presence, emoji="☑️" if d.presence else "⬜", row=4,
                       style=discord.ButtonStyle.success if d.presence else discord.ButtonStyle.secondary)

    async def refresh(self, interaction: discord.Interaction) -> None:
        self.render()
        await edit_message(interaction, content=self.summary(), embeds=build_say_embeds(self.gid, self.d, True), view=self)

    async def _on_template(self, interaction: discord.Interaction):
        apply_say_template(self.gid, self.d, interaction.data["values"][0])
        await self.refresh(interaction)

    async def _on_channel(self, interaction: discord.Interaction):
        self.d.channel_id = int(interaction.data["values"][0])
        await self.refresh(interaction)

    async def _on_roles(self, interaction: discord.Interaction):
        self.d.role_ids = [int(v) for v in interaction.data["values"]]
        await self.refresh(interaction)

    async def _content(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayContentModal(self))

    async def _images(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayImagesModal(self))

    async def _links(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayLinksModal(self))

    async def _game(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SayGameModal(self))

    async def _toggle_ts(self, interaction: discord.Interaction):
        self.d.timestamp = not self.d.timestamp
        await self.refresh(interaction)

    async def _toggle_everyone(self, interaction: discord.Interaction):
        self.d.everyone = not self.d.everyone
        await self.refresh(interaction)

    async def _toggle_presence(self, interaction: discord.Interaction):
        d = self.d
        d.presence = not d.presence
        if d.game["opponent"]:
            d.description = game_description(self.gid, d.game, d.presence)
        await self.refresh(interaction)

    async def _cancel(self, interaction: discord.Interaction):
        self.finished = True
        self.stop()
        await interaction.response.edit_message(content=None, embeds=[info_embed(
            self.gid, "Anúncio cancelado", "Nada foi enviado.")], view=None)

    async def _send(self, interaction: discord.Interaction):
        require_staff(interaction)
        gid, d = self.gid, self.d
        if self.finished:
            raise UserError("Este anúncio já foi enviado.", "Já enviado")
        guild = interaction.guild
        channel = guild.get_channel(d.channel_id) if d.channel_id else None
        if channel is None or not hasattr(channel, "send"):
            raise UserError("Escolha o **canal de destino** no menu antes de enviar.", "Canal não escolhido")
        if not d.title and not d.description and not d.image:
            raise UserError("O anúncio está vazio. Use o botão **Conteúdo** para escrever algo.", "Anúncio vazio")
        if d.template == "jogo" and d.presence and not d.game["opponent"]:
            raise UserError("Preencha os **Dados do jogo** antes de enviar o aviso com presença.", "Dados do jogo")
        perms = channel.permissions_for(guild.me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            raise UserError(f"O bot precisa das permissões **Ver canal, Enviar mensagens e Inserir links** em "
                            f"{channel.mention}.", "Permissão do bot")
        parts = []
        if d.everyone:
            parts.append("@everyone")
        parts += [f"<@&{r}>" for r in d.role_ids]
        parts += [f"<@{u}>" for u in d.ping_users]
        content = trunc(" ".join(parts), 1900, "") or None
        mentions = discord.AllowedMentions(everyone=d.everyone, roles=[discord.Object(id=r) for r in d.role_ids],
                                           users=[discord.Object(id=u) for u in d.ping_users])
        use_presence = d.template == "jogo" and d.presence
        embeds = build_say_embeds(gid, d)
        if use_presence:  # remove contadores: o publish_message adiciona os atuais
            embeds = [discord.Embed.from_dict(e.to_dict()) for e in embeds]
            embeds[-1].clear_fields()
        self.finished = True
        self.stop()
        msg = await publish_message(guild, channel, embeds=embeds, content=content, links=d.links, presence=use_presence,
                                    game_id=d.game.get("game_id") if use_presence else None,
                                    actor_id=interaction.user.id, allowed_mentions=mentions)
        await log_event(gid, interaction.user.id, "Comunicação", f"Anúncio enviado ({SAY_TEMPLATES[d.template][0]})",
                        after=f"{trunc(d.title or d.description, 120)} • {msg.jump_url}")
        await interaction.response.edit_message(content=None, embeds=[success_embed(
            gid, "Anúncio enviado", f"Publicado em {channel.mention}.\n[Abrir mensagem]({msg.jump_url})"
            + ("\n☑️ Confirmação de presença ativada." if use_presence else ""))], view=None)


@tree.command(name="say", description="Cria e envia anúncios personalizados (administração).")
@app_commands.guild_only()
@staff_only()
async def cmd_say(interaction: discord.Interaction):
    ch = interaction.channel
    channel_id = ch.id if isinstance(ch, (discord.TextChannel, discord.Thread)) else None
    view = SayBuilder(interaction.guild_id, interaction.user.id, channel_id)
    await respond(interaction, content=view.summary(), embeds=build_say_embeds(interaction.guild_id, view.d, True), view=view)
    view.bind(interaction)


# ==============================
# /PERFIL
# ==============================

def profile_embed(gid: int, player, avatar_url: str) -> discord.Embed:
    st = stats_row(gid, player["id"])
    rank = st["rank"]
    emb = make_embed(gid, player["name"].upper(), color=RANK_COLORS[rank])
    emb.description = (
        f"`#{player['number']} • {player['position']}` · {STATUS_LABELS[player['status']]}\n\n"
        f"## {RANK_ICONS[rank]} RANK {rank}\n"
        f"Pontuação: **{fmt_num(st['score'])}**\n\n"
        f"⚽ **{st['goals']}** Gols\n"
        f"🅰️ **{st['assists']}** Assistências\n"
        f"🏟️ **{st['games']}** Jogos\n"
        f"✅ **{st['wins']}** Vitórias\n"
        f"➖ **{st['draws']}** Empates\n"
        f"❌ **{st['losses']}** Derrotas\n"
        f"🏅 **{st['mvps']}** MVPs\n\n"
        f"Aproveitamento: **{fmt_pct(st['winrate'])}**\n{progress_bar(st['winrate'])}")
    emb.set_thumbnail(url=avatar_url)
    return emb


def stats_embed(gid: int, player, avatar_url: str) -> discord.Embed:
    st = stats_row(gid, player["id"])
    w = rank_weights(gid)
    emb = make_embed(gid, f"📊 Estatísticas • {player['name']}", color=RANK_COLORS[st["rank"]])
    emb.set_thumbnail(url=avatar_url)
    emb.add_field(name="⚽ Gols por jogo", value=f"**{st['gpg']:.2f}**".replace(".", ","), inline=True)
    emb.add_field(name="🅰️ Assistências por jogo", value=f"**{st['apg']:.2f}**".replace(".", ","), inline=True)
    emb.add_field(name="🎯 Participações em gols", value=f"**{st['participations']}**", inline=True)
    emb.add_field(name="✅ Vitórias", value=f"**{st['wins']}**", inline=True)
    emb.add_field(name="➖ Empates", value=f"**{st['draws']}**", inline=True)
    emb.add_field(name="❌ Derrotas", value=f"**{st['losses']}**", inline=True)
    emb.add_field(name="📈 Aproveitamento", value=f"**{fmt_pct(st['winrate'])}**\n{progress_bar(st['winrate'])}", inline=True)
    emb.add_field(name="🏅 MVPs", value=f"**{st['mvps']}**", inline=True)
    emb.add_field(name="🏟️ Jogos", value=f"**{st['games']}**", inline=True)
    emb.add_field(
        name=f"🧮 Pontuação: {fmt_num(st['score'])} • Rank {st['rank']}",
        value=(f"Gols {st['goals']}×{fmt_num(w['goals'])} = {fmt_num(st['goals'] * w['goals'])}\n"
               f"Assist. {st['assists']}×{fmt_num(w['assists'])} = {fmt_num(st['assists'] * w['assists'])}\n"
               f"Vitórias {st['wins']}×{fmt_num(w['wins'])} = {fmt_num(st['wins'] * w['wins'])}\n"
               f"MVPs {st['mvps']}×{fmt_num(w['mvps'])} = {fmt_num(st['mvps'] * w['mvps'])}"), inline=False)
    return emb


def build_player_history_pages(gid: int, player, per_page: int = 5) -> list:
    rows = db_all(
        "SELECT m.*, COALESCE((SELECT SUM(amount) FROM goals WHERE match_id=m.id AND player_id=?),0) AS g, "
        "COALESCE((SELECT SUM(amount) FROM assists WHERE match_id=m.id AND player_id=?),0) AS a "
        "FROM matches m JOIN match_players mp ON mp.match_id=m.id AND mp.player_id=? "
        "WHERE m.guild_id=? ORDER BY m.played_date DESC, m.id DESC LIMIT 100",
        (player["id"], player["id"], player["id"], gid))
    title = f"📜 Histórico • {player['name']}"
    if not rows:
        return [info_embed(gid, title, "Este jogador ainda não disputou nenhuma partida registrada.")]
    pages = []
    for group in chunk(rows, per_page):
        blocks = []
        for m in group:
            _, _, res_name, emoji = RESULT_LABELS[m["result"]]
            line2 = f"⚽ {m['g']} gol(s) · 🅰️ {m['a']} assist. · " + ("🏅 **MVP**" if m["mvp_player_id"] == player["id"] else "sem MVP")
            blocks.append(f"{emoji} **vs {m['opponent']}** — **{m['our_score']} × {m['opp_score']}** ({res_name})\n"
                          f"{line2}\n📅 {fmt_date(m['played_date'])}"
                          + (f" · 🏆 {m['competition']}" if m["competition"] else ""))
        pages.append(info_embed(gid, title, "\n\n".join(blocks)))
    return pages


def achievements_embed(gid: int, player) -> discord.Embed:
    metrics = get_metrics(gid, player["id"])
    unlocked = {r["code"]: r["unlocked_at"] for r in db_all(
        "SELECT code, unlocked_at FROM achievements WHERE guild_id=? AND player_id=?", (gid, player["id"]))}
    emb = make_embed(gid, f"🏆 Conquistas • {player['name']}")
    emb.description = f"Desbloqueadas: **{len(unlocked)}/{len(ACHIEVEMENTS)}**"
    have, lock = [], []
    for code, emoji, name, desc, metric, target in ACHIEVEMENTS:
        if code in unlocked:
            have.append(f"{emoji} **{name}** — {desc}\n└ desbloqueada em {fmt_date(unlocked[code])}")
        else:
            lock.append(f"🔒 **{name}** — {desc}\n└ progresso: {min(metrics.get(metric, 0), target)}/{target}")
    emb.add_field(name="✅ Desbloqueadas", value=trunc("\n".join(have), 1000) if have else "Nenhuma ainda.", inline=False)
    if lock:
        emb.add_field(name="🔒 Bloqueadas", value=trunc("\n".join(lock), 1000), inline=False)
    return emb


class ProfileView(SafeView):
    def __init__(self, gid: int, owner_id: int, player_id: int, avatar_url: str):
        super().__init__(owner_id=owner_id, timeout=300)
        self.gid, self.pid, self.avatar_url = gid, player_id, avatar_url
        self.page, self.hist, self.hi = "perfil", [], 0
        self.render()

    def embed(self) -> discord.Embed:
        player = get_player_by_id(self.pid)
        if self.page == "stats":
            return stats_embed(self.gid, player, self.avatar_url)
        if self.page == "historico":
            emb = self.hist[self.hi].copy()
            emb.set_footer(text=f"Página {self.hi + 1}/{len(self.hist)}")
            return emb
        if self.page == "conquistas":
            return achievements_embed(self.gid, player)
        return profile_embed(self.gid, player, self.avatar_url)

    def render(self) -> None:
        self.clear_items()
        for key, label, emoji in (("perfil", "Perfil", "👤"), ("stats", "Estatísticas", "📊"),
                                  ("historico", "Histórico", "📜"), ("conquistas", "Conquistas", "🏆")):
            async def cb(interaction: discord.Interaction, key=key):
                await self._show(interaction, key)
            add_button(self, label, cb, emoji=emoji, row=0,
                       style=discord.ButtonStyle.primary if self.page == key else discord.ButtonStyle.secondary)
        if self.page == "historico" and len(self.hist) > 1:
            add_button(self, None, self._prev, emoji="◀️", row=1, disabled=self.hi == 0)
            add_button(self, f"{self.hi + 1}/{len(self.hist)}", self._noop, row=1, disabled=True)
            add_button(self, None, self._next, emoji="▶️", row=1, disabled=self.hi >= len(self.hist) - 1)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def _show(self, interaction: discord.Interaction, page: str):
        self.page = page
        if page == "historico":
            self.hist = build_player_history_pages(self.gid, get_player_by_id(self.pid))
            self.hi = 0
        self.render()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def _prev(self, interaction: discord.Interaction):
        self.hi = max(0, self.hi - 1)
        self.render()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def _next(self, interaction: discord.Interaction):
        self.hi = min(len(self.hist) - 1, self.hi + 1)
        self.render()
        await interaction.response.edit_message(embed=self.embed(), view=self)


@tree.command(name="perfil", description="Mostra o perfil de um jogador.")
@app_commands.describe(usuario="Jogador (padrão: você mesmo)")
@app_commands.guild_only()
async def cmd_perfil(interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
    gid = interaction.guild_id
    target = usuario or interaction.user
    player = get_player(gid, target.id)
    if player is None:
        who = "Você ainda não está" if target.id == interaction.user.id else f"{target.mention} não está"
        raise UserError(f"{who} cadastrado no elenco. A administração pode cadastrar com `/jogador adicionar`.",
                        "Perfil não encontrado")
    view = ProfileView(gid, interaction.user.id, player["id"], target.display_avatar.url)
    await respond(interaction, embed=view.embed(), view=view, ephemeral=False)
    view.bind(interaction)


# ==============================
# /TIME
# ==============================

def team_stats(gid: int) -> dict:
    ms = db_all("SELECT * FROM matches WHERE guild_id=? ORDER BY played_date, id", (gid,))
    games = len(ms)
    wins = sum(1 for m in ms if m["result"] == "V")
    draws = sum(1 for m in ms if m["result"] == "E")
    losses = sum(1 for m in ms if m["result"] == "D")
    gf = sum(m["our_score"] for m in ms) + (db_one(
        "SELECT COALESCE(SUM(amount),0) AS n FROM goals WHERE guild_id=? AND match_id IS NULL", (gid,))["n"])
    ga = sum(m["opp_score"] for m in ms)
    assists = db_one("SELECT COALESCE(SUM(amount),0) AS n FROM assists WHERE guild_id=?", (gid,))["n"]
    best = max(ms, key=lambda m: (m["our_score"] - m["opp_score"], m["our_score"]), default=None)
    streak = cur = 0
    for m in ms:
        cur = cur + 1 if m["result"] == "V" else 0
        streak = max(streak, cur)

    def top(col: str):
        r = db_one(f"SELECT p.name, s.{col} AS n FROM player_stats s JOIN players p ON p.id=s.player_id "
                   f"WHERE s.guild_id=? AND s.{col}>0 ORDER BY s.{col} DESC, p.name LIMIT 1", (gid,))
        return (r["name"], r["n"]) if r else None

    return {"games": games, "wins": wins, "draws": draws, "losses": losses, "gf": gf, "ga": ga,
            "assists": assists, "winrate": calc_winrate(wins, draws, games), "scorer": top("goals"),
            "assister": top("assists"), "mvp": top("mvps"), "clean": sum(1 for m in ms if m["opp_score"] == 0),
            "best": best, "streak": streak, "form": [m["result"] for m in ms[-5:]]}


def team_panel_embed(gid: int) -> discord.Embed:
    t = team_stats(gid)
    name = team_name_of(gid).upper()[:20]
    header = "```\n━━━━━━━━━━━━━━━━━━━━\n" + name.center(20) + "\n━━━━━━━━━━━━━━━━━━━━\n```"
    scorer = f"{t['scorer'][0]} — {t['scorer'][1]} gols" if t["scorer"] else "—"
    assister = f"{t['assister'][0]} — {t['assister'][1]} assistências" if t["assister"] else "—"
    mvp = f"{t['mvp'][0]} — {t['mvp'][1]} MVPs" if t["mvp"] else "—"
    emb = make_embed(gid, description=header + (
        f"🏟️ **JOGOS**\n{t['games']} partidas\n\n"
        f"✅ Vitórias: **{t['wins']}**\n➖ Empates: **{t['draws']}**\n❌ Derrotas: **{t['losses']}**\n\n"
        f"⚽ Gols: **{t['gf']}**\n🅰️ Assistências: **{t['assists']}**\n\n"
        f"📊 Aproveitamento: **{fmt_pct(t['winrate'])}**\n\n"
        f"👑 **Artilheiro**\n{scorer}\n\n🎯 **Garçom**\n{assister}\n\n🏅 **Mais MVPs**\n{mvp}"))
    logo = cfg_get(gid, "logo_url").strip()
    if logo.startswith("http"):
        emb.set_thumbnail(url=logo)
    return emb


def team_roster_embed(gid: int) -> discord.Embed:
    players = list_players(gid, include_inactive=False)
    if not players:
        return info_embed(gid, "👥 Elenco", "Nenhum jogador cadastrado ainda.")
    lines = []
    for p in players:
        st = stats_row(gid, p["id"])
        lines.append(f"`#{p['number']:>2}` **{p['name']}** · {p['position']} · Rank **{st['rank']}** · {STATUS_LABELS[p['status']]}")
    return info_embed(gid, f"👥 Elenco ({len(players)})", trunc("\n".join(lines), 3900))


def team_results_embed(gid: int) -> discord.Embed:
    ms = db_all("SELECT * FROM matches WHERE guild_id=? ORDER BY played_date DESC, id DESC LIMIT 5", (gid,))
    if not ms:
        return info_embed(gid, "🏆 Últimos resultados", "Nenhuma partida registrada ainda.")
    return info_embed(gid, "🏆 Últimos resultados", "\n\n".join(match_block(m) for m in ms))


def team_stats_embed(gid: int) -> discord.Embed:
    t = team_stats(gid)
    g = t["games"]
    emb = make_embed(gid, "⚽ Estatísticas do time")
    emb.add_field(name="Gols marcados", value=f"**{t['gf']}** ({(t['gf'] / g if g else 0):.2f}/jogo)".replace(".", ","), inline=True)
    emb.add_field(name="Gols sofridos", value=f"**{t['ga']}** ({(t['ga'] / g if g else 0):.2f}/jogo)".replace(".", ","), inline=True)
    emb.add_field(name="Saldo", value=f"**{t['gf'] - t['ga']:+d}**", inline=True)
    emb.add_field(name="Jogos sem sofrer gol", value=f"**{t['clean']}**", inline=True)
    emb.add_field(name="Maior sequência de vitórias", value=f"**{t['streak']}**", inline=True)
    emb.add_field(name="Aproveitamento", value=f"**{fmt_pct(t['winrate'])}**\n{progress_bar(t['winrate'])}", inline=True)
    if t["best"]:
        b = t["best"]
        emb.add_field(name="Maior vitória", value=f"vs {b['opponent']} — **{b['our_score']} × {b['opp_score']}**", inline=False)
    emb.add_field(name="Últimos 5 jogos", value=" ".join(RESULT_LABELS[r][3] for r in t["form"]) or "—", inline=False)
    return emb


class TimePanelView(discord.ui.View):
    """Painel do /time (persistente). Cada botão abre a informação em uma resposta só sua."""

    def __init__(self):
        super().__init__(timeout=None)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        await handle_error(interaction, error)

    @discord.ui.button(label="Ranking", emoji="📊", style=discord.ButtonStyle.primary, custom_id="mps:time:ranking")
    async def btn_ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        await respond(interaction, embed=build_ranking_pages(interaction.guild_id, "geral", per_page=10)[0])

    @discord.ui.button(label="Elenco", emoji="👥", style=discord.ButtonStyle.secondary, custom_id="mps:time:elenco")
    async def btn_elenco(self, interaction: discord.Interaction, button: discord.ui.Button):
        await respond(interaction, embed=team_roster_embed(interaction.guild_id))

    @discord.ui.button(label="Jogos", emoji="📅", style=discord.ButtonStyle.secondary, custom_id="mps:time:jogos")
    async def btn_jogos(self, interaction: discord.Interaction, button: discord.ui.Button):
        await respond(interaction, embed=build_calendar_pages(interaction.guild_id, per_page=5)[0])

    @discord.ui.button(label="Resultados", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="mps:time:resultados")
    async def btn_resultados(self, interaction: discord.Interaction, button: discord.ui.Button):
        await respond(interaction, embed=team_results_embed(interaction.guild_id))

    @discord.ui.button(label="Estatísticas", emoji="⚽", style=discord.ButtonStyle.secondary, custom_id="mps:time:stats")
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await respond(interaction, embed=team_stats_embed(interaction.guild_id))


@tree.command(name="time", description="Painel geral informativo do time.")
@app_commands.guild_only()
async def cmd_time(interaction: discord.Interaction):
    await respond(interaction, embed=team_panel_embed(interaction.guild_id), view=TimePanelView(), ephemeral=False)


# ==============================
# /AJUDA
# ==============================

HELP_PAGES = {
    "jogadores": ("👤", "Jogadores", [
        "`/perfil [usuario]` — perfil com estatísticas, histórico e conquistas",
        "`/jogador adicionar|editar|remover` — gerencia o elenco *(admin)*",
        "`/jogador listar` — lista o elenco",
        "`/ranking [tipo]` — ranking individual (geral, gols, assistências, vitórias, MVP)"]),
    "estatisticas": ("📊", "Estatísticas", [
        "`/gol jogador amount` — adiciona gols *(admin)*",
        "`/assistencia jogador amount` — adiciona assistências *(admin)*",
        "`/historico` — histórico de resultados",
        "`/result` — registra uma partida com gols, assistências e MVP *(admin)*"]),
    "jogos": ("📅", "Jogos", [
        "`/calendario` — próximos jogos",
        "`/jogo adicionar|editar|remover|listar` — gerencia o calendário *(admin)*"]),
    "escalacao": ("📋", "Escalação", [
        "`/escalar [jogador] [posição]` — monta a escalação e abre o painel *(admin)*",
        "`/escalação [formacao]` — gera a imagem da escalação (4-3-3, 4-4-2, 3-5-2, 5-3-2)"]),
    "comunicacao": ("📣", "Comunicação", [
        "`/say` — cria anúncios (aviso, jogo com presença, calendário, convocação, resultado, comunicado) *(admin)*"]),
    "time": ("🏟️", "Time", ["`/time` — painel geral do time com ranking, elenco, jogos, resultados e estatísticas"]),
    "admin": ("🛠️", "Administração", [
        "`/admin` — painel administrativo completo *(admin)*",
        "`/config` — canais, cargos, pesos, ranks, escalação e aparência *(admin)*"]),
}


def help_embed(gid: int, key: Optional[str]) -> discord.Embed:
    if key is None or key not in HELP_PAGES:
        emb = make_embed(gid, "📖 Central de ajuda",
                         "Use o menu abaixo para ver os comandos de cada área.\n\n" +
                         "\n".join(f"{v[0]} **{v[1]}**" for v in HELP_PAGES.values()))
        emb.add_field(name="Como o Rank funciona",
                      value="Pontuação = gols, assistências, vitórias e MVPs × pesos configuráveis. "
                            "Ranks: **D, C, B, A, S**, atualizados automaticamente a cada 60 minutos.", inline=False)
        return emb
    emoji, title, lines = HELP_PAGES[key]
    return make_embed(gid, f"{emoji} {title}", "\n".join(lines))


class HelpView(SafeView):
    def __init__(self, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        opts = [discord.SelectOption(label="Visão geral", value="home", emoji="📖")]
        opts += [discord.SelectOption(label=v[1], value=k, emoji=v[0]) for k, v in HELP_PAGES.items()]
        sel = discord.ui.Select(placeholder="Escolha uma categoria…", options=opts)

        async def cb(interaction: discord.Interaction):
            key = sel.values[0]
            await interaction.response.edit_message(embed=help_embed(interaction.guild_id, None if key == "home" else key))

        sel.callback = cb
        self.add_item(sel)


@tree.command(name="ajuda", description="Lista todos os comandos do bot organizados por categoria.")
@app_commands.guild_only()
async def cmd_ajuda(interaction: discord.Interaction):
    view = HelpView(interaction.user.id)
    await respond(interaction, embed=help_embed(interaction.guild_id, None), view=view)
    view.bind(interaction)


# ==============================
# PAINEL ADMIN
# ==============================

async def pick_user(interaction: discord.Interaction, title: str, callback, placeholder: str = "Selecione o jogador") -> None:
    view = UserPickView(interaction.user.id, callback, placeholder=placeholder)
    await respond(interaction, embed=info_embed(interaction.guild_id, title), view=view)
    view.bind(interaction)


class AmountModal(SafeModal):
    def __init__(self, player_id: int, stat: str, sign: int):
        emoji, label = STAT_LABELS[stat]
        super().__init__(title=f"{'Adicionar' if sign > 0 else 'Remover'} {label}"[:45], timeout=300)
        self.player_id, self.stat, self.sign = player_id, stat, sign
        self.f_amount = discord.ui.TextInput(label="Quantidade", max_length=3, placeholder="Ex.: 1")
        self.add_item(self.f_amount)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        try:
            n = int(self.f_amount.value.strip())
        except ValueError:
            raise UserError("Informe um número inteiro.", "Quantidade inválida")
        limit = 100 if self.sign < 0 else 20
        if not (1 <= n <= limit):
            raise UserError(f"A quantidade deve estar entre 1 e {limit}.", "Quantidade inválida")
        gid = interaction.guild_id
        player = get_player_by_id(self.player_id)
        res = await apply_manual_stat(gid, interaction.user.id, player, self.stat, self.sign * n)
        await respond(interaction, embed=manual_stat_embed(gid, player, self.stat, self.sign * n, res))


class RankPickView(SafeView):
    def __init__(self, owner_id: int, callback: Callable[[discord.Interaction, Optional[str]], Awaitable[None]]):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=300)
        opts = [discord.SelectOption(label="Automático (pela pontuação)", value="auto", emoji="🤖")]
        opts += [discord.SelectOption(label=f"Rank {r} (manual)", value=r, emoji=RANK_ICONS[r]) for r in RANKS]
        sel = discord.ui.Select(placeholder="Escolha o Rank", options=opts)

        async def cb(interaction: discord.Interaction):
            self._origin = None
            v = sel.values[0]
            await callback(interaction, None if v == "auto" else v)

        sel.callback = cb
        self.add_item(sel)


def reset_stats(gid: int, player_ids: Optional[list] = None) -> list:
    """Apaga gols/assistências/MVPs/participações dos jogadores (mantém os placares dos jogos)."""
    if player_ids is None:
        player_ids = [r["id"] for r in db_all("SELECT id FROM players WHERE guild_id=?", (gid,))]
    if not player_ids:
        return []
    marks = ",".join("?" * len(player_ids))
    with db_tx() as c:
        for table in ("goals", "assists", "mvps"):
            c.execute(f"DELETE FROM {table} WHERE player_id IN ({marks})", tuple(player_ids))
        c.execute(f"DELETE FROM match_players WHERE player_id IN ({marks})", tuple(player_ids))
        c.execute(f"UPDATE matches SET mvp_player_id=NULL WHERE mvp_player_id IN ({marks})", tuple(player_ids))
        c.execute(f"DELETE FROM achievements WHERE player_id IN ({marks})", tuple(player_ids))
    return player_ids


class ResetAllModal(SafeModal):
    def __init__(self):
        super().__init__(title="Resetar TODAS as estatísticas", timeout=300)
        self.f_confirm = discord.ui.TextInput(label="Digite CONFIRMAR para continuar", max_length=10)
        self.add_item(self.f_confirm)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        if self.f_confirm.value.strip().upper() != "CONFIRMAR":
            raise UserError("Confirmação incorreta. Nada foi alterado.", "Reset cancelado")
        totals = db_one("SELECT COALESCE(SUM(goals),0) g, COALESCE(SUM(assists),0) a, COALESCE(SUM(mvps),0) m, "
                        "COALESCE(SUM(games),0) j FROM player_stats WHERE guild_id=?", (gid,))
        pids = reset_stats(gid)
        await after_stats_change(gid, pids, interaction.user.id, "Reset geral")
        await log_event(gid, interaction.user.id, "Estatísticas", "Reset geral de estatísticas",
                        before=f"{totals['g']} gols, {totals['a']} assist., {totals['m']} MVPs, {totals['j']} participações",
                        after="Tudo zerado")
        await respond(interaction, embed=success_embed(gid, "Estatísticas resetadas",
                                                       f"As estatísticas de **{len(pids)}** jogador(es) foram zeradas."))
        if interaction.guild:
            await refresh_ranking_board(interaction.guild)


async def admin_back(interaction: discord.Interaction, old: Optional[discord.ui.View]) -> None:
    view = AdminHomeView(interaction.guild_id, interaction.user.id)
    await switch_view(interaction, old, embed=admin_home_embed(interaction.guild_id), view=view)


def admin_home_embed(gid: int) -> discord.Embed:
    return make_embed(gid, "🛠️ Painel administrativo",
                      "Escolha uma categoria no menu abaixo.\n\n"
                      "👤 **Jogadores** — adicionar, editar, remover, posição, Rank\n"
                      "📊 **Estatísticas** — gols, assistências, MVPs e reset\n"
                      "📅 **Jogos** — calendário, resultados e histórico\n"
                      "📋 **Escalação** — montar, limpar e formação\n"
                      "⚙️ **Configurações** — canais, cargos, Rank, pesos, logs, aparência")


ADMIN_CATEGORIES = [("jogadores", "Jogadores", "👤"), ("estatisticas", "Estatísticas", "📊"),
                    ("jogos", "Jogos", "📅"), ("escalacao", "Escalação", "📋"),
                    ("configuracoes", "Configurações", "⚙️")]


class AdminHomeView(SafeView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.gid = gid
        sel = discord.ui.Select(placeholder="Escolha uma categoria…", options=[
            discord.SelectOption(label=n, value=k, emoji=e) for k, n, e in ADMIN_CATEGORIES])
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        require_staff(interaction)
        key = interaction.data["values"][0]
        gid = self.gid
        if key == "escalacao":
            await switch_view(interaction, self, embed=lineup_panel_embed(gid),
                              view=LineupPanelView(gid, interaction.user.id, back=admin_back))
        elif key == "configuracoes":
            await switch_view(interaction, self, embed=config_home_embed(gid),
                              view=ConfigHomeView(gid, interaction.user.id, back=admin_back))
        else:
            cls = {"jogadores": AdminPlayersView, "estatisticas": AdminStatsView, "jogos": AdminGamesView}[key]
            await switch_view(interaction, self, embed=admin_category_embed(gid, key),
                              view=cls(gid, interaction.user.id))


def admin_category_embed(gid: int, key: str) -> discord.Embed:
    texts = {
        "jogadores": ("👤 Admin • Jogadores", "Gerencie o elenco. Remover **não** apaga estatísticas (o jogador vira inativo)."),
        "estatisticas": ("📊 Admin • Estatísticas", "Ajustes manuais ficam registrados nos logs com valores antes/depois."),
        "jogos": ("📅 Admin • Jogos", "Calendário, registro de resultados e histórico (com opção de excluir resultados)."),
    }
    t, d = texts[key]
    return make_embed(gid, t, d)


class AdminCategoryView(SafeView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.gid = gid

    def add_back(self, row: int) -> None:
        add_button(self, "Voltar", self._back, emoji="⬅️", row=row)

    async def _back(self, interaction: discord.Interaction):
        await admin_back(interaction, self)


class AdminPlayersView(AdminCategoryView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(gid, owner_id)
        add_button(self, "Adicionar", self._add, emoji="➕", style=discord.ButtonStyle.success, row=0)
        add_button(self, "Editar", self._edit, emoji="✏️", row=0)
        add_button(self, "Remover", self._remove, emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
        add_button(self, "Alterar posição", self._position, emoji="🔁", row=1)
        add_button(self, "Alterar Rank", self._rank, emoji="🏷️", row=1)
        add_button(self, "Ver estatísticas", self._stats, emoji="📈", row=1)
        self.add_back(2)

    async def _add(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            existing = get_player(self.gid, user.id)
            if existing is not None and existing["status"] != "inativo":
                raise UserError(f"**{existing['name']}** já está no elenco. Use **Editar**.", "Já cadastrado")
            await inter.response.send_modal(PlayerModal(self.gid, user, existing))

        await pick_user(interaction, "Quem será adicionado ao elenco?", picked, "Selecione o usuário")

    async def _edit(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            existing = require_player(self.gid, user.id)
            await inter.response.send_modal(PlayerModal(self.gid, user, existing))

        await pick_user(interaction, "Qual jogador você quer editar?", picked)

    async def _remove(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)
            if player["status"] == "inativo":
                raise UserError(f"**{player['name']}** já está inativo.", "Já inativo")

            async def do_remove(i2: discord.Interaction):
                require_staff(i2)
                before, after = remove_player(self.gid, user.id)
                await log_event(self.gid, i2.user.id, "Jogadores", "Jogador removido (inativo)",
                                before=player_snapshot(before), after=player_snapshot(after))
                await i2.response.edit_message(embed=success_embed(
                    self.gid, "Jogador removido", f"**{player['name']}** agora está inativo. Estatísticas preservadas."), view=None)

            view = ConfirmView(inter.user.id, do_remove, confirm_label="Remover jogador")
            await inter.response.edit_message(embed=warn_embed(
                self.gid, "Remover este jogador?",
                f"**{player['name']}** será marcado como **inativo**.\nO histórico e as estatísticas continuam salvos."), view=view)
            view.bind(inter)

        await pick_user(interaction, "Qual jogador você quer remover?", picked)

    async def _position(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)

            async def chosen(i2: discord.Interaction, pos: str):
                require_staff(i2)
                before, after = edit_player(self.gid, user.id, position=pos)
                await log_event(self.gid, i2.user.id, "Jogadores", "Posição alterada",
                                before=f"{before['name']}: {before['position']}", after=f"{after['name']}: {after['position']}")
                await i2.response.edit_message(embed=success_embed(
                    self.gid, "Posição alterada", f"**{player['name']}**: {before['position']} ➜ **{pos}**"), view=None)

            view = PositionPickView(inter.user.id, chosen, f"Nova posição de {player['name']}"[:100])
            await inter.response.edit_message(embed=info_embed(self.gid, f"Nova posição de {player['name']}"), view=view)
            view.bind(inter)

        await pick_user(interaction, "De qual jogador você quer alterar a posição?", picked)

    async def _rank(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)

            async def chosen(i2: discord.Interaction, rank: Optional[str]):
                require_staff(i2)
                before = stats_row(self.gid, player["id"])
                db_exec("UPDATE players SET rank_override=? WHERE id=?", (rank, player["id"]))
                await after_stats_change(self.gid, [player["id"]], i2.user.id, "Rank alterado pela administração")
                after = stats_row(self.gid, player["id"])
                await log_event(self.gid, i2.user.id, "Rank", "Rank alterado manualmente",
                                before=f"{player['name']}: Rank {before['rank']}",
                                after=f"{player['name']}: Rank {after['rank']} ({'manual' if rank else 'automático'})")
                await i2.response.edit_message(embed=success_embed(
                    self.gid, "Rank atualizado",
                    f"**{player['name']}**: {before['rank']} ➜ **{after['rank']}**"
                    f"{' (fixado manualmente)' if rank else ' (automático pela pontuação)'}"), view=None)

            view = RankPickView(inter.user.id, chosen)
            await inter.response.edit_message(embed=info_embed(self.gid, f"Rank de {player['name']}"), view=view)
            view.bind(inter)

        await pick_user(interaction, "De qual jogador você quer alterar o Rank?", picked)

    async def _stats(self, interaction: discord.Interaction):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)
            await inter.response.edit_message(embed=stats_embed(self.gid, player, user.display_avatar.url), view=None)

        await pick_user(interaction, "Ver estatísticas de qual jogador?", picked)


class AdminStatsView(AdminCategoryView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(gid, owner_id)
        specs = [("goals", 1, "Adicionar gol", "⚽", discord.ButtonStyle.success),
                 ("goals", -1, "Remover gol", "⚽", discord.ButtonStyle.danger),
                 ("assists", 1, "Adicionar assistência", "🅰️", discord.ButtonStyle.success),
                 ("assists", -1, "Remover assistência", "🅰️", discord.ButtonStyle.danger),
                 ("mvps", 1, "Adicionar MVP", "🏅", discord.ButtonStyle.success),
                 ("mvps", -1, "Remover MVP", "🏅", discord.ButtonStyle.danger)]
        for i, (stat, sign, label, emoji, style) in enumerate(specs):
            async def cb(interaction: discord.Interaction, stat=stat, sign=sign):
                await self._ask(interaction, stat, sign)
            add_button(self, label, cb, emoji=emoji, style=style, row=0 if i < 3 else 1)
        add_button(self, "Resetar estatísticas", self._reset, emoji="🔄", style=discord.ButtonStyle.danger, row=2)
        self.add_back(2)

    async def _ask(self, interaction: discord.Interaction, stat: str, sign: int):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id, allow_inactive=False)
            await inter.response.send_modal(AmountModal(player["id"], stat, sign))

        label = STAT_LABELS[stat][1].lower()
        await pick_user(interaction, f"{'Adicionar' if sign > 0 else 'Remover'} {label} — selecione o jogador", picked)

    async def _reset(self, interaction: discord.Interaction):
        require_staff(interaction)
        view = ResetChoiceView(self.gid, interaction.user.id)
        await respond(interaction, embed=warn_embed(
            self.gid, "Resetar estatísticas",
            "Escolha o escopo. Os **placares das partidas** permanecem; são apagados gols, assistências, MVPs, "
            "participações e conquistas dos jogadores. Esta ação é registrada nos logs."), view=view)
        view.bind(interaction)


class ResetChoiceView(SafeView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=120)
        self.gid = gid

    @discord.ui.button(label="Resetar um jogador", emoji="👤", style=discord.ButtonStyle.danger)
    async def btn_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        require_staff(interaction)

        async def picked(inter: discord.Interaction, user):
            player = require_player(self.gid, user.id)

            async def do_reset(i2: discord.Interaction):
                require_staff(i2)
                before = stats_row(self.gid, player["id"])
                reset_stats(self.gid, [player["id"]])
                await after_stats_change(self.gid, [player["id"]], i2.user.id, "Reset individual")
                await log_event(self.gid, i2.user.id, "Estatísticas", "Reset de estatísticas do jogador",
                                before=f"{player['name']}: {before['goals']} gols, {before['assists']} assist., "
                                       f"{before['mvps']} MVPs, {before['games']} jogos", after="Zerado")
                await i2.response.edit_message(embed=success_embed(
                    self.gid, "Estatísticas resetadas", f"As estatísticas de **{player['name']}** foram zeradas."), view=None)

            view = ConfirmView(inter.user.id, do_reset, confirm_label="Resetar estatísticas")
            await inter.response.edit_message(embed=warn_embed(
                self.gid, f"Resetar {player['name']}?", "Gols, assistências, MVPs, participações e conquistas serão apagados."), view=view)
            view.bind(inter)

        await pick_user(interaction, "Qual jogador terá as estatísticas resetadas?", picked)

    @discord.ui.button(label="Resetar TODOS", emoji="☢️", style=discord.ButtonStyle.danger)
    async def btn_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        require_staff(interaction)
        await interaction.response.send_modal(ResetAllModal())


class AdminGamesView(AdminCategoryView):
    def __init__(self, gid: int, owner_id: int):
        super().__init__(gid, owner_id)
        add_button(self, "Adicionar jogo", self._add, emoji="➕", style=discord.ButtonStyle.success, row=0)
        add_button(self, "Editar jogo", self._edit, emoji="✏️", row=0)
        add_button(self, "Remover jogo", self._remove, emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
        add_button(self, "Registrar resultado", self._result, emoji="📝", style=discord.ButtonStyle.primary, row=1)
        add_button(self, "Histórico", self._history, emoji="📜", row=1)
        self.add_back(2)

    async def _add(self, interaction: discord.Interaction):
        require_staff(interaction)
        await interaction.response.send_modal(GameModal(self.gid))

    async def _edit(self, interaction: discord.Interaction):
        require_staff(interaction)
        await ask_game_then(interaction, edit_game_flow)

    async def _remove(self, interaction: discord.Interaction):
        require_staff(interaction)
        await ask_game_then(interaction, remove_game_flow)

    async def _result(self, interaction: discord.Interaction):
        require_staff(interaction)
        await interaction.response.send_modal(ResultStartModal())

    async def _history(self, interaction: discord.Interaction):
        require_staff(interaction)
        gid = self.gid
        matches = db_all("SELECT * FROM matches WHERE guild_id=? ORDER BY played_date DESC, id DESC LIMIT 25", (gid,))
        if not matches:
            raise UserError("Nenhum resultado registrado ainda.", "Histórico vazio")
        view = SafeView(owner_id=interaction.user.id, staff_only=True, timeout=300)
        sel = discord.ui.Select(placeholder="Selecione um resultado para ver/excluir…", options=[
            discord.SelectOption(label=trunc(f"{m['opponent']} • {m['our_score']}×{m['opp_score']}", 100),
                                 value=str(m["id"]), description=f"{fmt_date(m['played_date'])} • {RESULT_LABELS[m['result']][2]}")
            for m in matches])

        async def picked(inter: discord.Interaction):
            view._origin = None
            mid = int(sel.values[0])

            async def do_delete(i2: discord.Interaction):
                require_staff(i2)
                match, pids = delete_match(gid, mid)
                await after_stats_change(gid, pids, i2.user.id, f"Resultado #{mid} excluído")
                await log_event(gid, i2.user.id, "Resultados", "Resultado excluído",
                                before=f"{match['opponent']} {match['our_score']}×{match['opp_score']} ({fmt_date(match['played_date'])})",
                                after="Estatísticas revertidas")
                await i2.response.edit_message(embed=success_embed(
                    gid, "Resultado excluído", "As estatísticas ligadas a essa partida foram revertidas e o Rank recalculado."), view=None)
                if i2.guild:
                    await refresh_ranking_board(i2.guild)
                    await refresh_calendar_board(i2.guild)

            emb = build_result_embed(gid, mid)
            emb.add_field(name="⚠️ Excluir?", value="Confirmar remove a partida e **reverte** gols, assistências, MVP e jogos.", inline=False)
            cview = ConfirmView(inter.user.id, do_delete, confirm_label="Excluir resultado")
            await inter.response.edit_message(embed=emb, view=cview)
            cview.bind(inter)

        sel.callback = picked
        view.add_item(sel)
        await respond(interaction, embed=info_embed(gid, "📜 Histórico de resultados (últimos 25)"), view=view)
        view.bind(interaction)


@tree.command(name="admin", description="Painel administrativo do time.")
@app_commands.guild_only()
@staff_only()
async def cmd_admin(interaction: discord.Interaction):
    view = AdminHomeView(interaction.guild_id, interaction.user.id)
    await respond(interaction, embed=admin_home_embed(interaction.guild_id), view=view)
    view.bind(interaction)


# ==============================
# CONFIGURAÇÕES (/config)
# ==============================

CONFIG_SECTIONS = [("canais", "Canais", "📺"), ("cargos", "Cargos", "👥"), ("pesos", "Pesos do Rank", "⚖️"),
                   ("ranks", "Valores dos Ranks", "🏅"), ("escalacao", "Escalação", "📋"),
                   ("aparencia", "Aparência", "🎨"), ("logs", "Logs", "📜"), ("calendario", "Calendário e ranking", "📅")]


def config_home_embed(gid: int) -> discord.Embed:
    return make_embed(gid, "⚙️ Configurações do servidor",
                      "As configurações são salvas **separadamente por servidor**.\n\n" +
                      "\n".join(f"{e} **{n}**" for _, n, e in CONFIG_SECTIONS))


def channel_label(guild: Optional[discord.Guild], gid: int, key: str) -> str:
    cid = cfg_int(gid, key)
    if not cid:
        return "não definido"
    ch = guild.get_channel(cid) if guild else None
    return f"#{ch.name}" if ch else f"ID {cid}"


class ConfigHomeView(SafeView):
    def __init__(self, gid: int, owner_id: int, back: Optional[Callable] = None):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.gid, self.back = gid, back
        sel = discord.ui.Select(placeholder="Escolha uma seção…", options=[
            discord.SelectOption(label=n, value=k, emoji=e) for k, n, e in CONFIG_SECTIONS], row=0)
        sel.callback = self._on_select
        self.add_item(sel)
        if back is not None:
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=1)

    async def _go_back(self, interaction: discord.Interaction):
        await self.back(interaction, self)

    async def _on_select(self, interaction: discord.Interaction):
        require_staff(interaction)
        await open_config_section(interaction, self, interaction.data["values"][0], self.back)


async def config_home_back(interaction: discord.Interaction, old: Optional[discord.ui.View], back: Optional[Callable]) -> None:
    gid = interaction.guild_id
    await switch_view(interaction, old, embed=config_home_embed(gid), view=ConfigHomeView(gid, interaction.user.id, back))


async def recalc_all(gid: int, actor_id: int, reason: str) -> None:
    pids = [r["id"] for r in db_all("SELECT id FROM players WHERE guild_id=?", (gid,))]
    await after_stats_change(gid, pids, actor_id, reason)
    guild = bot.get_guild(gid)
    if guild:
        await refresh_ranking_board(guild)


class WeightsModal(SafeModal):
    def __init__(self, gid: int):
        super().__init__(title="Pesos do Rank", timeout=300)
        w = rank_weights(gid)
        self.fields = {}
        for key, label in (("goals", "Peso de gols"), ("assists", "Peso de assistências"),
                           ("wins", "Peso de vitórias"), ("mvps", "Peso de MVP")):
            item = discord.ui.TextInput(label=label, max_length=8, default=fmt_num(w[key]).replace(",", "."))
            self.fields[key] = item
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        vals = {}
        for key, item in self.fields.items():
            try:
                v = float(item.value.replace(",", ".").strip())
            except ValueError:
                raise UserError(f"Valor inválido em **{item.label}**. Use números (ex.: 3 ou 2.5).", "Peso inválido")
            if not (0 <= v <= 1000):
                raise UserError("Os pesos devem estar entre 0 e 1000.", "Peso inválido")
            vals[key] = v
        before = rank_weights(gid)
        for key, cfgkey in (("goals", "w_goal"), ("assists", "w_assist"), ("wins", "w_win"), ("mvps", "w_mvp")):
            cfg_set(gid, cfgkey, vals[key])
        await log_event(gid, interaction.user.id, "Configurações", "Pesos do Rank alterados",
                        before=", ".join(f"{k}={fmt_num(v)}" for k, v in before.items()),
                        after=", ".join(f"{k}={fmt_num(v)}" for k, v in vals.items()))
        await recalc_all(gid, interaction.user.id, "Pesos do Rank alterados")
        await respond(interaction, embed=success_embed(gid, "Pesos atualizados", "O Rank de todos os jogadores foi recalculado."))


class RanksModal(SafeModal):
    def __init__(self, gid: int):
        super().__init__(title="Pontuação mínima de cada Rank", timeout=300)
        th = rank_thresholds(gid)
        self.fields = {}
        for r in RANKS:
            item = discord.ui.TextInput(label=f"Rank {r} — pontuação mínima", max_length=8,
                                        default=fmt_num(th[r]).replace(",", "."))
            self.fields[r] = item
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        vals = {}
        for r, item in self.fields.items():
            try:
                vals[r] = float(item.value.replace(",", ".").strip())
            except ValueError:
                raise UserError(f"Valor inválido no Rank {r}.", "Valor inválido")
            if vals[r] < 0:
                raise UserError("Os valores não podem ser negativos.", "Valor inválido")
        if not (vals["D"] <= vals["C"] < vals["B"] < vals["A"] < vals["S"]):
            raise UserError("Os valores precisam ser crescentes: D ≤ C < B < A < S.", "Ordem inválida")
        before = rank_thresholds(gid)
        for r in RANKS:
            cfg_set(gid, f"rank_{r.lower()}", vals[r])
        await log_event(gid, interaction.user.id, "Configurações", "Valores dos Ranks alterados",
                        before=", ".join(f"{k}≥{fmt_num(v)}" for k, v in before.items()),
                        after=", ".join(f"{k}≥{fmt_num(v)}" for k, v in vals.items()))
        await recalc_all(gid, interaction.user.id, "Valores dos Ranks alterados")
        await respond(interaction, embed=success_embed(gid, "Ranks atualizados", "O Rank de todos os jogadores foi recalculado."))


class AppearanceModal(SafeModal):
    def __init__(self, gid: int):
        super().__init__(title="Aparência das mensagens", timeout=300)
        self.f_name = discord.ui.TextInput(label="Nome do time", required=False, max_length=40,
                                           default=cfg_get(gid, "team_name") or None, placeholder="Vazio = nome do servidor")
        self.f_color = discord.ui.TextInput(label="Cor principal (#hex ou nome)", max_length=20, default=cfg_get(gid, "color"))
        self.f_footer = discord.ui.TextInput(label="Rodapé das mensagens", required=False, max_length=100,
                                             default=cfg_get(gid, "footer") or None)
        self.f_logo = discord.ui.TextInput(label="Logo do time (URL da imagem)", required=False, max_length=500,
                                           default=cfg_get(gid, "logo_url") or None)
        self.f_tz = discord.ui.TextInput(label="Fuso horário (horas, ex.: -3)", max_length=5, default=cfg_get(gid, "tz_offset"))
        for item in (self.f_name, self.f_color, self.f_footer, self.f_logo, self.f_tz):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        require_staff(interaction)
        gid = interaction.guild_id
        color = parse_color(self.f_color.value, 0x3B82F6)
        logo = valid_url(self.f_logo.value, "logo")
        try:
            tz = float(self.f_tz.value.replace(",", ".").strip())
        except ValueError:
            raise UserError("O fuso deve ser um número de horas (ex.: -3).", "Fuso inválido")
        if not (-12 <= tz <= 14):
            raise UserError("O fuso deve estar entre -12 e +14.", "Fuso inválido")
        before = f"{cfg_get(gid, 'team_name')} | {cfg_get(gid, 'color')} | {cfg_get(gid, 'footer')} | fuso {cfg_get(gid, 'tz_offset')}"
        cfg_set(gid, "team_name", self.f_name.value.strip())
        cfg_set(gid, "color", f"#{color:06X}")
        cfg_set(gid, "footer", self.f_footer.value.strip())
        cfg_set(gid, "logo_url", logo)
        cfg_set(gid, "tz_offset", fmt_num(tz).replace(",", "."))
        await log_event(gid, interaction.user.id, "Configurações", "Aparência alterada", before=before,
                        after=f"{self.f_name.value} | #{color:06X} | {self.f_footer.value} | fuso {tz}")
        await respond(interaction, embed=success_embed(gid, "Aparência atualizada", "As próximas mensagens já usarão as novas configurações."))


class ConfigSectionView(SafeView):
    def __init__(self, gid: int, owner_id: int, section: str, back: Optional[Callable]):
        super().__init__(owner_id=owner_id, staff_only=True, timeout=600)
        self.gid, self.section, self.back_cb = gid, section, back
        guild = bot.get_guild(gid)
        text_types = [discord.ChannelType.text, discord.ChannelType.news]
        if section == "canais":
            for i, (key, label) in enumerate((("log_channel", "Canal de logs"), ("results_channel", "Canal de resultados"),
                                              ("calendar_channel", "Canal de calendário"), ("ranking_channel", "Canal de ranking"))):
                sel = discord.ui.ChannelSelect(placeholder=trunc(f"{label} (atual: {channel_label(guild, gid, key)})", 150),
                                               channel_types=text_types, min_values=1, max_values=1, row=i)

                async def cb(interaction: discord.Interaction, key=key, label=label, sel=sel):
                    await self._set_channel(interaction, key, label, sel.values[0])

                sel.callback = cb
                self.add_item(sel)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=4)
        elif section == "cargos":
            for i, (key, label) in enumerate((("admin_role", "Cargo de administrador"), ("player_role", "Cargo de jogador"))):
                cur = cfg_int(gid, key)
                role = guild.get_role(cur) if guild and cur else None
                sel = discord.ui.RoleSelect(placeholder=trunc(f"{label} (atual: {role.name if role else 'não definido'})", 150),
                                            min_values=1, max_values=1, row=i)

                async def cb(interaction: discord.Interaction, key=key, label=label, sel=sel):
                    await self._set_role(interaction, key, label, sel.values[0])

                sel.callback = cb
                self.add_item(sel)
            add_button(self, "Limpar cargo admin", self._clear_admin, emoji="🧹", row=2)
            add_button(self, "Limpar cargo jogador", self._clear_player, emoji="🧹", row=2)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=3)
        elif section == "pesos":
            add_button(self, "Editar pesos", self._weights, emoji="✏️", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=0)
        elif section == "ranks":
            add_button(self, "Editar valores", self._ranks, emoji="✏️", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=0)
        elif section == "escalacao":
            sel = discord.ui.Select(placeholder="Formação padrão…", row=0, options=[
                discord.SelectOption(label=f, value=f, default=(f == cfg_get(gid, "lineup_formation"))) for f in FORMATIONS])
            sel.callback = self._formation
            self.add_item(sel)
            add_button(self, "Avatares na imagem", self._toggle_avatars, emoji="🖼️", row=1,
                       style=discord.ButtonStyle.success if cfg_get(gid, "lineup_avatars") != "0" else discord.ButtonStyle.secondary)
            add_button(self, "Números das camisas", self._toggle_numbers, emoji="🔢", row=1,
                       style=discord.ButtonStyle.success if cfg_get(gid, "lineup_numbers") != "0" else discord.ButtonStyle.secondary)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=2)
        elif section == "aparencia":
            add_button(self, "Editar aparência", self._appearance, emoji="🎨", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=0)
        elif section == "logs":
            add_button(self, "Ver últimos registros", self._logs, emoji="📜", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=0)
        else:  # calendario
            add_button(self, "Atualizar calendário", self._refresh_calendar, emoji="📅", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Atualizar ranking", self._refresh_ranking, emoji="🏆", style=discord.ButtonStyle.primary, row=0)
            add_button(self, "Voltar", self._go_back, emoji="⬅️", row=0)

    def embed(self) -> discord.Embed:
        gid = self.gid
        guild = bot.get_guild(gid)
        s = self.section
        if s == "canais":
            return make_embed(gid, "📺 Canais", "\n".join(f"{n}: **{channel_label(guild, gid, k)}**" for k, n in (
                ("log_channel", "📜 Logs"), ("results_channel", "🏆 Resultados"),
                ("calendar_channel", "📅 Calendário"), ("ranking_channel", "📊 Ranking"))) +
                "\n\nUse os menus para escolher. O bot precisa de permissão para enviar mensagens nos canais.")
        if s == "cargos":
            def role_text(key):
                rid = cfg_int(gid, key)
                return f"<@&{rid}>" if rid else "**não definido**"
            return make_embed(gid, "👥 Cargos", f"Administrador: {role_text('admin_role')}\nJogador: {role_text('player_role')}\n\n"
                                               "Administradores do servidor sempre têm acesso. O cargo de jogador é mencionado nos avisos de jogo.")
        if s == "pesos":
            w = rank_weights(gid)
            return make_embed(gid, "⚖️ Pesos do Rank",
                              f"Pontuação = gols×**{fmt_num(w['goals'])}** + assistências×**{fmt_num(w['assists'])}** "
                              f"+ vitórias×**{fmt_num(w['wins'])}** + MVPs×**{fmt_num(w['mvps'])}**")
        if s == "ranks":
            th = rank_thresholds(gid)
            return make_embed(gid, "🏅 Valores dos Ranks", "\n".join(
                f"{RANK_ICONS[r]} Rank **{r}**: a partir de **{fmt_num(th[r])}** pontos" for r in reversed(RANKS)))
        if s == "escalacao":
            return make_embed(gid, "📋 Escalação", f"Formação padrão: **{cfg_get(gid, 'lineup_formation')}**\n"
                              f"Avatares na imagem: **{'sim' if cfg_get(gid, 'lineup_avatars') != '0' else 'não'}**\n"
                              f"Números das camisas: **{'sim' if cfg_get(gid, 'lineup_numbers') != '0' else 'não'}**")
        if s == "aparencia":
            return make_embed(gid, "🎨 Aparência", f"Nome do time: **{team_name_of(gid)}**\nCor: **{cfg_get(gid, 'color')}**\n"
                              f"Rodapé: **{cfg_get(gid, 'footer') or '—'}**\nLogo: **{cfg_get(gid, 'logo_url') or '—'}**\n"
                              f"Fuso: **UTC{cfg_get(gid, 'tz_offset')}**", accent_color(gid))
        if s == "logs":
            return make_embed(gid, "📜 Logs", f"Canal de logs: **{channel_label(guild, gid, 'log_channel')}**\n"
                              "Gols, assistências, MVPs, Ranks, jogadores, resultados, escalações, configurações e erros são registrados.")
        return make_embed(gid, "📅 Calendário e ranking",
                          f"Canal do calendário: **{channel_label(guild, gid, 'calendar_channel')}**\n"
                          f"Canal do ranking: **{channel_label(guild, gid, 'ranking_channel')}**\n"
                          "As mensagens fixas são atualizadas automaticamente (ranking: a cada 60 min).")

    async def _go_back(self, interaction: discord.Interaction):
        await config_home_back(interaction, self, self.back_cb)

    async def _reload(self, interaction: discord.Interaction):
        view = ConfigSectionView(self.gid, interaction.user.id, self.section, self.back_cb)
        await switch_view(interaction, self, embed=view.embed(), view=view)

    async def _set_channel(self, interaction, key, label, channel):
        require_staff(interaction)
        old = cfg_get(self.gid, key)
        guild = interaction.guild
        real = guild.get_channel(channel.id)
        if real is None:
            raise UserError("Não consegui acessar esse canal.", "Canal inválido")
        perms = real.permissions_for(guild.me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            raise UserError(f"O bot não tem permissão de **ver, enviar mensagens e inserir links** em {real.mention}.",
                            "Permissão do bot")
        cfg_set(self.gid, key, channel.id)
        if key == "calendar_channel":
            cfg_set(self.gid, "calendar_message_id", "")
        if key == "ranking_channel":
            cfg_set(self.gid, "ranking_message_id", "")
        await log_event(self.gid, interaction.user.id, "Configurações", f"{label} alterado",
                        before=f"<#{old}>" if old else "não definido", after=real.mention)
        if key == "calendar_channel":
            await refresh_calendar_board(guild)
        elif key == "ranking_channel":
            await refresh_ranking_board(guild)
        await self._reload(interaction)

    async def _set_role(self, interaction, key, label, role):
        require_staff(interaction)
        old = cfg_get(self.gid, key)
        cfg_set(self.gid, key, role.id)
        await log_event(self.gid, interaction.user.id, "Configurações", f"{label} alterado",
                        before=f"<@&{old}>" if old else "não definido", after=role.mention)
        await self._reload(interaction)

    async def _clear_role(self, interaction, key, label):
        require_staff(interaction)
        old = cfg_get(self.gid, key)
        cfg_set(self.gid, key, "")
        await log_event(self.gid, interaction.user.id, "Configurações", f"{label} removido",
                        before=f"<@&{old}>" if old else "não definido", after="não definido")
        await self._reload(interaction)

    async def _clear_admin(self, interaction: discord.Interaction):
        await self._clear_role(interaction, "admin_role", "Cargo de administrador")

    async def _clear_player(self, interaction: discord.Interaction):
        await self._clear_role(interaction, "player_role", "Cargo de jogador")

    async def _weights(self, interaction: discord.Interaction):
        require_staff(interaction)
        await interaction.response.send_modal(WeightsModal(self.gid))

    async def _ranks(self, interaction: discord.Interaction):
        require_staff(interaction)
        await interaction.response.send_modal(RanksModal(self.gid))

    async def _appearance(self, interaction: discord.Interaction):
        require_staff(interaction)
        await interaction.response.send_modal(AppearanceModal(self.gid))

    async def _formation(self, interaction: discord.Interaction):
        require_staff(interaction)
        value = interaction.data["values"][0]
        old = cfg_get(self.gid, "lineup_formation")
        cfg_set(self.gid, "lineup_formation", value)
        await log_event(self.gid, interaction.user.id, "Configurações", "Formação padrão alterada", before=old, after=value)
        await self._reload(interaction)

    async def _toggle(self, interaction: discord.Interaction, key: str, label: str):
        require_staff(interaction)
        new = "0" if cfg_get(self.gid, key) != "0" else "1"
        cfg_set(self.gid, key, new)
        await log_event(self.gid, interaction.user.id, "Configurações", f"{label} {'ativado' if new == '1' else 'desativado'}")
        await self._reload(interaction)

    async def _toggle_avatars(self, interaction: discord.Interaction):
        await self._toggle(interaction, "lineup_avatars", "Avatares na escalação")

    async def _toggle_numbers(self, interaction: discord.Interaction):
        await self._toggle(interaction, "lineup_numbers", "Números na escalação")

    async def _logs(self, interaction: discord.Interaction):
        require_staff(interaction)
        await send_paged(interaction, build_log_pages(self.gid), ephemeral=True)

    async def _refresh_calendar(self, interaction: discord.Interaction):
        require_staff(interaction)
        if not cfg_int(self.gid, "calendar_channel"):
            raise UserError("Defina primeiro o **canal de calendário** na seção Canais.", "Canal não definido")
        await refresh_calendar_board(interaction.guild)
        await respond(interaction, embed=success_embed(self.gid, "Calendário atualizado"))

    async def _refresh_ranking(self, interaction: discord.Interaction):
        require_staff(interaction)
        if not cfg_int(self.gid, "ranking_channel"):
            raise UserError("Defina primeiro o **canal de ranking** na seção Canais.", "Canal não definido")
        await recalc_all(self.gid, interaction.user.id, "Atualização manual")
        await respond(interaction, embed=success_embed(self.gid, "Ranking atualizado"))


async def open_config_section(interaction: discord.Interaction, old: Optional[discord.ui.View], section: str,
                              back: Optional[Callable]) -> None:
    view = ConfigSectionView(interaction.guild_id, interaction.user.id, section, back)
    await switch_view(interaction, old, embed=view.embed(), view=view)


@tree.command(name="config", description="Configurações do bot neste servidor (administração).")
@app_commands.guild_only()
@staff_only()
async def cmd_config(interaction: discord.Interaction):
    view = ConfigHomeView(interaction.guild_id, interaction.user.id)
    await respond(interaction, embed=config_home_embed(interaction.guild_id), view=view)
    view.bind(interaction)


# ==============================
# EVENTOS
# ==============================

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await handle_error(interaction, error)


@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            ensure_guild(guild)
        except Exception:
            log.exception("Falha ao registrar o servidor %s.", guild.id)
    if not rank_update_loop.is_running():
        rank_update_loop.start()
    try:
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="o time jogar | /ajuda"))
    except Exception:
        pass
    log.info("Bot online como %s em %d servidor(es).", bot.user, len(bot.guilds))


@bot.event
async def on_guild_join(guild: discord.Guild):
    ensure_guild(guild)
    log.info("Entrei no servidor %s (%s).", guild.name, guild.id)


@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    if before.name != after.name:
        ensure_guild(after)


# ==============================
# INICIALIZAÇÃO
# ==============================

def main() -> None:
    if not TOKEN or TOKEN.strip() == "COLOQUE_SEU_TOKEN_AQUI":
        print("\n[ERRO] Coloque o token do seu bot na variável TOKEN, no início do main.py.\n")
        sys.exit(1)
    init_db()
    log.info("Banco de dados pronto em '%s'.", DB_PATH)
    bot.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
