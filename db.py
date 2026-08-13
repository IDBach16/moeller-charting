"""
db.py -- schema and connection for the Moeller charting app.

One engine, driven by DATABASE_URL:

    DATABASE_URL unset      -> sqlite:///charting.db   (local dev, no Postgres needed)
    DATABASE_URL set        -> that database           (Railway Postgres in production)

Railway hands out `postgres://...` on some plugin versions; SQLAlchemy only accepts
`postgresql://`, so we rewrite it. Everything is declared through SQLAlchemy Core so the
same DDL runs on both backends -- no SERIAL-vs-AUTOINCREMENT branching.

Why Postgres and not a SQLite file like GC_App_2026: Railway's filesystem is ephemeral.
A charting app writes while you are standing on a mound, and a redeploy would take the
session with it.
"""

import os

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        MetaData, String, Table, Text, create_engine, func)

metadata = MetaData()

# --- reference data ----------------------------------------------------------

players = Table(
    "players", metadata,
    Column("id", Integer, primary_key=True),
    Column("first_name", String(60), nullable=False),
    Column("last_name", String(60), nullable=False),
    Column("class_year", String(10)),
    Column("throws", String(1), server_default="R"),   # R / L
    Column("bats", String(1), server_default="R"),     # R / L / S
    Column("is_pitcher", Boolean, server_default="0"),
    Column("is_active", Boolean, server_default="1"),
)

# --- a charting session ------------------------------------------------------
#
# Clark's app had only a Date column, so two bullpens on one day were
# indistinguishable. Same trap as counting pitches by date instead of game_key.
# Every pitch hangs off a session.

sessions = Table(
    "sessions", metadata,
    Column("id", Integer, primary_key=True),
    Column("session_date", String(10), nullable=False),      # YYYY-MM-DD
    Column("session_type", String(20), nullable=False),      # bullpen / live_ab / scrimmage / intrasquad
    Column("charter_name", String(60)),
    Column("catcher_id", Integer, ForeignKey("players.id")),
    Column("notes", Text),
    Column("created_at", DateTime, server_default=func.now()),
)

# --- one row per pitch -------------------------------------------------------
#
# Column names follow Clark's export so anything already written against that
# CSV keeps working. Handedness is copied onto the row rather than joined at read
# time: if a player is later corrected in the roster, past pitches keep what was
# actually true when they were thrown.

pitches = Table(
    "pitches", metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", Integer, ForeignKey("sessions.id"), nullable=False),

    Column("pitcher_id", Integer, ForeignKey("players.id"), nullable=False),
    Column("throws", String(1)),
    Column("batter_id", Integer, ForeignKey("players.id")),
    Column("bats", String(1)),

    Column("pitch_result", String(20), nullable=False),
    Column("pitch_type", String(20), nullable=False),
    Column("pitch_velocity", Integer),
    Column("balls", Integer, server_default="0"),
    Column("strikes", Integer, server_default="0"),
    Column("attack_zone", Integer),

    Column("play_result", String(24)),
    Column("bip_position", String(4)),
    Column("exit_velocity", String(40)),   # contact quality, Clark's naming kept
    Column("hit_type", String(16)),

    Column("charter_name", String(60)),
    Column("created_at", DateTime, server_default=func.now()),
)


# --- vocabularies ------------------------------------------------------------
# Single source of truth: the form renders from these and the API validates
# against them, so the two can never drift apart.

PITCH_RESULTS = ["Ball", "Called Strike", "Swinging Strike", "Foul", "Ball in Play"]

PITCH_TYPES = ["Fastball", "Sinker", "Curveball", "Slider", "Changeup", "Splitter"]

PLAY_RESULTS = ["None", "Groundout", "Flyout", "Line Out", "Single", "Double",
                "Triple", "Home Run", "Walk", "Called Strikeout",
                "Swinging Strikeout", "Sac Bunt", "Bunt For Hit"]

BIP_POSITIONS = ["None", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]

# Clark calls this "Exit Velocity" but the options are contact-quality buckets.
# Name kept for CSV compatibility; the label in the UI says what it is.
CONTACT_QUALITY = ["None", "Handle: Jammed / Miss-Hit", "Barrel: Squared / Solid",
                   "Sweet Spot: Flush / Damage"]

HIT_TYPES = ["None", "Ground Ball", "Fly Ball", "Line Drive"]

SESSION_TYPES = [("bullpen", "Bullpen"), ("live_ab", "Live ABs"),
                 ("scrimmage", "Scrimmage"), ("intrasquad", "Intrasquad")]

# Statcast attack zones. Heart 1-9, then three rings that each skip their centre.
ZONE_BANDS = {
    "heart": list(range(1, 10)),
    "shadow": [11, 12, 13, 14, 16, 17, 18, 19],
    "chase": [21, 22, 23, 24, 26, 27, 28, 29],
    "waste": [31, 32, 33, 34, 36, 37, 38, 39],
}
VALID_ZONES = {z for band in ZONE_BANDS.values() for z in band}


def zone_band(zone):
    """Which band a zone number belongs to, or None if it is not a real zone."""
    for name, zones in ZONE_BANDS.items():
        if zone in zones:
            return name
    return None


# --- engine ------------------------------------------------------------------

_engine = None


def database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        here = os.path.dirname(os.path.abspath(__file__))
        return "sqlite:///" + os.path.join(here, "charting.db")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_engine():
    global _engine
    if _engine is None:
        url = database_url()
        kwargs = {"future": True}
        if url.startswith("postgresql"):
            # Railway idles connections out; check them before handing them over.
            kwargs.update(pool_pre_ping=True, pool_recycle=280)
        _engine = create_engine(url, **kwargs)
        metadata.create_all(_engine)
    return _engine


def is_postgres():
    return database_url().startswith("postgresql")
