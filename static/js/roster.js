/* Roster page. */

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

async function loadPlayers() {
  const tbody = document.getElementById('playerList');
  try {
    const rows = await api('/api/players?all=1');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No players yet.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(p => `
      <tr style="${p.is_active ? '' : 'opacity:.45'}">
        <td>${escapeHtml(p.name)}</td>
        <td>${escapeHtml(p.class_year || '')}</td>
        <td>${escapeHtml(p.throws || '')}</td>
        <td>${escapeHtml(p.bats || '')}</td>
        <td>${p.is_pitcher ? '<span class="tag tag-bullpen">P</span>' : ''}</td>
        <td style="text-align:right;white-space:nowrap">
          <button class="btn-sm toggle-active" data-id="${p.id}" data-active="${p.is_active ? 1 : 0}">
            ${p.is_active ? 'Deactivate' : 'Reactivate'}
          </button>
          <button class="btn-sm btn-danger del-player" data-id="${p.id}">×</button>
        </td>
      </tr>`).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Could not load the roster.</td></tr>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadPlayers();

  document.getElementById('addPlayer').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await api('/api/players', {
        method: 'POST',
        body: JSON.stringify({
          first_name: document.getElementById('first').value,
          last_name: document.getElementById('last').value,
          class_year: document.getElementById('class_year').value,
          throws: document.getElementById('throws').value,
          bats: document.getElementById('bats').value,
          is_pitcher: chipValue('is_pitcher') === '1',
        }),
      });
      e.target.reset();
      setChip('is_pitcher', '0');
      toast('Player added');
      await loadPlayers();
    } catch (err) { toast(err.message, true); }
  });

  document.getElementById('playerList').addEventListener('click', async e => {
    const toggle = e.target.closest('.toggle-active');
    const del = e.target.closest('.del-player');
    try {
      if (toggle) {
        await api('/api/players/' + toggle.dataset.id, {
          method: 'PUT',
          body: JSON.stringify({ is_active: toggle.dataset.active !== '1' }),
        });
        await loadPlayers();
      } else if (del) {
        if (!confirm('Delete this player?')) return;
        await api('/api/players/' + del.dataset.id, { method: 'DELETE' });
        toast('Player deleted');
        await loadPlayers();
      }
    } catch (err) { toast(err.message, true); }
  });
});
