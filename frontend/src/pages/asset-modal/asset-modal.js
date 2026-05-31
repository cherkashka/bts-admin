/**
 * Модалка актива (создание/редактирование).
 * Шаблон формы — asset-modal.html. В этом файле HTML нет:
 * только DOM-операции (заполнение values, добавление option-ов).
 */
import { api } from '../../api/client.js';
import { openModal, validateRequired, applyValidationErrors } from '../../components/Modal/Modal.js';
import { toast } from '../../components/Toast/Toast.js';
import formTpl from './asset-modal.html?raw';

const ASSET_TYPES = [
  { value: 'laptop',     label: 'Ноутбук' },
  { value: 'desktop',    label: 'ПК' },
  { value: 'monitor',    label: 'Монитор' },
  { value: 'printer',    label: 'Принтер/МФУ' },
  { value: 'peripheral', label: 'Периферия' },
  { value: 'mobile',     label: 'Смартфон/Планшет' },
  { value: 'other',      label: 'Прочее' },
];

const STATUSES = [
  { value: 'installed', label: 'Установлен' },
  { value: 'in_use',    label: 'В использовании' },
  { value: 'repair',    label: 'На ремонте' },
  { value: 'retired',   label: 'Снят с эксплуатации' },
];

// ===== История актива (единый audit_log) =====
const ACTION_LABELS = { create: 'Создание', update: 'Изменение', delete: 'Удаление' };
const ACTION_COLORS = { create: '#10b981', update: '#f59e0b', delete: '#ef4444' };

const HISTORY_FIELD_LABELS = {
  name: 'Название', inventory_number: 'Инв. номер', serial_number: 'Серийный номер',
  asset_type: 'Тип', status: 'Статус', mol_name: 'МОЛ', mol_user_id: 'МОЛ (id)',
  mac_address: 'MAC', location: 'Расположение', comments: 'Комментарии',
  commission_date: 'Дата ввода', warranty_end_date: 'Конец гарантии',
  warranty_months: 'Гарантия (мес.)',
};

function fmtHistoryDateTime(value) {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtHistoryVal(v) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'да' : 'нет';
  if (typeof v === 'object') return JSON.stringify(v);
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    const d = new Date(v);
    if (!isNaN(d.getTime())) return d.toLocaleDateString('ru-RU');
  }
  return String(v);
}

/** Краткое текстовое описание изменений записи (без HTML). */
function summarizeEntry(entry) {
  if (entry.action === 'create') return 'Актив создан';
  if (entry.action === 'delete') return 'Актив удалён';
  const after = entry.after || {};
  const before = entry.before || {};
  const parts = Object.keys(after).map((k) => {
    const label = HISTORY_FIELD_LABELS[k] || k;
    return `${label}: ${fmtHistoryVal(before[k])} → ${fmtHistoryVal(after[k])}`;
  });
  return parts.join(';  ') || 'Без изменений';
}

function ymd(iso) {
  if (!iso) return '';
  try { return new Date(iso).toISOString().split('T')[0]; }
  catch { return ''; }
}

function appendOption(sel, value, label, selected = false, disabled = false) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  if (selected) opt.selected = true;
  if (disabled) opt.disabled = true;
  sel.appendChild(opt);
}

function buildBody(asset, usersList) {
  const root = document.createElement('div');
  root.innerHTML = formTpl;

  // Text inputs
  root.querySelector('input[name="name"]').value             = asset.name || '';
  root.querySelector('input[name="inventory_number"]').value = asset.inventory_number || '';
  root.querySelector('input[name="serial_number"]').value    = asset.serial_number || '';
  root.querySelector('input[name="mac_address"]').value      = asset.mac_address || '';
  root.querySelector('input[name="commission_date"]').value  = ymd(asset.commission_date);
  root.querySelector('input[name="warranty_months"]').value  = asset.warranty_months ?? '';
  root.querySelector('input[name="warranty_end_date"]').value = ymd(asset.warranty_end_date);
  root.querySelector('input[name="location"]').value         = asset.location || '';
  root.querySelector('textarea[name="comments"]').value      = asset.comments || '';

  // Тип актива
  const typeSel = root.querySelector('select[name="asset_type"]');
  appendOption(typeSel, '', 'Выберите тип', !asset.asset_type, true);
  for (const t of ASSET_TYPES) appendOption(typeSel, t.value, t.label, asset.asset_type === t.value);

  // МОЛ
  const molSel = root.querySelector('select[name="mol_user_id"]');
  appendOption(molSel, '', 'Не выбран', !asset.mol_user_id);
  for (const u of usersList) appendOption(molSel, u.id, u.full_name, asset.mol_user_id === u.id);

  // Статус
  const statusSel = root.querySelector('select[name="status"]');
  for (const s of STATUSES) appendOption(statusSel, s.value, s.label, asset.status === s.value);

  // Возвращаем DOM-узел (не строку): иначе .value/.selected теряются.
  return root;
}

/** Заполняет список истории клонами template-строки (DOM API, без HTML в JS). */
function renderHistory(bodyEl, entries) {
  const list    = bodyEl.querySelector('.asset-history-list');
  const loading = bodyEl.querySelector('.asset-history-loading');
  const empty   = bodyEl.querySelector('.asset-history-empty');
  const rowTpl  = bodyEl.querySelector('#asset-history-row');
  if (!list || !rowTpl) return;

  if (loading) loading.hidden = true;
  list.textContent = '';

  if (!entries.length) {
    if (empty) empty.hidden = false;
    return;
  }

  for (const entry of entries) {
    const node = rowTpl.content.cloneNode(true);
    const actionEl  = node.querySelector('.asset-history-action');
    const actorEl   = node.querySelector('.asset-history-actor');
    const timeEl    = node.querySelector('.asset-history-time');
    const changesEl = node.querySelector('.asset-history-changes');

    actionEl.textContent = ACTION_LABELS[entry.action] || entry.action;
    const c = ACTION_COLORS[entry.action] || '#6b7280';
    actionEl.style.background = `${c}20`;
    actionEl.style.color = c;
    actionEl.style.border = `1px solid ${c}55`;

    actorEl.textContent   = entry.actor_name || '—';
    timeEl.textContent    = fmtHistoryDateTime(entry.timestamp);
    changesEl.textContent = summarizeEntry(entry);

    list.appendChild(node);
  }
}

/** Показывает вкладки и подгружает историю актива из audit_log. */
function wireHistoryTabs(ctl, assetId) {
  const body  = ctl.bodyEl;
  const strip = body.querySelector('[data-asset-tabs]');
  if (!strip) return;
  strip.hidden = false;

  const btns   = body.querySelectorAll('[data-tab-btn]');
  const panels = body.querySelectorAll('[data-tab-panel]');
  let loaded = false;

  const activate = (name) => {
    btns.forEach(b => b.classList.toggle('is-active', b.dataset.tabBtn === name));
    panels.forEach(p => { p.hidden = p.dataset.tabPanel !== name; });
    // submit-кнопка нужна только на вкладке «Данные»
    if (ctl.submitBtn) ctl.submitBtn.style.visibility = name === 'history' ? 'hidden' : '';
    if (name === 'history' && !loaded) {
      loaded = true;
      loadHistory();
    }
  };

  async function loadHistory() {
    try {
      const entries = await api.get(
        `/audit?entity_type=asset&entity_id=${assetId}&limit=100`
      );
      renderHistory(body, entries);
    } catch (e) {
      console.error('Ошибка загрузки истории актива:', e);
      const loading = body.querySelector('.asset-history-loading');
      if (loading) loading.textContent = 'Не удалось загрузить историю';
    }
  }

  btns.forEach(b => b.addEventListener('click', () => activate(b.dataset.tabBtn)));
}

export async function openAssetModal({ mode = 'add', id = null, onSaved = null } = {}) {
  let asset = {};
  if (mode === 'edit' && id) {
    try { asset = await api.get(`/assets/${id}`); }
    catch (err) { toast.error('Ошибка загрузки актива: ' + err.message); return; }
  }

  let usersList = [];
  try { usersList = await api.get('/users'); }
  catch (e) { console.error('users load', e); }

  const body = buildBody(asset, usersList);

  openModal({
    title: mode === 'edit' ? 'Редактировать актив' : 'Новый актив',
    body,
    size: 'lg',
    submitText: mode === 'edit' ? 'Сохранить' : 'Создать',
    onCancel: () => {
      if (onSaved) return;
      if (window.location.hash !== '#/assets') window.location.hash = '/assets';
    },
    onOpen: (ctl) => {
      // Вкладка «История» — только в режиме редактирования (есть id).
      if (mode === 'edit' && id) wireHistoryTabs(ctl, id);

      const form   = ctl.form;
      const start  = form.elements['commission_date'];
      const months = form.elements['warranty_months'];
      const end    = form.elements['warranty_end_date'];

      const recalc = () => {
        if (start.value && months.value) {
          const s = new Date(start.value);
          if (!isNaN(s.getTime())) {
            const e = new Date(s);
            e.setMonth(e.getMonth() + parseInt(months.value));
            end.value = e.toISOString().split('T')[0];
          }
        }
      };
      start.addEventListener('change', recalc);
      months.addEventListener('input', recalc);

      form.querySelectorAll('input, select, textarea').forEach(el => {
        el.addEventListener('input',  () => el.classList.remove('has-error'));
        el.addEventListener('change', () => el.classList.remove('has-error'));
      });
    },
    onSubmit: async (data, ctl) => {
      const errors = {
        ...validateRequired(data, ['name', 'inventory_number', 'asset_type', 'serial_number']),
      };
      if (data.mac_address && !/^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/.test(data.mac_address)) {
        errors.mac_address = 'Неверный формат (AA:BB:CC:DD:EE:FF)';
      }
      if (data.name && data.name.length < 3) errors.name = 'Минимум 3 символа';
      if (data.inventory_number && data.inventory_number.length < 3) errors.inventory_number = 'Минимум 3 символа';

      if (Object.keys(errors).length > 0) {
        applyValidationErrors(ctl, errors);
        ctl.setError('Проверьте корректность полей');
        return;
      }

      const payload = {};
      for (const [k, v] of Object.entries(data)) {
        if (v === null || v === undefined || String(v).trim() === '') continue;
        if (k === 'commission_date' || k === 'warranty_end_date') {
          payload[k] = new Date(v).toISOString();
        } else if (k === 'warranty_months') {
          payload[k] = parseInt(v);
        } else {
          payload[k] = v;
        }
      }

      if (mode === 'edit' && id) {
        // Очищенные необязательные поля шлём как null — иначе PATCH не трогает
        // непереданные ключи и старое значение осталось бы в БД.
        const OPTIONAL = ['mol_user_id', 'mac_address', 'commission_date',
                          'warranty_months', 'warranty_end_date', 'location', 'comments'];
        for (const f of OPTIONAL) if (!(f in payload)) payload[f] = null;
        await api.patch(`/assets/${id}`, payload);
      } else {
        await api.post('/assets', payload);
      }

      ctl.close();
      if (onSaved) onSaved();
      else if (window.location.hash !== '#/assets') window.location.hash = '/assets';
    },
  });
}
