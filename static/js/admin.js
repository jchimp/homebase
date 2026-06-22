'use strict';

// Icon picker — delegated event handling so it works after HTMX swaps.

document.addEventListener('click', function (e) {
  // Click on an icon search result
  const opt = e.target.closest('.icon-opt');
  if (opt) {
    const picker = opt.closest('.icon-picker');
    if (!picker) return;
    selectIconRef(picker, opt.dataset.ref, opt.dataset.source || 'iconify');
    return;
  }

  // Favicon button
  if (e.target.closest('[data-picker-favicon]')) {
    const picker = e.target.closest('.icon-picker');
    if (!picker) return;
    resolveFaviconForPicker(picker);
    return;
  }

  // Clear button
  if (e.target.closest('[data-picker-clear]')) {
    const picker = e.target.closest('.icon-picker');
    if (!picker) return;
    clearIcon(picker);
    return;
  }
});

function selectIconRef(picker, ref, source) {
  setHidden(picker, 'icon_source', source);
  setHidden(picker, 'icon_ref', ref);

  if (source === 'iconify') {
    // Fetch the resolved SVG for storage; preview from CDN img tag
    fetch(`/api/icons/resolve?ref=${encodeURIComponent(ref)}`)
      .then(r => r.json())
      .then(data => {
        setHidden(picker, 'icon_svg', data.svg || '');
        updatePreview(picker, { ref, source: 'iconify', svg: data.svg });
      })
      .catch(() => {
        // Preview only — SVG will be empty but ref is saved
        updatePreview(picker, { ref, source: 'iconify', svg: '' });
      });
  }

  // Highlight selected option
  picker.querySelectorAll('.icon-opt').forEach(b => b.classList.toggle('is-selected', b.dataset.ref === ref));
}

function resolveFaviconForPicker(picker) {
  // Find the URL field in the nearest parent form
  const form = picker.closest('form');
  if (!form) return;
  const urlInput = form.querySelector('input[name="url"]');
  if (!urlInput || !urlInput.value) return;

  const url = urlInput.value;
  fetch(`/api/icons/favicon?url=${encodeURIComponent(url)}`)
    .then(r => r.json())
    .then(data => {
      if (!data.svg) return;
      setHidden(picker, 'icon_source', data.source || 'favicon');
      setHidden(picker, 'icon_ref', data.ref || '');
      setHidden(picker, 'icon_svg', data.svg);
      updatePreview(picker, data);
    })
    .catch(() => {});
}

function clearIcon(picker) {
  setHidden(picker, 'icon_source', '');
  setHidden(picker, 'icon_ref', '');
  setHidden(picker, 'icon_svg', '');
  updatePreview(picker, null);
  picker.querySelectorAll('.icon-opt').forEach(b => b.classList.remove('is-selected'));
}

function setHidden(picker, name, value) {
  const input = picker.querySelector(`input[name="${name}"]`);
  if (input) input.value = value;
}

function updatePreview(picker, icon) {
  const preview = picker.querySelector('.icon-picker__preview');
  if (!preview) return;

  if (!icon || (!icon.svg && !icon.ref)) {
    const itemName = (picker.dataset.itemName || '?').trim();
    const letter = (itemName[0] || '?').toUpperCase();
    preview.innerHTML = `<span class="icon-prev-letter">${escHtml(letter)}</span>`;
    return;
  }

  if (icon.source === 'iconify' && icon.ref) {
    const parts = icon.ref.split(':');
    if (parts.length === 2) {
      const src = `https://api.iconify.design/${parts[0]}/${parts[1]}.svg`;
      preview.innerHTML = `<span class="icon-opt__img" role="img" style="-webkit-mask-image:url(${escHtml(src)});mask-image:url(${escHtml(src)})"></span>`;
      return;
    }
  }

  if (icon.svg) {
    // For data-URI favicons or inline SVG
    if (icon.svg.startsWith('data:')) {
      preview.innerHTML = `<img src="${escHtml(icon.svg)}" width="32" height="32" alt="">`;
    } else {
      preview.innerHTML = icon.svg;
    }
  }
}

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Drag-to-reorder (SortableJS) ─────────────────────────

let _sortInstances = [];

function initSortable() {
  if (typeof Sortable === 'undefined') return;

  _sortInstances.forEach(s => s.destroy());
  _sortInstances = [];

  const appsSection = document.getElementById('apps-section');
  if (appsSection) {
    // Group-level reorder
    _sortInstances.push(new Sortable(appsSection, {
      animation: 150,
      handle: '.drag-handle--group',
      draggable: '.bm-group',
      onEnd() {
        const ids = [...appsSection.querySelectorAll(':scope > .bm-group')]
          .map(el => el.id.replace('grp-', ''));
        fetch('/admin/apps/groups/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ids),
        });
      },
    }));

    // Item-level reorder within each group
    appsSection.querySelectorAll('.bm-links').forEach(ul => {
      const grpEl = ul.closest('.bm-group');
      const gid = grpEl?.id?.replace('grp-', '');
      if (!gid) return;
      _sortInstances.push(new Sortable(ul, {
        animation: 150,
        handle: '.drag-handle--item',
        draggable: '.bm-link',
        onEnd() {
          const ids = [...ul.querySelectorAll(':scope > .bm-link')]
            .map(el => el.id.replace('app-', ''));
          fetch(`/admin/apps/groups/${gid}/items/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ids),
          });
        },
      }));
    });
  }

  const bmSection = document.getElementById('bookmarks-section');
  if (bmSection) {
    // Group-level reorder
    _sortInstances.push(new Sortable(bmSection, {
      animation: 150,
      handle: '.drag-handle--group',
      draggable: '.bm-group',
      onEnd() {
        const ids = [...bmSection.querySelectorAll(':scope > .bm-group')]
          .map(el => el.id.replace('grp-', ''));
        fetch('/admin/bookmarks/groups/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ids),
        });
      },
    }));

    // Link-level reorder within each group
    bmSection.querySelectorAll('.bm-links').forEach(ul => {
      const grpEl = ul.closest('.bm-group');
      const gid = grpEl?.id?.replace('grp-', '');
      if (!gid) return;
      _sortInstances.push(new Sortable(ul, {
        animation: 150,
        handle: '.drag-handle--item',
        draggable: '.bm-link',
        onEnd() {
          const ids = [...ul.querySelectorAll(':scope > .bm-link')]
            .map(el => el.id.replace('lnk-', ''));
          fetch(`/admin/bookmarks/groups/${gid}/links/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ids),
          });
        },
      }));
    });
  }
}

document.addEventListener('DOMContentLoaded', initSortable);
document.addEventListener('htmx:afterSwap', function (e) {
  if (e.target.id === 'apps-section' || e.target.id === 'bookmarks-section') {
    initSortable();
  }
});
