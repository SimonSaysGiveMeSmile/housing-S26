(() => {
  const cards = [...document.querySelectorAll('.latest-card')];
  const ids = ['search', 'budget', 'source', 'region', 'maxdistance', 'term', 'parking', 'furnished', 'sort'];
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
    const sortKey = {price: 'price', distance: 'distance', recommended: 'rank'}[controls.sort.value];
    const sorted = [...cards].sort((a, b) =>
      Number(a.dataset[sortKey]) - Number(b.dataset[sortKey]) || Number(a.dataset.rank) - Number(b.dataset.rank));
    for (const card of sorted) {
      const d = card.dataset;
      const term = controls.term.value;
      const timingGroups = {start: ['monthly', 'one_month', 'confirm'], monthly: ['monthly', 'one_month'], active: ['monthly', 'one_month', 'confirm', 'later'], review: ['monthly', 'one_month', 'confirm', 'later', 'unverified']};
      const timingFits = timingGroups[term] ? timingGroups[term].includes(d.group) : d.group === term;
      const source = controls.source.value;
      const sourceFits = source === 'all' || d.source === source;
      const regionFits = controls.region.value === 'all' || d.region === controls.region.value;
      const distanceFits = controls.maxdistance.value === 'all' || Number(d.distance) <= Number(controls.maxdistance.value);
      const parking = controls.parking.value;
      const parkingFits = parking === 'all' || (parking === 'offstreet' ? ['offstreet', 'driveway'].includes(d.parking) : d.parking === parking);
      const visible = Number(d.price) <= Number(controls.budget.value) && timingFits && parkingFits && sourceFits && regionFits && distanceFits
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
    controls.source.value = 'all';
    controls.region.value = 'all';
    controls.maxdistance.value = 'all';
    controls.term.value = 'start';
    controls.parking.value = 'all';
    controls.furnished.value = 'all';
    controls.sort.value = 'distance';
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
  document.getElementById('north').addEventListener('click', () => {
    reset();
    controls.region.value = 'north';
    controls.term.value = 'review';
    filter();
    document.querySelector('.filterbar').scrollIntoView({block: 'start', behavior: 'smooth'});
  });
  document.querySelectorAll('[data-source-preset]').forEach(button => {
    button.addEventListener('click', () => {
      reset();
      controls.source.value = button.dataset.sourcePreset;
      controls.term.value = 'active';
      filter();
      document.querySelector('.filterbar').scrollIntoView({block: 'start', behavior: 'smooth'});
    });
  });
  const dialog = document.getElementById('photo-dialog');
  let activePhotos = [], activeIndex = 0, activeLocation = '';
  function showPhoto(index) {
    activeIndex = (index + activePhotos.length) % activePhotos.length;
    const photo = document.getElementById('large-photo');
    photo.src = activePhotos[activeIndex];
    photo.alt = `Advertiser’s photo ${activeIndex + 1} of ${activeLocation}`;
    document.getElementById('photo-title').textContent = activeLocation;
    document.getElementById('photo-position').textContent = `${activeIndex + 1} of ${activePhotos.length}`;
  }
  document.querySelectorAll('[data-photo-index]').forEach(button => {
    button.addEventListener('click', () => {
      const gallery = button.closest('.listing-gallery');
      activePhotos = JSON.parse(gallery.dataset.photos);
      activeLocation = gallery.dataset.location;
      showPhoto(Number(button.dataset.photoIndex));
      dialog.showModal();
    });
  });
  document.getElementById('close-photo').addEventListener('click', () => dialog.close());
  document.getElementById('previous-photo').addEventListener('click', () => showPhoto(activeIndex - 1));
  document.getElementById('next-photo').addEventListener('click', () => showPhoto(activeIndex + 1));
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      showPhoto(activeIndex + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    }
  });
  filter();
})();
