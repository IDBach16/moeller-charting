/* Coach dashboard.
 *
 * Two visual encodings, each with one job:
 *   - attack zone heatmap  -> magnitude, so a single hue light->dark (gold ramp,
 *     lowest step sitting near the navy surface, contrast 1.5 -> 10.3 across it)
 *   - pitch mix            -> identity, so categorical hues in a FIXED order,
 *     assigned per pitch type and never cycled, so a filter that drops a pitch
 *     type never repaints the others.
 * Both carry a hover tooltip; the tables below are the table view.
 */

/* sequential, low -> high (one hue) */
const HEAT_RAMP = ['#403938', '#625440', '#847049', '#a68c52', '#c5a55a', '#dec78e'];

/* categorical, fixed slot order -- validated against the #1a1a2e surface */
const TYPE_COLOR = {
  'Fastball': '#3987e5',
  'Sinker': '#d95926',
  'Curveball': '#199e70',
  'Slider': '#c98500',
  'Changeup': '#d55181',
  'Splitter': '#008300',
};
const TYPE_ORDER = Object.keys(TYPE_COLOR);

const ZONE_LAYOUT = [
  [31, 1, 1, 2, 2], [32, 1, 2, 2, 9], [33, 1, 9, 2, 10],
  [34, 2, 1, 9, 2], [36, 2, 9, 9, 10],
  [37, 9, 1, 10, 2], [38, 9, 2, 10, 9], [39, 9, 9, 10, 10],
  [21, 2, 2, 3, 3], [22, 2, 3, 3, 8], [23, 2, 8, 3, 9],
  [24, 3, 2, 8, 3], [26, 3, 8, 8, 9],
  [27, 8, 2, 9, 3], [28, 8, 3, 9, 8], [29, 8, 8, 9, 9],
  [11, 3, 3, 4, 4], [12, 3, 4, 4, 7], [13, 3, 7, 4, 8],
  [14, 4, 3, 7, 4], [16, 4, 7, 7, 8],
  [17, 7, 3, 8, 4], [18, 7, 4, 8, 7], [19, 7, 7, 8, 8],
  [1, 4, 4, 5, 5], [2, 4, 5, 5, 6], [3, 4, 6, 5, 7],
  [4, 5, 4, 6, 5], [5, 5, 5, 6, 6], [6, 5, 6, 6, 7],
  [7, 6, 4, 7, 5], [8, 6, 5, 7, 6], [9, 6, 6, 7, 7],
];

const BAND_OF = z => z < 10 ? 'Heart' : z < 20 ? 'Shadow' : z < 30 ? 'Chase' : 'Waste';

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

const fmt = v => (v === null || v === undefined) ? '—' : v;
const pct = v => (v === null || v === undefined) ? '—' : v + '%';

/* ---- tooltip ---- */
const tip = () => document.getElementById('vizTip');
function showTip(html, e) {
  const t = tip();
  t.innerHTML = html;
  t.classList.add('show');
  const pad = 14;
  let x = e.clientX + pad, y = e.clientY + pad;
  const r = t.getBoundingClientRect();
  if (x + r.width > window.innerWidth - 8) x = e.clientX - r.width - pad;
  if (y + r.height > window.innerHeight - 8) y = e.clientY - r.height - pad;
  t.style.left = x + 'px';
  t.style.top = y + 'px';
}
function hideTip() { tip().classList.remove('show'); }

/* ---- heatmap ---- */
function drawHeat(zones) {
  const grid = document.getElementById('heatGrid');
  grid.innerHTML = '';
  const counts = Object.values(zones).map(Number);
  const max = counts.length ? Math.max(...counts) : 0;
  const total = counts.reduce((a, b) => a + b, 0);

  ZONE_LAYOUT.forEach(([num, r1, c1, r2, c2]) => {
    const n = Number(zones[num] || 0);
    // Bucket into the ramp. Zero keeps the lowest step so the grid stays legible
    // as a grid even where nothing was thrown.
    const cell = document.createElement('div');
    cell.className = 'zone';
    cell.style.gridArea = `${r1} / ${c1} / ${r2} / ${c2}`;

    if (n === 0) {
      // "Nothing thrown here" must not look like "one pitch here" -- an empty
      // cell drops to the surface with a hairline, rather than taking step 1.
      cell.style.background = 'transparent';
      cell.style.boxShadow = 'inset 0 0 0 1px rgba(197,165,90,.16)';
      cell.style.color = 'rgba(255,255,255,.22)';
    } else {
      const idx = Math.min(HEAT_RAMP.length - 1,
                           1 + Math.floor((n / max) * (HEAT_RAMP.length - 1.001)));
      cell.style.background = HEAT_RAMP[idx];
      cell.style.color = idx >= 4 ? 'rgba(15,15,30,.85)' : 'rgba(255,255,255,.75)';
    }
    cell.textContent = n || '';
    cell.addEventListener('mousemove', e => showTip(
      `Zone <b>${num}</b> · ${BAND_OF(num)}<br/>${n} pitch${n === 1 ? '' : 'es'}` +
      (total ? ` · ${(100 * n / total).toFixed(1)}%` : ''), e));
    cell.addEventListener('mouseleave', hideTip);
    grid.appendChild(cell);
  });

  document.getElementById('heatTotal').textContent =
    total ? `${total} located pitch${total === 1 ? '' : 'es'}` : 'No located pitches yet';
}

/* ---- pitch mix ---- */
function drawMix(pitchers) {
  const legend = document.getElementById('mixLegend');
  const chart = document.getElementById('mixChart');

  const present = TYPE_ORDER.filter(t =>
    pitchers.some(p => p.mix.some(m => m.pitch_type === t && m.n > 0)));

  // A legend is always present once there are two or more series.
  legend.innerHTML = present.length > 1
    ? present.map(t =>
        `<span><i style="background:${TYPE_COLOR[t]}"></i>${escapeHtml(t)}</span>`).join('')
    : '';

  if (!pitchers.length) {
    chart.innerHTML = '<div class="empty">Nothing charted yet.</div>';
    return;
  }

  chart.innerHTML = pitchers.map(p => {
    const segs = TYPE_ORDER
      .map(t => p.mix.find(m => m.pitch_type === t))
      .filter(m => m && m.n > 0)
      .map(m => {
        // Label only where the segment is wide enough to hold one.
        const label = m.usage_pct >= 12 ? Math.round(m.usage_pct) + '%' : '';
        return `<div class="mix-seg" style="flex:${m.n};background:${TYPE_COLOR[m.pitch_type]}"
                     data-tip="${escapeHtml(m.pitch_type)}|${m.n}|${m.usage_pct}|${m.avg_velo ?? ''}"
                >${label}</div>`;
      }).join('');
    return `<div class="mix-row">
      <div class="mix-head"><b>${escapeHtml(p.pitcher)}</b><span>${p.pitches} pitches</span></div>
      <div class="mix-bar">${segs}</div>
    </div>`;
  }).join('');

  chart.querySelectorAll('.mix-seg').forEach(seg => {
    seg.addEventListener('mousemove', e => {
      const [type, n, usage, velo] = seg.dataset.tip.split('|');
      showTip(`<b>${escapeHtml(type)}</b><br/>${n} thrown · ${usage}%` +
              (velo ? `<br/>avg ${velo} mph` : ''), e);
    });
    seg.addEventListener('mouseleave', hideTip);
  });
}

/* ---- tables ---- */
function drawTables(pitchers) {
  const tbody = document.getElementById('pitcherTable');
  if (!pitchers.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty">Nothing charted yet.</td></tr>';
    document.getElementById('veloTable').innerHTML =
      '<tr><td colspan="6" class="empty">Nothing charted yet.</td></tr>';
    return;
  }
  tbody.innerHTML = pitchers.map(p => `
    <tr>
      <td>${escapeHtml(p.pitcher)}</td>
      <td class="num">${p.pitches}</td>
      <td class="num">${pct(p.strike_pct)}</td>
      <td class="num">${pct(p.fps_pct)}</td>
      <td class="num">${pct(p.whiff_pct)}</td>
      <td class="num">${pct(p.zone_pct)}</td>
      <td class="num">${pct(p.heart_pct)}</td>
      <td class="num">${pct(p.chase_pct)}</td>
      <td class="num">${pct(p.hard_pct)}</td>
      <td class="num">${fmt(p.avg_velo)}</td>
      <td class="num">${fmt(p.max_velo)}</td>
    </tr>`).join('');

  const rows = [];
  pitchers.forEach(p => p.mix.forEach(m => rows.push(`
    <tr>
      <td>${escapeHtml(p.pitcher)}</td>
      <td><i style="display:inline-block;width:9px;height:9px;border-radius:2px;
                   background:${TYPE_COLOR[m.pitch_type] || 'var(--faint)'};
                   margin-right:.4rem"></i>${escapeHtml(m.pitch_type)}</td>
      <td class="num">${m.n}</td>
      <td class="num">${pct(m.usage_pct)}</td>
      <td class="num">${fmt(m.avg_velo)}</td>
      <td class="num">${fmt(m.max_velo)}</td>
    </tr>`)));
  document.getElementById('veloTable').innerHTML = rows.join('');
}

function drawTotals(t) {
  document.getElementById('totals').innerHTML = `
    <div class="stat"><div class="k">Pitches</div><div class="v">${t.pitches}</div></div>
    <div class="stat"><div class="k">Pitchers</div><div class="v">${t.pitchers}</div></div>
    <div class="stat"><div class="k">Sessions</div><div class="v">${t.sessions}</div></div>`;
}

/* ---- load ---- */
async function load() {
  const params = new URLSearchParams();
  const type = document.getElementById('f_type').value;
  const since = document.getElementById('f_since').value;
  const pitcher = document.getElementById('f_pitcher').value;
  if (type && type !== 'all') params.set('session_type', type);
  if (since) params.set('since', since);
  if (pitcher) params.set('pitcher_id', pitcher);

  try {
    const data = await api('/api/dashboard?' + params.toString());
    drawTotals(data.totals);
    drawTables(data.pitchers);
    drawHeat(data.zones);
    drawMix(data.pitchers);
  } catch (err) {
    toast(err.message, true);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const players = await api('/api/players');
    const sel = document.getElementById('f_pitcher');
    players.filter(p => p.is_pitcher).forEach(p => {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.name;
      sel.appendChild(o);
    });
  } catch (e) { /* dashboard still works without the filter populated */ }

  ['f_type', 'f_since', 'f_pitcher'].forEach(id =>
    document.getElementById(id).addEventListener('change', load));
  document.getElementById('f_clear').addEventListener('click', () => {
    document.getElementById('f_type').value = 'all';
    document.getElementById('f_since').value = '';
    document.getElementById('f_pitcher').value = '';
    load();
  });

  load();
});
