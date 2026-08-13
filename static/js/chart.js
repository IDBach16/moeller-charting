/* The charting screen: zone grid, count auto-advance, submit, undo. */

/* Statcast attack zones laid onto a 9x9 grid.
   Heart is the middle 3x3; each ring is eight rectangles around it, which is why
   the numbering skips x5 -- that slot is the ring's hole. */
const ZONE_LAYOUT = [
  // waste ring: rows/cols 1-9, hole 2-8
  [31, 'waste', 1, 1, 2, 2],   [32, 'waste', 1, 2, 2, 9],   [33, 'waste', 1, 9, 2, 10],
  [34, 'waste', 2, 1, 9, 2],   [36, 'waste', 2, 9, 9, 10],
  [37, 'waste', 9, 1, 10, 2],  [38, 'waste', 9, 2, 10, 9],  [39, 'waste', 9, 9, 10, 10],
  // chase ring: rows/cols 2-8, hole 3-7
  [21, 'chase', 2, 2, 3, 3],   [22, 'chase', 2, 3, 3, 8],   [23, 'chase', 2, 8, 3, 9],
  [24, 'chase', 3, 2, 8, 3],   [26, 'chase', 3, 8, 8, 9],
  [27, 'chase', 8, 2, 9, 3],   [28, 'chase', 8, 3, 9, 8],   [29, 'chase', 8, 8, 9, 9],
  // shadow ring: rows/cols 3-7, hole 4-6
  [11, 'shadow', 3, 3, 4, 4],  [12, 'shadow', 3, 4, 4, 7],  [13, 'shadow', 3, 7, 4, 8],
  [14, 'shadow', 4, 3, 7, 4],  [16, 'shadow', 4, 7, 7, 8],
  [17, 'shadow', 7, 3, 8, 4],  [18, 'shadow', 7, 4, 8, 7],  [19, 'shadow', 7, 7, 8, 8],
  // heart: the middle 3x3
  [1, 'heart', 4, 4, 5, 5], [2, 'heart', 4, 5, 5, 6], [3, 'heart', 4, 6, 5, 7],
  [4, 'heart', 5, 4, 6, 5], [5, 'heart', 5, 5, 6, 6], [6, 'heart', 5, 6, 6, 7],
  [7, 'heart', 6, 4, 7, 5], [8, 'heart', 6, 5, 7, 6], [9, 'heart', 6, 6, 7, 7],
];

const BAND_LABEL = { heart: 'Heart', shadow: 'Shadow', chase: 'Chase', waste: 'Waste' };

let selectedZone = null;
let lastPitchId = null;

function buildZoneGrid() {
  const grid = document.getElementById('zoneGrid');
  if (!grid) return;
  ZONE_LAYOUT.forEach(([num, band, r1, c1, r2, c2]) => {
    const cell = document.createElement('div');
    cell.className = 'zone b-' + band;
    cell.style.gridArea = `${r1} / ${c1} / ${r2} / ${c2}`;
    cell.textContent = num;
    cell.dataset.zone = num;
    cell.dataset.band = band;
    cell.addEventListener('click', () => selectZone(num, band));
    grid.appendChild(cell);
  });
}

function selectZone(num, band) {
  selectedZone = num;
  document.querySelectorAll('.zone').forEach(z => {
    z.classList.toggle('on', Number(z.dataset.zone) === num);
  });
  document.getElementById('zoneValue').textContent = num;
  document.getElementById('zoneBand').textContent = '· ' + BAND_LABEL[band];
}

function clearZone() {
  selectedZone = null;
  document.querySelectorAll('.zone').forEach(z => z.classList.remove('on'));
  document.getElementById('zoneValue').textContent = '—';
  document.getElementById('zoneBand').textContent = '';
}

/* Ball in play reveals the contact fields; anything else hides them.
   A 3-2 count or two strikes can end the PA without contact, so the
   walk/strikeout block appears when the count makes that possible. */
function syncConditionalBlocks() {
  const result = chipValue('pitch_result');
  const balls = Number(chipValue('balls') || 0);
  const strikes = Number(chipValue('strikes') || 0);

  const inPlay = result === 'Ball in Play';
  document.getElementById('bipBlock').style.display = inPlay ? '' : 'none';

  const canEndPA = !inPlay && ((result === 'Ball' && balls >= 3) ||
    ((result === 'Called Strike' || result === 'Swinging Strike') && strikes >= 2));
  document.getElementById('paBlock').style.display = canEndPA ? '' : 'none';
  if (!canEndPA) setChip('pa_result', 'None');
}

/* Advance the count the way the pitch actually would.
   Fouls do not add a third strike. Anything that ends the PA resets to 0-0. */
function advanceCount(result, paResult) {
  let balls = Number(chipValue('balls') || 0);
  let strikes = Number(chipValue('strikes') || 0);

  const paOver = result === 'Ball in Play' || (paResult && paResult !== 'None');
  if (paOver) {
    setChip('balls', 0);
    setChip('strikes', 0);
    return true;
  }

  if (result === 'Ball') {
    balls = Math.min(3, balls + 1);
  } else if (result === 'Called Strike' || result === 'Swinging Strike') {
    strikes = Math.min(2, strikes + 1);
  } else if (result === 'Foul') {
    strikes = Math.min(2, strikes + 1);
  }
  setChip('balls', balls);
  setChip('strikes', strikes);
  return false;
}

function collectPitch() {
  const pitcherSel = document.getElementById('pitcher');
  const batterSel = document.getElementById('batter');
  const velo = document.getElementById('velo').value;
  const result = chipValue('pitch_result');
  const inPlay = result === 'Ball in Play';
  const paResult = document.getElementById('paBlock').style.display === 'none'
    ? 'None' : chipValue('pa_result');

  // Play result comes from the contact block when the ball is in play, and from
  // the walk/strikeout block otherwise. They can never both apply.
  let playResult = 'None';
  if (inPlay) playResult = chipValue('play_result');
  else if (paResult && paResult !== 'None') playResult = paResult;

  return {
    pitcher_id: pitcherSel.value,
    throws: chipValue('throws'),
    batter_id: batterSel.value || null,
    bats: batterSel.value ? chipValue('bats') : null,
    pitch_result: result,
    pitch_type: chipValue('pitch_type'),
    pitch_velocity: velo === '' ? null : velo,
    balls: Number(chipValue('balls') || 0),
    strikes: Number(chipValue('strikes') || 0),
    attack_zone: selectedZone,
    play_result: playResult,
    bip_position: inPlay ? chipValue('bip_position') : 'None',
    exit_velocity: inPlay ? chipValue('exit_velocity') : 'None',
    hit_type: inPlay ? chipValue('hit_type') : 'None',
    charter_name: document.getElementById('charter').value,
    _paResult: paResult,
  };
}

async function submitPitch() {
  const btn = document.getElementById('submitPitch');
  const pitch = collectPitch();

  if (!pitch.pitcher_id) { toast('Pick a pitcher first', true); return; }
  if (selectedZone === null) { toast('Tap a zone on the chart', true); return; }

  const paResult = pitch._paResult;
  delete pitch._paResult;

  btn.disabled = true;
  try {
    const res = await api('/api/sessions/' + window.SESSION_ID + '/pitches', {
      method: 'POST', body: JSON.stringify(pitch),
    });
    lastPitchId = res.id;
    document.getElementById('pitchCount').textContent = res.session_total;

    const paOver = advanceCount(pitch.pitch_result, paResult);
    clearZone();
    // Contact detail is per-pitch; never let it bleed into the next one.
    setChip('play_result', 'None');
    setChip('bip_position', 'None');
    setChip('exit_velocity', 'None');
    setChip('hit_type', 'None');
    setChip('pa_result', 'None');
    syncConditionalBlocks();

    toast(paOver ? 'Logged — new batter' : 'Logged');
    await loadLog();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function undoLast() {
  if (!lastPitchId) { toast('Nothing to undo', true); return; }
  try {
    await api('/api/pitches/' + lastPitchId, { method: 'DELETE' });
    lastPitchId = null;
    toast('Removed last pitch');
    await loadLog();
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadLog() {
  const tbody = document.getElementById('pitchLog');
  try {
    const rows = await api('/api/sessions/' + window.SESSION_ID + '/pitches');
    document.getElementById('pitchCount').textContent = rows.length;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">Nothing yet.</td></tr>';
      return;
    }
    if (rows.length) lastPitchId = rows[0].id;
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${escapeHtml(r.pitcher)}</td>
        <td>${escapeHtml(r.pitch_type)}</td>
        <td class="num">${r.pitch_velocity ?? ''}</td>
        <td>${escapeHtml(r.pitch_result)}${
          r.play_result && r.play_result !== 'None'
            ? ' <span style="color:var(--gold)">· ' + escapeHtml(r.play_result) + '</span>'
            : ''}</td>
        <td class="num">${r.attack_zone ?? ''}</td>
        <td><button class="btn-sm btn-danger del-pitch" data-id="${r.id}">×</button></td>
      </tr>`).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Could not load pitches.</td></tr>';
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('zoneGrid')) return;  // roster empty, form not rendered

  buildZoneGrid();
  loadLog();

  // Handedness follows the selected player, but stays overridable.
  const pitcherSel = document.getElementById('pitcher');
  const batterSel = document.getElementById('batter');
  const syncThrows = () => {
    const opt = pitcherSel.selectedOptions[0];
    if (opt && opt.dataset.throws) setChip('throws', opt.dataset.throws);
  };
  const syncBats = () => {
    const opt = batterSel.selectedOptions[0];
    if (opt && opt.dataset.bats) setChip('bats', opt.dataset.bats);
  };
  pitcherSel.addEventListener('change', syncThrows);
  batterSel.addEventListener('change', syncBats);
  syncThrows();

  ['pitch_result', 'balls', 'strikes'].forEach(id => {
    document.getElementById(id).addEventListener('chipchange', syncConditionalBlocks);
  });
  syncConditionalBlocks();

  document.getElementById('submitPitch').addEventListener('click', submitPitch);

  document.getElementById('pitchLog').addEventListener('click', async e => {
    const btn = e.target.closest('.del-pitch');
    if (!btn) return;
    try {
      await api('/api/pitches/' + btn.dataset.id, { method: 'DELETE' });
      if (String(lastPitchId) === btn.dataset.id) lastPitchId = null;
      toast('Pitch removed');
      await loadLog();
    } catch (err) { toast(err.message, true); }
  });

  document.addEventListener('keydown', e => {
    const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName);
    if (e.key === 'Enter' && !typing) { e.preventDefault(); submitPitch(); }
    if (e.key === 'Backspace' && !typing) { e.preventDefault(); undoLast(); }
  });
});
