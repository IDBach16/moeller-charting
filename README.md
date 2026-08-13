# Moeller Charting App

Pitch-by-pitch charting for off-season bullpens and live ABs. Flask + Postgres,
built to sit on Railway beside the rest of the analytics suite.

Rebuilt from the Clark State Shiny app — see **[SPEC.md](SPEC.md)** for the recovered
original outline and what was deliberately changed.

## Run it locally

```
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:5060
```

With no `DATABASE_URL` set it writes a local `charting.db` (SQLite), so you can try it
without installing Postgres. Password is `HUB_PASSWORD`, default `Held_2027` — the same
one the hub uses.

```
python smoke_test.py              # 43 checks against a throwaway database
```

## Deploy to Railway

1. New project → deploy from this repo.
2. **Add the Postgres plugin.** It sets `DATABASE_URL` automatically, which is all the
   app needs — tables are created on first boot.
3. Set `HUB_PASSWORD` and `SECRET_KEY` in the service variables.
4. Copy the generated URL into `Moeller_Hub/app.py` (the Charting App card's `href`) and
   delete that card's `<div class="badge">Coming Soon</div>` line.

**Do not swap Postgres for a SQLite file.** Railway's filesystem is ephemeral; a redeploy
mid-session would take the bullpen with it. That is why this app does not follow
`GC_App_2026`'s pattern.

## How it's used

**Roster** first — add players, tick *Pitcher* for anyone who throws. Names come from
here so they are spelled the same way every time and can be joined to AWRE data later.

**Sessions** — start one before charting. A session is a date *plus* a type
(bullpen / live ABs / scrimmage / intrasquad), so two bullpens on the same day stay
separate. Clark's version had only a date and could not tell them apart.

**Charting** — pick the pitcher, tap the result, the type, and the zone, hit Submit.

- The count advances itself: a ball adds a ball, a strike adds a strike, a foul never
  adds a third one, and anything ending the plate appearance resets to 0-0.
- Contact fields (play result, hit type, contact quality, fielded by) only appear on
  *Ball in Play*. Walk/strikeout options only appear when the count allows one.
- `Enter` submits, `Backspace` undoes the last pitch. Any row in the session log can be
  deleted individually.
- Handedness follows the selected player but stays overridable.

**Dashboard** — per-pitcher rates, a location heatmap, pitch mix and velocity, filtered
by session type, date and pitcher.

## Export

`/export.csv`, or per session from the sessions list. The first 18 columns are Clark's
export in Clark's order, so anything already written against that CSV keeps working;
`session_id`, `session_type` and `attack_zone_band` are appended after them.

## Attack zones

Statcast's 39-zone scheme: **1–9 Heart**, **11–19 Shadow**, **21–29 Chase**,
**31–39 Waste**. Each ring skips its own centre (no 15, 25, 35) — that slot is the ring's
hole, filled by the ring inside it. The grid is a 9×9 CSS grid; the layout table lives in
`static/js/chart.js`.

The bands are coloured as an *ordinal* ramp (one hue, light in the middle → dark at the
edges) because they are ordered by distance from the middle of the zone, not four
unrelated categories. The dashboard heatmap is a separate single-hue sequential ramp in
gold, so "where pitches went" never gets confused with "which band is which".

## Files

| File | What it is |
|---|---|
| `app.py` | Flask routes, validation, dashboard maths, CSV export |
| `db.py` | Schema, the option vocabularies, engine setup |
| `smoke_test.py` | End-to-end checks — run before pushing |
| `templates/` | `sessions` · `chart` · `roster` · `dashboard` · `login` |
| `static/js/chart.js` | Zone grid, count logic, submit/undo |
| `static/js/dashboard.js` | Heatmap, pitch mix, tables |
| `SPEC.md` | The recovered Clark outline and the gaps it left |

## Not built yet

- Google Sheets mirror. Postgres is the system of record; a Sheet export can be added as
  a scheduled push if you want one.
- No link to AWRE pitch data. The roster makes that join possible later, but nothing
  reconciles charted pitches against `awre_data.csv` today.
- Catcher is stored on the session but not yet used anywhere in the dashboard.
