"""
Moeller Charting App -- pitch-by-pitch charting for off-season bullpens and live ABs.

Rebuilt from the Clark State Shiny app (see SPEC.md) as Flask + Postgres so it can
sit on Railway next to the rest of the Moeller analytics suite.

    python app.py                 local, writes charting.db (SQLite)
    gunicorn app:app              production, writes DATABASE_URL (Railway Postgres)

Gated with the same HUB_PASSWORD as the hub, so one password covers the suite.
"""

import csv
import io
import os
from datetime import date, datetime, timedelta

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from sqlalchemy import delete, func, insert, select, update

import db
from db import (BIP_POSITIONS, CONTACT_QUALITY, HIT_TYPES, PITCH_RESULTS,
                PITCH_TYPES, PLAY_RESULTS, SESSION_TYPES, VALID_ZONES,
                ZONE_BANDS, get_engine, pitches, players, sessions, zone_band)

app = Flask(__name__)
APP_DIR = os.path.dirname(os.path.abspath(__file__))

app.secret_key = os.environ.get("SECRET_KEY", "moeller-charting-2027-secret")
app.permanent_session_lifetime = timedelta(days=30)

HUB_PASSWORD = os.environ.get("HUB_PASSWORD", "Held_2027")

PUBLIC_PATHS = {"/login", "/healthz", "/moeller-logo.png", "/shield.png",
                "/bg-field.jpg", "/favicon.ico", "/manifest.json"}


@app.before_request
def require_login():
    if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
        return None
    if not session.get("authed"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not authenticated"}), 401
        return redirect(url_for("login"))
    return None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == HUB_PASSWORD:
            session.permanent = True
            session["authed"] = True
            return redirect(url_for("index"))
        error = "Incorrect password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    return {"ok": True, "backend": "postgres" if db.is_postgres() else "sqlite"}


# ---------------------------------------------------------------------------
# Static odds and ends
# ---------------------------------------------------------------------------

@app.route("/moeller-logo.png")
def logo():
    return send_from_directory(APP_DIR, "moeller-logo.png")


@app.route("/shield.png")
def shield():
    return send_from_directory(APP_DIR, "shield.png")


@app.route("/bg-field.jpg")
def bg_field():
    return send_from_directory(APP_DIR, "bg-field.jpg")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(APP_DIR, "moeller-logo.png")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(APP_DIR, "manifest.json")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def _player_name(row):
    return f"{row.first_name} {row.last_name}".strip()


@app.route("/")
def index():
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(
            select(sessions).order_by(sessions.c.session_date.desc(), sessions.c.id.desc())
        ).all()
        counts = dict(c.execute(
            select(pitches.c.session_id, func.count()).group_by(pitches.c.session_id)
        ).all())
        roster = c.execute(
            select(players).where(players.c.is_active == True)  # noqa: E712
            .order_by(players.c.last_name, players.c.first_name)
        ).all()

    session_rows = [{
        "id": r.id,
        "session_date": r.session_date,
        "session_type": r.session_type,
        "charter_name": r.charter_name or "",
        "notes": r.notes or "",
        "pitch_count": counts.get(r.id, 0),
    } for r in rows]

    return render_template(
        "sessions.html",
        sessions=session_rows,
        session_types=SESSION_TYPES,
        catchers=[{"id": p.id, "name": _player_name(p)} for p in roster],
        today=date.today().isoformat(),
    )


@app.route("/session/<int:session_id>")
def chart(session_id):
    eng = get_engine()
    with eng.connect() as c:
        s = c.execute(select(sessions).where(sessions.c.id == session_id)).first()
        if not s:
            return redirect(url_for("index"))
        roster = c.execute(
            select(players).where(players.c.is_active == True)  # noqa: E712
            .order_by(players.c.last_name, players.c.first_name)
        ).all()

    return render_template(
        "chart.html",
        session_id=session_id,
        session_meta=dict(s._mapping),
        session_type_label=dict(SESSION_TYPES).get(s.session_type, s.session_type),
        pitchers=[{"id": p.id, "name": _player_name(p), "throws": p.throws or "R"}
                  for p in roster if p.is_pitcher],
        batters=[{"id": p.id, "name": _player_name(p), "bats": p.bats or "R"}
                 for p in roster],
        pitch_results=PITCH_RESULTS,
        pitch_types=PITCH_TYPES,
        play_results=PLAY_RESULTS,
        bip_positions=BIP_POSITIONS,
        contact_quality=CONTACT_QUALITY,
        hit_types=HIT_TYPES,
        zone_bands=ZONE_BANDS,
    )


@app.route("/roster")
def roster_page():
    return render_template("roster.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", session_types=SESSION_TYPES)


# ---------------------------------------------------------------------------
# API -- roster
# ---------------------------------------------------------------------------

@app.route("/api/players", methods=["GET"])
def api_players():
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(
            select(players).order_by(players.c.last_name, players.c.first_name)
        ).all()
    out = []
    for p in rows:
        if request.args.get("all") != "1" and not p.is_active:
            continue
        out.append({"id": p.id, "first_name": p.first_name, "last_name": p.last_name,
                    "name": _player_name(p), "class_year": p.class_year,
                    "throws": p.throws, "bats": p.bats,
                    "is_pitcher": bool(p.is_pitcher), "is_active": bool(p.is_active)})
    return jsonify(out)


@app.route("/api/players", methods=["POST"])
def api_add_player():
    d = request.get_json(force=True) or {}
    first, last = (d.get("first_name") or "").strip(), (d.get("last_name") or "").strip()
    if not first or not last:
        return jsonify({"error": "first and last name are required"}), 400
    eng = get_engine()
    with eng.begin() as c:
        res = c.execute(insert(players).values(
            first_name=first, last_name=last,
            class_year=(d.get("class_year") or "").strip() or None,
            throws=d.get("throws") or "R", bats=d.get("bats") or "R",
            is_pitcher=bool(d.get("is_pitcher")), is_active=True,
        ))
    return jsonify({"ok": True, "id": res.inserted_primary_key[0]})


@app.route("/api/players/<int:player_id>", methods=["PUT"])
def api_update_player(player_id):
    d = request.get_json(force=True) or {}
    vals = {}
    for key in ("first_name", "last_name", "class_year", "throws", "bats"):
        if key in d:
            vals[key] = d[key]
    for key in ("is_pitcher", "is_active"):
        if key in d:
            vals[key] = bool(d[key])
    if not vals:
        return jsonify({"error": "nothing to update"}), 400
    eng = get_engine()
    with eng.begin() as c:
        c.execute(update(players).where(players.c.id == player_id).values(**vals))
    return jsonify({"ok": True})


@app.route("/api/players/<int:player_id>", methods=["DELETE"])
def api_delete_player(player_id):
    eng = get_engine()
    with eng.begin() as c:
        used = c.execute(
            select(func.count()).select_from(pitches).where(
                (pitches.c.pitcher_id == player_id) | (pitches.c.batter_id == player_id))
        ).scalar()
        if used:
            # Same rule as GC_App_2026: never orphan charted data.
            return jsonify({"error": f"{used} charted pitches reference this player. "
                                     "Mark them inactive instead."}), 400
        c.execute(delete(players).where(players.c.id == player_id))
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API -- sessions
# ---------------------------------------------------------------------------

@app.route("/api/sessions", methods=["POST"])
def api_add_session():
    d = request.get_json(force=True) or {}
    stype = d.get("session_type")
    if stype not in dict(SESSION_TYPES):
        return jsonify({"error": "unknown session type"}), 400
    sdate = (d.get("session_date") or "").strip() or date.today().isoformat()
    try:
        datetime.strptime(sdate, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "session_date must be YYYY-MM-DD"}), 400

    eng = get_engine()
    with eng.begin() as c:
        res = c.execute(insert(sessions).values(
            session_date=sdate, session_type=stype,
            charter_name=(d.get("charter_name") or "").strip() or None,
            catcher_id=d.get("catcher_id") or None,
            notes=(d.get("notes") or "").strip() or None,
        ))
    return jsonify({"ok": True, "id": res.inserted_primary_key[0]})


@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    eng = get_engine()
    with eng.begin() as c:
        n = c.execute(select(func.count()).select_from(pitches)
                      .where(pitches.c.session_id == session_id)).scalar()
        if n and request.args.get("force") != "1":
            return jsonify({"error": f"session has {n} pitches", "pitch_count": n}), 409
        c.execute(delete(pitches).where(pitches.c.session_id == session_id))
        c.execute(delete(sessions).where(sessions.c.id == session_id))
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API -- pitches
# ---------------------------------------------------------------------------

def _clean_pitch(d):
    """Validate one submitted pitch. Returns (values, error)."""
    if d.get("pitch_result") not in PITCH_RESULTS:
        return None, "pitch_result is not one of the allowed values"
    if d.get("pitch_type") not in PITCH_TYPES:
        return None, "pitch_type is not one of the allowed values"

    zone = d.get("attack_zone")
    if zone in ("", None):
        zone = None
    else:
        try:
            zone = int(zone)
        except (TypeError, ValueError):
            return None, "attack_zone must be a number"
        if zone not in VALID_ZONES:
            return None, f"{zone} is not a valid attack zone"

    velo = d.get("pitch_velocity")
    if velo in ("", None):
        velo = None
    else:
        try:
            velo = int(round(float(velo)))
        except (TypeError, ValueError):
            return None, "pitch_velocity must be a number"
        if not 20 <= velo <= 110:
            return None, "pitch_velocity looks wrong (expected 20-110)"

    def bounded(name, lo, hi):
        try:
            v = int(d.get(name) or 0)
        except (TypeError, ValueError):
            return None
        return v if lo <= v <= hi else None

    balls, strikes = bounded("balls", 0, 3), bounded("strikes", 0, 2)
    if balls is None:
        return None, "balls must be 0-3"
    if strikes is None:
        return None, "strikes must be 0-2"

    def one_of(name, allowed):
        v = d.get(name) or "None"
        return v if v in allowed else "None"

    # Numeric contact readings, like the original Moeller Bullpen app recorded.
    def reading(name, lo, hi):
        v = d.get(name)
        if v in ("", None):
            return None, None
        try:
            v = int(round(float(v)))
        except (TypeError, ValueError):
            return None, f"{name} must be a number"
        if not lo <= v <= hi:
            return None, f"{name} looks wrong (expected {lo} to {hi})"
        return v, None

    ev, err = reading("exit_velo_mph", 20, 130)
    if err:
        return None, err
    la, err = reading("launch_angle", -90, 90)
    if err:
        return None, err

    if not d.get("pitcher_id"):
        return None, "pitcher is required"

    return {
        "pitcher_id": int(d["pitcher_id"]),
        "throws": (d.get("throws") or "R")[:1],
        "batter_id": int(d["batter_id"]) if d.get("batter_id") else None,
        "bats": (d.get("bats") or "R")[:1] if d.get("batter_id") else None,
        "pitch_result": d["pitch_result"],
        "pitch_type": d["pitch_type"],
        "pitch_velocity": velo,
        "balls": balls,
        "strikes": strikes,
        "attack_zone": zone,
        "play_result": one_of("play_result", PLAY_RESULTS),
        "bip_position": one_of("bip_position", BIP_POSITIONS),
        "exit_velocity": one_of("exit_velocity", CONTACT_QUALITY),
        "hit_type": one_of("hit_type", HIT_TYPES),
        "exit_velo_mph": ev,
        "launch_angle": la,
        "charter_name": (d.get("charter_name") or "").strip() or None,
    }, None


@app.route("/api/sessions/<int:session_id>/pitches", methods=["GET"])
def api_session_pitches(session_id):
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(
            select(pitches, players.c.first_name, players.c.last_name)
            .select_from(pitches.join(players, pitches.c.pitcher_id == players.c.id))
            .where(pitches.c.session_id == session_id)
            .order_by(pitches.c.id.desc())
        ).all()
    return jsonify([{
        "id": r.id, "pitcher": f"{r.first_name} {r.last_name}",
        "pitch_type": r.pitch_type, "pitch_result": r.pitch_result,
        "pitch_velocity": r.pitch_velocity, "attack_zone": r.attack_zone,
        "band": zone_band(r.attack_zone), "balls": r.balls, "strikes": r.strikes,
        "play_result": r.play_result, "hit_type": r.hit_type,
        "exit_velocity": r.exit_velocity, "bip_position": r.bip_position,
        "exit_velo_mph": r.exit_velo_mph, "launch_angle": r.launch_angle,
    } for r in rows])


@app.route("/api/sessions/<int:session_id>/pitches", methods=["POST"])
def api_add_pitch(session_id):
    d = request.get_json(force=True) or {}
    vals, err = _clean_pitch(d)
    if err:
        return jsonify({"error": err}), 400

    eng = get_engine()
    with eng.begin() as c:
        if not c.execute(select(sessions.c.id).where(sessions.c.id == session_id)).first():
            return jsonify({"error": "session not found"}), 404
        vals["session_id"] = session_id
        res = c.execute(insert(pitches).values(**vals))
        total = c.execute(select(func.count()).select_from(pitches)
                          .where(pitches.c.session_id == session_id)).scalar()
    return jsonify({"ok": True, "id": res.inserted_primary_key[0], "session_total": total})


@app.route("/api/pitches/<int:pitch_id>", methods=["DELETE"])
def api_delete_pitch(pitch_id):
    eng = get_engine()
    with eng.begin() as c:
        c.execute(delete(pitches).where(pitches.c.id == pitch_id))
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API -- dashboard
# ---------------------------------------------------------------------------

def _rate(num, den):
    return round(100.0 * num / den, 1) if den else None


def _summarise(rows):
    """Per-pitcher summary from raw pitch rows. Done in Python so the same code
    runs against SQLite locally and Postgres in production."""
    by_pitcher = {}
    for r in rows:
        p = by_pitcher.setdefault(r.name, {
            "pitcher": r.name, "pitches": 0, "strikes": 0, "swings": 0, "whiffs": 0,
            "in_zone": 0, "zoned": 0, "heart": 0, "chase": 0, "waste": 0,
            "first_pitch": 0, "first_pitch_strikes": 0, "bip": 0, "hard": 0,
            "velos": [], "evs": [], "types": {},
        })
        p["pitches"] += 1

        strike_like = r.pitch_result in ("Called Strike", "Swinging Strike",
                                         "Foul", "Ball in Play")
        if strike_like:
            p["strikes"] += 1
        if r.pitch_result in ("Swinging Strike", "Foul", "Ball in Play"):
            p["swings"] += 1
        if r.pitch_result == "Swinging Strike":
            p["whiffs"] += 1
        if r.balls == 0 and r.strikes == 0:
            p["first_pitch"] += 1
            if strike_like:
                p["first_pitch_strikes"] += 1

        band = zone_band(r.attack_zone)
        if band:
            p["zoned"] += 1
            if band in ("heart", "shadow"):
                p["in_zone"] += 1
            p[band] = p.get(band, 0) + 1

        if r.pitch_result == "Ball in Play":
            p["bip"] += 1
            # Hard contact from either signal: the quality bucket, or a real
            # exit-velo reading of 90+.
            if ((r.exit_velocity and r.exit_velocity.startswith(("Barrel", "Sweet Spot")))
                    or (r.exit_velo_mph is not None and r.exit_velo_mph >= 90)):
                p["hard"] += 1
            if r.exit_velo_mph is not None:
                p["evs"].append(r.exit_velo_mph)

        if r.pitch_velocity:
            p["velos"].append(r.pitch_velocity)
            t = p["types"].setdefault(r.pitch_type, {"n": 0, "velos": []})
            t["n"] += 1
            t["velos"].append(r.pitch_velocity)
        else:
            p["types"].setdefault(r.pitch_type, {"n": 0, "velos": []})["n"] += 1

    out = []
    for p in by_pitcher.values():
        velos = p.pop("velos")
        evs = p.pop("evs")
        types = p.pop("types")
        out.append({
            "pitcher": p["pitcher"],
            "pitches": p["pitches"],
            "strike_pct": _rate(p["strikes"], p["pitches"]),
            "whiff_pct": _rate(p["whiffs"], p["swings"]),
            "zone_pct": _rate(p["in_zone"], p["zoned"]),
            "heart_pct": _rate(p["heart"], p["zoned"]),
            "chase_pct": _rate(p["chase"], p["zoned"]),
            "waste_pct": _rate(p["waste"], p["zoned"]),
            "fps_pct": _rate(p["first_pitch_strikes"], p["first_pitch"]),
            "hard_pct": _rate(p["hard"], p["bip"]),
            "avg_ev": round(sum(evs) / len(evs), 1) if evs else None,
            "avg_velo": round(sum(velos) / len(velos), 1) if velos else None,
            "max_velo": max(velos) if velos else None,
            "mix": sorted(
                [{"pitch_type": k,
                  "n": v["n"],
                  "usage_pct": _rate(v["n"], p["pitches"]),
                  "avg_velo": round(sum(v["velos"]) / len(v["velos"]), 1) if v["velos"] else None,
                  "max_velo": max(v["velos"]) if v["velos"] else None}
                 for k, v in types.items()],
                key=lambda x: -x["n"]),
        })
    return sorted(out, key=lambda x: -x["pitches"])


def _dashboard_rows(conn):
    q = (select(pitches, players.c.first_name, players.c.last_name,
                sessions.c.session_type, sessions.c.session_date)
         .select_from(pitches
                      .join(players, pitches.c.pitcher_id == players.c.id)
                      .join(sessions, pitches.c.session_id == sessions.c.id)))

    stype = request.args.get("session_type")
    if stype and stype != "all":
        q = q.where(sessions.c.session_type == stype)
    since = request.args.get("since")
    if since:
        q = q.where(sessions.c.session_date >= since)
    pitcher_id = request.args.get("pitcher_id")
    if pitcher_id:
        q = q.where(pitches.c.pitcher_id == int(pitcher_id))

    rows = conn.execute(q).all()
    # attach a display name without another round trip
    return [type("Row", (), {**dict(r._mapping),
                             "name": f"{r.first_name} {r.last_name}"})() for r in rows]


@app.route("/api/dashboard")
def api_dashboard():
    eng = get_engine()
    with eng.connect() as c:
        rows = _dashboard_rows(c)
        n_sessions = c.execute(select(func.count()).select_from(sessions)).scalar()

    zones = {}
    for r in rows:
        if r.attack_zone:
            zones[r.attack_zone] = zones.get(r.attack_zone, 0) + 1

    return jsonify({
        "pitchers": _summarise(rows),
        "totals": {"pitches": len(rows), "sessions": n_sessions,
                   "pitchers": len({r.name for r in rows})},
        "zones": zones,
    })


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

# The original Moeller Bullpen app's 16 columns, in its exact order -- so anything
# written against that CSV keeps working. exit_velocity is the NUMBER there (the
# contact-quality bucket ships separately as contact_quality). Extras appended.
EXPORT_COLUMNS = ["pitcher", "throws", "batter", "bats", "pitch_result",
                  "pitch_type", "pitch_velocity", "balls", "strikes",
                  "exit_velocity", "launch_angle", "play_result", "bip_position",
                  "charter_name", "attack_zone", "Date",
                  "hit_type", "contact_quality",
                  "session_id", "session_type", "attack_zone_band"]


def _export_rows(session_id=None):
    eng = get_engine()
    pitcher = players.alias("pitcher")
    batter = players.alias("batter")
    q = (select(pitches, sessions.c.session_date, sessions.c.session_type,
                pitcher.c.first_name.label("p_first"), pitcher.c.last_name.label("p_last"),
                batter.c.first_name.label("b_first"), batter.c.last_name.label("b_last"))
         .select_from(pitches
                      .join(sessions, pitches.c.session_id == sessions.c.id)
                      .join(pitcher, pitches.c.pitcher_id == pitcher.c.id)
                      .outerjoin(batter, pitches.c.batter_id == batter.c.id))
         .order_by(pitches.c.id))
    if session_id:
        q = q.where(pitches.c.session_id == session_id)
    with eng.connect() as c:
        rows = c.execute(q).all()

    for r in rows:
        yield {
            "pitcher": f"{r.p_first} {r.p_last}",
            "throws": r.throws,
            "batter": f"{r.b_first} {r.b_last}" if r.b_first else "",
            "bats": r.bats or "",
            "pitch_result": r.pitch_result,
            "pitch_type": r.pitch_type,
            "pitch_velocity": r.pitch_velocity if r.pitch_velocity is not None else "",
            "balls": r.balls,
            "strikes": r.strikes,
            "exit_velocity": r.exit_velo_mph if r.exit_velo_mph is not None else "",
            "launch_angle": r.launch_angle if r.launch_angle is not None else "",
            "play_result": r.play_result,
            "bip_position": r.bip_position,
            "charter_name": r.charter_name or "",
            "attack_zone": r.attack_zone if r.attack_zone is not None else "",
            "Date": r.session_date,
            "hit_type": r.hit_type,
            "contact_quality": r.exit_velocity,
            "session_id": r.session_id,
            "session_type": r.session_type,
            "attack_zone_band": zone_band(r.attack_zone) or "",
        }


@app.route("/export.csv")
@app.route("/export/session/<int:session_id>.csv")
def export_csv(session_id=None):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, lineterminator="\n")
    w.writeheader()
    for row in _export_rows(session_id):
        w.writerow(row)
    name = f"moeller_charting_{session_id or 'all'}_{date.today().isoformat()}.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    app.run(debug=True, host="0.0.0.0", port=port)
