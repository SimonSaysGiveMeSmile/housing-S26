(() => {
  const cards = [...document.querySelectorAll('.latest-card')];
  const ids = ['search', 'budget', 'term', 'parking', 'furnished', 'sort'];
  const controls = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const contactKey = 'housingContacted';
  let contacts = {};
  try {
    const saved = JSON.parse(localStorage.getItem(contactKey) || '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) contacts = saved;
  } catch (_) {}

  function filter() {
    const q = controls.search.value.trim().toLowerCase();
    let shown = 0;
    const sorted = [...cards].sort((a, b) => controls.sort.value === 'price'
      ? Number(a.dataset.price) - Number(b.dataset.price) || Number(a.dataset.rank) - Number(b.dataset.rank)
      : Number(a.dataset.rank) - Number(b.dataset.rank));
    for (const card of sorted) {
      const d = card.dataset;
      const term = controls.term.value;
      const timingFits = term === 'all' || (term === 'start' ? ['monthly', 'confirm'].includes(d.group) : d.group === term);
      const parking = controls.parking.value;
      const parkingFits = parking === 'all' || (parking === 'offstreet' ? ['offstreet', 'driveway'].includes(d.parking) : d.parking === parking);
      const visible = Number(d.price) <= Number(controls.budget.value) && timingFits && parkingFits
        && (controls.furnished.value === 'all' || d.furnished === controls.furnished.value)
        && (!q || d.text.includes(q));
      card.hidden = !visible;
      if (visible) shown++;
      document.getElementById('listings').appendChild(card);
    }
    document.getElementById('shown').textContent = shown;
    document.getElementById('empty').hidden = shown > 0;
  }

  function reset() {
    controls.search.value = '';
    controls.budget.value = '1500';
    controls.term.value = 'start';
    controls.parking.value = 'all';
    controls.furnished.value = 'all';
    controls.sort.value = 'recommended';
  }

  let feedbackTimer;
  function feedback(message) {
    clearTimeout(feedbackTimer);
    document.getElementById('feedback').textContent = message;
    feedbackTimer = setTimeout(() => { document.getElementById('feedback').textContent = ''; }, 3500);
  }

  function paint(card, on) {
    card.dataset.contacted = on ? '1' : '0';
    card.classList.toggle('contacted', on);
    const button = card.querySelector('.mark-contact');
    button.classList.toggle('on', on);
    button.setAttribute('aria-pressed', String(on));
    button.textContent = on ? '✓ Reached out' : 'Mark as reached out';
  }

  for (const card of cards) {
    if (Object.prototype.hasOwnProperty.call(contacts, card.dataset.id)) paint(card, Boolean(contacts[card.dataset.id]));
    card.querySelector('.mark-contact').addEventListener('click', () => {
      const on = card.dataset.contacted !== '1';
      contacts[card.dataset.id] = on;
      paint(card, on);
      try {
        localStorage.setItem(contactKey, JSON.stringify(contacts));
        feedback(on ? 'Marked as reached out. No message sent.' : 'Reached-out mark removed.');
      } catch (_) { feedback('Updated for this visit; browser storage is unavailable.'); }
    });
    card.querySelector('.copy-inquiry').addEventListener('click', async () => {
      const inquiry = document.getElementById('inquiry');
      try {
        await navigator.clipboard.writeText(inquiry.textContent);
        feedback('Inquiry copied. Review it before sending.');
      } catch (_) {
        inquiry.closest('details').open = true;
        const range = document.createRange();
        range.selectNodeContents(inquiry);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        inquiry.scrollIntoView({block: 'center'});
        feedback('Inquiry selected; copy it with your keyboard.');
      }
    });
  }
  for (const control of Object.values(controls)) control.addEventListener(control.type === 'search' ? 'input' : 'change', filter);
  document.getElementById('reset').addEventListener('click', () => { reset(); filter(); });
  document.getElementById('best').addEventListener('click', () => { reset(); controls.term.value = 'monthly'; filter(); });
  filter();
})();
