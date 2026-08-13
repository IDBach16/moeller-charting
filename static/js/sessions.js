/* Sessions page: start one, delete one. */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('newSession');
  if (form) {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      try {
        const res = await api('/api/sessions', {
          method: 'POST',
          body: JSON.stringify({
            session_date: document.getElementById('s_date').value,
            session_type: chipValue('s_type'),
            charter_name: document.getElementById('s_charter').value,
            catcher_id: document.getElementById('s_catcher').value || null,
            notes: document.getElementById('s_notes').value,
          }),
        });
        window.location.href = '/session/' + res.id;
      } catch (err) {
        toast(err.message, true);
        btn.disabled = false;
      }
    });
  }

  document.querySelectorAll('.del-session').forEach(btn => {
    btn.addEventListener('click', async () => {
      const n = Number(btn.dataset.count || 0);
      // A session with pitches in it is a real loss -- make them say so.
      if (n > 0 && !confirm(`Delete this session and its ${n} charted pitch${n === 1 ? '' : 'es'}? This cannot be undone.`)) return;
      if (n === 0 && !confirm('Delete this empty session?')) return;
      try {
        await api('/api/sessions/' + btn.dataset.id + (n > 0 ? '?force=1' : ''),
                  { method: 'DELETE' });
        window.location.reload();
      } catch (err) { toast(err.message, true); }
    });
  });
});
