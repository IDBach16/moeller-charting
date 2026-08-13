/* Shared helpers: chip groups, toasts, fetch wrapper. */

function toast(msg, isError) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle('err', !!isError);
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), isError ? 4200 : 1700);
}

/* A chip group behaves like a radio group: exactly one selection. */
function chipValue(groupId) {
  const on = document.querySelector('#' + groupId + ' .chip.on');
  return on ? on.dataset.value : null;
}

function setChip(groupId, value) {
  const group = document.getElementById(groupId);
  if (!group) return;
  let matched = false;
  group.querySelectorAll('.chip').forEach(c => {
    const hit = c.dataset.value === String(value);
    c.classList.toggle('on', hit);
    if (hit) matched = true;
  });
  // Never leave a group with nothing selected.
  if (!matched) {
    const first = group.querySelector('.chip');
    if (first) first.classList.add('on');
  }
}

function initChips(root) {
  (root || document).querySelectorAll('.chips').forEach(group => {
    group.addEventListener('click', e => {
      const chip = e.target.closest('.chip');
      if (!chip || !group.contains(chip)) return;
      group.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
      chip.classList.add('on');
      group.dispatchEvent(new CustomEvent('chipchange', {
        detail: { value: chip.dataset.value }, bubbles: true
      }));
    });
  });
}

async function api(url, options) {
  const res = await fetch(url, Object.assign({
    headers: { 'Content-Type': 'application/json' }
  }, options || {}));
  let body = null;
  try { body = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) {
    throw new Error((body && body.error) || ('Request failed (' + res.status + ')'));
  }
  return body;
}

document.addEventListener('DOMContentLoaded', () => initChips());
