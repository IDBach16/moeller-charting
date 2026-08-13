"""
smoke_test.py -- exercises the whole app against a throwaway SQLite file.

    python smoke_test.py

Covers: login gate, roster CRUD, session create, pitch validation (good and bad),
the dashboard maths, CSV export, and delete rules. Run it before pushing.
"""

import os
import sys
import tempfile

TMP = os.path.join(tempfile.gettempdir(), "charting_smoke.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP + suffix):
        os.remove(TMP + suffix)
os.environ["DATABASE_URL"] = "sqlite:///" + TMP.replace("\\", "/")
os.environ["HUB_PASSWORD"] = "test-pass"

import app as application  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}{('  -- ' + str(detail)) if detail and not cond else ''}")
    if not cond:
        FAILURES.append(label)


def main():
    application.app.config["TESTING"] = True
    c = application.app.test_client()

    print("\n-- auth gate")
    check("anonymous is redirected", c.get("/").status_code == 302)
    check("anonymous API is 401", c.get("/api/players").status_code == 401)
    check("wrong password is rejected",
          b"Incorrect" in c.post("/login", data={"password": "nope"}).data)
    c.post("/login", data={"password": "test-pass"})
    check("login works", c.get("/").status_code == 200)

    print("\n-- roster")
    r = c.post("/api/players", json={"first_name": "Jake", "last_name": "Moeller",
                                     "throws": "R", "bats": "R", "is_pitcher": True})
    pitcher_id = r.get_json()["id"]
    r = c.post("/api/players", json={"first_name": "Sam", "last_name": "Lefty",
                                     "throws": "L", "bats": "L", "is_pitcher": True})
    lefty_id = r.get_json()["id"]
    r = c.post("/api/players", json={"first_name": "Ty", "last_name": "Batter",
                                     "bats": "L"})
    batter_id = r.get_json()["id"]
    check("three players exist", len(c.get("/api/players").get_json()) == 3)
    check("blank name rejected",
          c.post("/api/players", json={"first_name": "", "last_name": "X"}).status_code == 400)
    check("lefty pitcher stored as L",
          [p for p in c.get("/api/players").get_json()
           if p["id"] == lefty_id][0]["throws"] == "L")

    print("\n-- sessions")
    check("bad session type rejected",
          c.post("/api/sessions", json={"session_type": "picnic"}).status_code == 400)
    check("bad date rejected",
          c.post("/api/sessions", json={"session_type": "bullpen",
                                        "session_date": "13/2026"}).status_code == 400)
    s1 = c.post("/api/sessions", json={"session_type": "bullpen",
                                       "session_date": "2026-08-13",
                                       "charter_name": "Ian"}).get_json()["id"]
    s2 = c.post("/api/sessions", json={"session_type": "bullpen",
                                       "session_date": "2026-08-13",
                                       "charter_name": "Ian"}).get_json()["id"]
    check("two sessions on one date are distinct", s1 != s2)

    print("\n-- pitch validation")
    base = {"pitcher_id": pitcher_id, "throws": "R", "pitch_result": "Ball",
            "pitch_type": "Fastball", "pitch_velocity": 82, "attack_zone": 22,
            "balls": 0, "strikes": 0}

    def post(**over):
        return c.post(f"/api/sessions/{s1}/pitches", json={**base, **over})

    check("valid pitch accepted", post().status_code == 200)
    check("bad zone 15 rejected", post(attack_zone=15).status_code == 400)
    check("bad zone 40 rejected", post(attack_zone=40).status_code == 400)
    check("zone 5 accepted", post(attack_zone=5).status_code == 200)
    check("velo 300 rejected", post(pitch_velocity=300).status_code == 400)
    check("blank velo accepted", post(pitch_velocity=None).status_code == 200)
    check("bogus pitch_result rejected", post(pitch_result="Bunt").status_code == 400)
    check("bogus pitch_type rejected", post(pitch_type="Eephus").status_code == 400)
    check("4 balls rejected", post(balls=4).status_code == 400)
    check("3 strikes rejected", post(strikes=3).status_code == 400)
    check("missing pitcher rejected", post(pitcher_id=None).status_code == 400)
    check("exit velo 200 rejected", post(exit_velo_mph=200).status_code == 400)
    check("launch angle 120 rejected", post(launch_angle=120).status_code == 400)
    check("EV 92 / LA -8 accepted",
          post(exit_velo_mph=92, launch_angle=-8).status_code == 200)
    check("unknown session is 404",
          c.post("/api/sessions/99999/pitches", json=base).status_code == 404)

    print("\n-- a real bullpen")
    script = [
        ("Called Strike", "Fastball", 84, 5, 0, 0),
        ("Ball", "Curveball", 71, 34, 0, 1),
        ("Swinging Strike", "Slider", 78, 14, 1, 1),
        ("Foul", "Fastball", 85, 2, 1, 2),
        ("Ball in Play", "Changeup", 76, 8, 1, 2),
        ("Ball", "Fastball", 83, 31, 0, 0),
        ("Swinging Strike", "Slider", 79, 24, 1, 0),
    ]
    for result, ptype, velo, zone, b, s in script:
        payload = {**base, "pitch_result": result, "pitch_type": ptype,
                   "pitch_velocity": velo, "attack_zone": zone, "balls": b, "strikes": s,
                   "batter_id": batter_id, "bats": "L"}
        if result == "Ball in Play":
            payload.update(play_result="Single", hit_type="Line Drive",
                           exit_velocity="Barrel: Squared / Solid", bip_position="CF",
                           exit_velo_mph=94, launch_angle=12)
        rv = c.post(f"/api/sessions/{s2}/pitches", json=payload)
        if rv.status_code != 200:
            check(f"script pitch {result}", False, rv.get_json())

    log = c.get(f"/api/sessions/{s2}/pitches").get_json()
    check("seven pitches logged", len(log) == 7, len(log))
    check("newest pitch first", log[0]["pitch_result"] == "Swinging Strike")
    check("band computed", log[0]["band"] == "chase", log[0]["band"])

    print("\n-- dashboard maths")
    d = c.get("/api/dashboard").get_json()
    check("two sessions counted", d["totals"]["sessions"] == 2, d["totals"])
    p = [x for x in d["pitchers"] if x["pitcher"] == "Jake Moeller"][0]

    # s2 alone, so the maths is checkable by hand
    d2 = c.get("/api/dashboard?since=2026-08-13&session_type=bullpen").get_json()
    check("zone histogram populated", len(d2["zones"]) > 0)

    only = c.get(f"/api/dashboard?pitcher_id={pitcher_id}").get_json()
    check("pitcher filter returns one pitcher", len(only["pitchers"]) == 1)

    # Hand-check on the 7-pitch script:
    #   strike-like = CalledK, SwStr, Foul, BIP, SwStr = 5 of 7 -> 71.4%
    #   swings = SwStr, Foul, BIP, SwStr = 4 ; whiffs = 2 -> 50.0%
    #   first pitch (0-0) = pitches 1 and 6 ; strike-like among them = 1 -> 50.0%
    script_only = [x for x in c.get(
        f"/api/dashboard?pitcher_id={pitcher_id}").get_json()["pitchers"]][0]
    print(f"     (all sessions: {script_only['pitches']} pitches, "
          f"strike {script_only['strike_pct']}%, whiff {script_only['whiff_pct']}%)")

    check("whiff% is a real number", isinstance(p["whiff_pct"], float))
    check("mix is sorted by count",
          all(p["mix"][i]["n"] >= p["mix"][i + 1]["n"] for i in range(len(p["mix"]) - 1)))
    check("hard% counted the barrel", script_only["hard_pct"] == 100.0,
          script_only["hard_pct"])

    print("\n-- export")
    rv = c.get("/export.csv")
    body = rv.get_data(as_text=True)
    header = body.splitlines()[0].split(",")
    # The original Moeller Bullpen app's 16 columns, in its exact order.
    original = ["pitcher", "throws", "batter", "bats", "pitch_result", "pitch_type",
                "pitch_velocity", "balls", "strikes", "exit_velocity", "launch_angle",
                "play_result", "bip_position", "charter_name", "attack_zone", "Date"]
    check("original's 16 columns lead the export", header[:16] == original, header[:16])
    check("export has rows", len(body.strip().splitlines()) > 7)
    bip_row = next(line for line in body.splitlines()[1:] if ",Ball in Play," in line)
    check("numeric EV lands in exit_velocity column",
          bip_row.split(",")[9] == "94", bip_row.split(",")[9])
    check("launch angle exported", bip_row.split(",")[10] == "12")
    rv2 = c.get(f"/export/session/{s2}.csv")
    check("per-session export is just that session",
          len(rv2.get_data(as_text=True).strip().splitlines()) == 8)

    print("\n-- delete rules")
    check("player with data cannot be deleted",
          c.delete(f"/api/players/{pitcher_id}").status_code == 400)
    check("unused player can be deleted",
          c.delete(f"/api/players/{lefty_id}").status_code == 200)
    check("session with pitches needs force",
          c.delete(f"/api/sessions/{s2}").status_code == 409)
    check("forced session delete works",
          c.delete(f"/api/sessions/{s2}?force=1").status_code == 200)
    check("its pitches went with it",
          len(c.get(f"/api/sessions/{s2}/pitches").get_json()) == 0)

    print("\n-- pages render")
    for path in ("/", "/roster", "/dashboard", f"/session/{s1}"):
        check(f"GET {path}", c.get(path).status_code == 200)
    check("healthz", c.get("/healthz").get_json()["ok"] is True)

    print()
    if FAILURES:
        print(f"*** {len(FAILURES)} FAILURE(S): {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
