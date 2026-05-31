
import { api, notes, categories, assets, users } from '../../api/client.js';
import { openModal, validateRequired, applyValidationErrors } from '../../components/Modal/Modal.js';
import { toast } from '../../components/Toast/Toast.js';
import formTpl from './note-modal.html?raw';

function appendOption(sel, value, label, selected = false, attrs = {}) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  if (selected) opt.selected = true;
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== undefined && v !== null) opt.dataset[k] = v;
  }
  sel.appendChild(opt);
}

function buildBody({ noteData, categoriesList, assetsList, usersList, currentUserId, presetDate }) {
  const isEdit = !!noteData;
  const isSingleEvent = noteData ? noteData.event_start === noteData.event_end : true;
  const initialStart = noteData
    ? noteData.event_start.slice(0, 16)
    : (presetDate ? `${presetDate}T09:00` : '');
  const initialEnd = noteData && !isSingleEvent ? noteData.event_end.slice(0, 16) : '';

  const root = document.createElement('div');
  root.innerHTML = formTpl;

  root.querySelector('input[name="title"]').value      = noteData?.title || '';
  root.querySelector('textarea[name="content"]').value = noteData?.content || '';
  root.querySelector('input[name="event_start"]').value = initialStart;
  root.querySelector('input[name="event_end"]').value   = initialEnd;
  root.querySelector('input[name="is_single"]').checked = isSingleEvent;

  const endGroup = root.querySelector('.nm-end-group');
  if (isSingleEvent && endGroup) endGroup.classList.add('is-hidden');

  const catSel = root.querySelector('select[name="category_id"]');
  for (const c of categoriesList) {
    appendOption(catSel, c.id, c.name, noteData?.category_id === c.id, { color: c.color });
  }

  const assetSel = root.querySelector('select[name="related_asset_id"]');
  appendOption(assetSel, '', '— Не выбрано —', !noteData?.related_asset_id);
  for (const a of assetsList) {
    const aid = a._id || a.id;
    appendOption(assetSel, aid, `${a.name} (${a.inventory_number || 'б/н'})`,
                 noteData?.related_asset_id === aid);
  }

  const userSel = root.querySelector('select[name="related_user_id"]');
  appendOption(userSel, '', '— Не выбрано —', !noteData?.related_user_id);
  if (currentUserId) {
    appendOption(userSel, 'self', '— Я сам —',
                 noteData?.related_user_id === currentUserId);
  }
  for (const u of usersList) {
    const uid = u._id || u.id;
    appendOption(userSel, uid, u.full_name || u.username,
                 noteData?.related_user_id === uid);
  }

  return root;
}

export async function openNoteModal({ id = null, presetDate = null, onSaved = null, returnHash = '/calendar' } = {}) {
  let noteData = null;
  let assetsList = [], usersList = [], categoriesList = [];
  let currentUserId = null;

  try {
    const me = await api.authCheck();
    currentUserId = me.user?.id || me.user?._id;
  } catch {}

  if (id) {
    try { noteData = await notes.getById(id); }
    catch (e) { toast.error('Ошибка: ' + e.message); return; }
  }

  // Справочники тянем независимо: нет права на актив/сотрудника/категорию —
  // просто пустой список в соответствующем дропдауне, модалка не падает.
  const [a, u, c] = await Promise.all([
    assets.getAll().catch(() => []),
    users.getAll().catch(() => []),
    categories.getAll(true).catch(() => []),
  ]);
  assetsList = a || [];
  usersList = (u || []).filter(x => x.is_active !== false);
  categoriesList = (c || []).sort((x, y) => {
    if (x.is_default && !y.is_default) return -1;
    if (!x.is_default && y.is_default) return 1;
    return x.name.localeCompare(y.name);
  });

  const isEdit = !!noteData;
  const body = buildBody({ noteData, categoriesList, assetsList, usersList, currentUserId, presetDate });

  openModal({
    title: isEdit ? 'Редактировать запись' : 'Новая запись',
    body,
    size: 'lg',
    submitText: isEdit ? 'Сохранить' : 'Создать',
    onCancel: () => {
      if (onSaved) return;
      if (window.location.hash !== `#${returnHash}`) window.location.hash = returnHash;
    },
    onOpen: (ctl) => {
      const form = ctl.form;
      const catSelect = form.elements['category_id'];

      const updateColor = () => {
        const opt = catSelect.options[catSelect.selectedIndex];
        const color = opt?.dataset?.color || '#008080';
        catSelect.style.borderLeft = `4px solid ${color}`;
      };
      catSelect.addEventListener('change', updateColor);
      setTimeout(updateColor, 0);

      const isSingleCb = form.elements['is_single'];
      const endGroup   = ctl.bodyEl.querySelector('.nm-end-group');
      const startEl    = form.elements['event_start'];
      const endEl      = form.elements['event_end'];

      isSingleCb.addEventListener('change', (e) => {
        if (e.target.checked) {
          endGroup.classList.add('is-hidden');
          endEl.value = '';
        } else {
          endGroup.classList.remove('is-hidden');
          if (!endEl.value && startEl.value) endEl.value = startEl.value;
        }
      });

      form.querySelectorAll('input, select, textarea').forEach(el => {
        el.addEventListener('input',  () => el.classList.remove('has-error'));
        el.addEventListener('change', () => el.classList.remove('has-error'));
      });
    },
    onSubmit: async (data, ctl) => {
      const errors = validateRequired(data, ['title', 'event_start', 'category_id']);
      if (data.title && data.title.length < 2) errors.title = 'Минимум 2 символа';

      if (Object.keys(errors).length > 0) {
        applyValidationErrors(ctl, errors);
        ctl.setError('Проверьте корректность полей');
        return;
      }

      const isSingle = data.is_single === 'on';
      const payload = {
        title: data.title,
        content: data.content || null,
        event_start: new Date(data.event_start).toISOString(),
        event_end: isSingle
          ? new Date(data.event_start).toISOString()
          : (data.event_end ? new Date(data.event_end).toISOString() : new Date(data.event_start).toISOString()),
        category_id: data.category_id || null,
        related_asset_id: data.related_asset_id || null,
        related_user_id: null,
      };

      if (data.related_user_id === 'self' && currentUserId) {
        payload.related_user_id = currentUserId;
      } else if (data.related_user_id) {
        payload.related_user_id = data.related_user_id;
      }

      if (isEdit) await notes.update(id, payload);
      else        await notes.create(payload);

      ctl.close();
      if (onSaved) { onSaved(); return; }
      if (window.location.hash !== `#${returnHash}`) window.location.hash = returnHash;
    },
  });
}
