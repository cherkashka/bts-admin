/**
 * Модалка задачи (add / edit / status).
 * Шаблоны — task-modal.html. В JS — только DOM-операции.
 */
import { api } from '../../api/client.js';
import { openModal, validateRequired, applyValidationErrors } from '../../components/Modal/Modal.js';
import { toast } from '../../components/Toast/Toast.js';
import tplHtml from './task-modal.html?raw';

let _templatesHost = null;
function ensureTemplates() {
  if (_templatesHost) return _templatesHost;
  _templatesHost = document.createElement('div');
  _templatesHost.innerHTML = tplHtml;
  return _templatesHost;
}
function cloneTemplate(id) {
  const tpl = ensureTemplates().querySelector(`#${id}`);
  if (!tpl) throw new Error(`Template #${id} not found`);
  return tpl.content.cloneNode(true);
}

function isoToInputDateTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ''; }
}

function inputDateTimeToIso(value) {
  if (!value) return null;
  const d = new Date(value);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

function appendOption(sel, value, label, selected = false) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  if (selected) opt.selected = true;
  sel.appendChild(opt);
}

function buildStatusBody(task) {
  const root = document.createElement('div');
  root.appendChild(cloneTemplate('task-modal-status'));
  root.querySelector('.tm-status-title').textContent = task.title || '';
  const desc = root.querySelector('.tm-status-desc');
  if (task.description) desc.textContent = task.description;
  else desc.remove();
  // Подсветить текущий статус
  const sel = root.querySelector('select[name="status"]');
  sel.value = task.status || 'pending';
  return root; // DOM-узел: иначе .value/.selected теряются при сериализации
}

function buildFullBody(task, users, assets) {
  const root = document.createElement('div');
  root.appendChild(cloneTemplate('task-modal-full'));

  root.querySelector('input[name="title"]').value          = task.title || '';
  root.querySelector('textarea[name="description"]').value = task.description || '';
  root.querySelector('input[name="start_date"]').value     = isoToInputDateTime(task.start_date);
  root.querySelector('input[name="due_date"]').value       = isoToInputDateTime(task.due_date);

  root.querySelector('select[name="priority"]').value = task.priority || 'medium';
  root.querySelector('select[name="status"]').value   = task.status   || 'pending';

  const assigneeSel = root.querySelector('select[name="assigned_to"]');
  for (const u of users) {
    appendOption(assigneeSel, u.id, `${u.full_name} (${u.username})`, task.assigned_to === u.id);
  }

  const assetSel = root.querySelector('select[name="related_asset_id"]');
  for (const a of assets) {
    appendOption(assetSel, a.id, `${a.name} (${a.inventory_number})`, task.related_asset_id === a.id);
  }

  return root; // DOM-узел: иначе .value/.selected теряются при сериализации
}

export async function openTaskModal({ mode = 'add', id = null, onSaved = null } = {}) {
  let task = {};
  let users = [];
  let assetsList = [];

  try {
    const promises = [];
    if (id) promises.push(api.get(`/tasks/${id}`).then(r => task = r).catch(() => task = {}));
    if (mode !== 'status') {
      promises.push(api.get('/users?active_only=true').then(r => users = r || []).catch(() => users = []));
      promises.push(api.get('/assets').then(r => assetsList = r || []).catch(() => assetsList = []));
    }
    await Promise.all(promises);
  } catch {}

  if (id && !task.id) {
    toast.error('Не удалось загрузить задачу');
    return;
  }

  const body = mode === 'status'
    ? buildStatusBody(task)
    : buildFullBody(task, users, assetsList);

  const titles = {
    add:    'Новая задача',
    edit:   'Редактировать задачу',
    status: 'Сменить статус',
  };
  const submitTexts = { add: 'Создать', edit: 'Сохранить', status: 'Сохранить' };

  openModal({
    title:      titles[mode] || 'Задача',
    body,
    size:       'md',
    submitText: submitTexts[mode] || 'Сохранить',
    onSubmit: async (data, ctl) => {
      try {
        if (mode === 'status') {
          await api.put(`/tasks/${id}`, { status: data.status });
        } else {
          const errors = validateRequired(data, ['title', 'start_date']);
          if (Object.keys(errors).length) {
            applyValidationErrors(ctl, errors);
            ctl.setError('Проверьте корректность полей');
            return;
          }

          const payload = {
            title:       data.title.trim(),
            description: data.description?.trim() || null,
            priority:    data.priority || 'medium',
            status:      data.status   || 'pending',
            task_type:   data.assigned_to ? 'user' : 'admin',
            start_date:  inputDateTimeToIso(data.start_date),
            due_date:    data.due_date ? inputDateTimeToIso(data.due_date) : null,
            assigned_to: data.assigned_to || null,
            related_asset_id: data.related_asset_id || null,
          };
          if (mode === 'add') {
            // При создании пустые поля просто не отправляем (exclude_none на бэке).
            Object.keys(payload).forEach(k => { if (payload[k] === null) delete payload[k]; });
            await api.post('/tasks', payload);
          } else {
            // При редактировании null оставляем — это осознанная очистка поля.
            await api.put(`/tasks/${id}`, payload);
          }
        }

        ctl.close();
        if (onSaved) onSaved();
      } catch (err) {
        ctl.setError(err.message || 'Ошибка сохранения');
      }
    },
  });
}
