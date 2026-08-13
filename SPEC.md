# Moeller Charting App — spec

Recovered 2026-08-13 from the live Clark State app (`idbach16.shinyapps.io/Clark_State_app`)
because the local source is an unreadable OneDrive stub. This file **is** the outline —
the R source was never readable, so this is what we build from.

## Origin

`OneDrive\Desktop\Personal\Clark_State_app\Game_App.R` (33 KB) + `Game_App_DEV.R` (40 KB),
R/Shiny, deployed to shinyapps.io. Both files are OneDrive online-only placeholders and the
cloud file provider is not running, so every read fails with "the cloud file provider is not
running." Pinning with `attrib +P -U` did not help. Recovered the outline from the rendered
UI instead.

## Decisions (Ian, 2026-08-13)

- **Stack:** Flask / Python. Matches Pitcher_Card, Hitter_Card, Scouting_Agent, Moeller_Hub.
- **Storage:** Railway Postgres as system of record. Not SQLite — Railway's filesystem is
  ephemeral and a charting app writes on the field, so a redeploy mid-session would lose data.
- **Outline:** keep Clark's, with additions expected along the way.
- **Surfacing:** new card in `Moeller_Hub` (repo `IDBach16/moeller-hub`, branch `main`,
  live at `web-production-bf2c9.up.railway.app`).

## Clark's charting form — exact, as rendered

Three tabs: **Charting** | **Data** | **Plots (Coming Soon)**.

### Left column — who
| Field | Control | Clark's values |
|---|---|---|
| Charter Name | text | free |
| Pitcher Team Name | dropdown (`pitnm`) | only "Clark State College" |
| Pitcher | text | free |
| Pitcher Hand | dropdown (`p_throws`) | only "R" |
| Batter Team Name | dropdown (`batnm`) | only "Clark State College" |
| Batter | text | free |
| Batter Hand | dropdown (`stand`) | only "R" |

Note: every dropdown ships exactly one option — the handedness selects can't even pick L.
Treat these as stubs to replace, not as a design to copy.

### Middle column — the pitch
- **Pitch Result:** Ball · Called Strike · Swinging Strike · Foul · Ball in Play
- **Pitch Type:** Fastball · Sinker · Curveball · Slider · Changeup · Splitter
- **Pitch Velocity:** number, default 70
- **Balls:** number, default 0
- **Strikes:** number, default 0
- **Attack Zone:** number, default 1 — typed in by hand, 1–39
- **Play Result:** None · Groundout · Flyout · Line Out · Single · Double · Triple ·
  Home Run · Walk · Called Strikeout · Swinging Strikeout · Sac Bunt · Bunt For Hit
- **BIP Position:** None · 1B · 2B · 3B · SS · LF · CF · RF
- **Exit Velocity:** None · Handle: Jammed / Miss-Hit · Barrel: Squared / Solid ·
  Sweet Spot: Flush / Damage  ← contact quality, not a number despite the name
- **Hit Type:** None · Ground Ball · Fly Ball · Line Drive

### Right column
- **Submit Event** button
- **Attack Zone Chart** — static reference image, the Statcast 39-zone grid:
  - **1–9 Heart** (3×3 center)
  - **11–19 Shadow** (ring on the edge of the zone)
  - **21–29 Chase**
  - **31–39 Waste**

### Data tab — output columns, in order
```
pitcher_team_name, pitcher, throws, batter_team_name, batter, bats,
pitch_result, pitch_type, pitch_velocity, balls, strikes,
exit_velocity, hit_type, play_result, bip_position,
charter_name, attack_zone, Date
```
18 columns. One row per pitch. No game/session identifier — only `Date`.

### Plots tab
Placeholder. Never built.

## Gaps to close for Moeller

Things Clark's version does not do that this one has to:

1. **No session concept.** Only a `Date` column, so two bullpens on one day are
   indistinguishable. This is the same shape as the M7 bug just fixed in `reconcile.py`:
   date is not an identifier. Needs a real session row (date, type, notes) with pitches
   keyed to it.
2. **Free-text pitcher/batter names.** Guarantees spelling drift and makes joins to AWRE
   data impossible. Needs a roster table.
3. **Handedness dropdowns cannot select L.**
4. **Attack zone typed as a number.** Fine at a desk, bad on a phone in a bullpen.
5. **No auth.** The hub is gated with `HUB_PASSWORD`; this should match.
6. **No edit or delete.** A mis-keyed pitch is permanent.
