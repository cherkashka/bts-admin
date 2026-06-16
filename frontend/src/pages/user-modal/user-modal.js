
import { api } from '../../api/client.js';
import { openModal, validateRequired, applyValidationErrors } from '../../components/Modal/Modal.js';
import { toast } from '../../components/Toast/Toast.js';
import { Icons } from '../../components/icons.js';
import tplHtml from './user-modal.html?raw';

const RESOURCES = ['assets', 'tasks', 'notes', 'categories'];
const ACTIONS   = ['read', 'create', 'update', 'delete'];
const RES_LABEL = { assets: 'Активы', tasks: 'Задачи', notes: 'Заметки', categories: 'Категории' };
const ACT_LABEL = { create: 'Создание', read: 'Просмотр', update: 'Изменение', delete: 'Удаление' };

let _templatesHost = null;
function ensureTemplates() {
  if (_templatesHost) return _templatesHost;
  _templatesHost = document.createElement('div');
  _templatesHost.innerHTML = tplHtml;
  return _templatesHost;
}

function cloneTemplate(id) {
  const host = ensureTemplates();
  const tpl = host.querySelector(`#${id}`);
  if (!tpl) throw new Error(`Template #${id} not found`);
  return tpl.content.cloneNode(true);
}

function fillPermMatrix(rootEl, permissions = {}) {
  const headRow = rootEl.querySelector('.um-perm-head-row');
  const body    = rootEl.querySelector('.um-perm-body');

  const corner = document.createElement('th');
  headRow.appendChild(corner);
  for (const a of ACTIONS) {
    const th = document.createElement('th');
    th.className = 'um-perm-th';
    th.textContent = ACT_LABEL[a];
    headRow.appendChild(th);
  }

  for (const res of RESOURCES) {
    const tr = document.createElement('tr');
    const resTd = document.createElement('td');
    resTd.className = 'um-perm-td-res';
    resTd.textContent = RES_LABEL[res];
    tr.appendChild(resTd);

    for (const act of ACTIONS) {
      const td = document.createElement('td');
      td.className = 'um-perm-td';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.name = `perm_${res}_${act}`;
      cb.className = 'um-perm-cb';
      cb.checked = !!permissions[res]?.[act];
      td.appendChild(cb);
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }

  for (const res of RESOURCES) {
    const read = rootEl.querySelector(`[name="perm_${res}_read"]`);
    if (!read) continue;
    const others = ['create', 'update', 'delete']
      .map(a => rootEl.querySelector(`[name="perm_${res}_${a}"]`))
      .filter(Boolean);
    if (others.some(c => c.checked)) read.checked = true;
    read.addEventListener('change', () => {
      if (!read.checked) others.forEach(c => { c.checked = false; });
    });
    for (const c of others) {
      c.addEventListener('change', () => { if (c.checked) read.checked = true; });
    }
  }
}

function collectPermissions(formEl) {
  const perms = {};
  for (const res of RESOURCES) {
    perms[res] = {};
    for (const act of ACTIONS) {
      perms[res][act] = formEl.querySelector(`[name="perm_${res}_${act}"]`)?.checked ?? false;
    }
  }
  return perms;
}

function buildAddBody() {
  const root = document.createElement('div');
  root.appendChild(cloneTemplate('user-modal-add'));
  fillPermMatrix(root, {});
  return root;
}

function buildEditBody(user) {
  const root = document.createElement('div');
  root.appendChild(cloneTemplate('user-modal-edit'));
  root.querySelector('input[name="full_name"]').value = user.full_name || '';
  root.querySelector('input[name="email"]').value     = user.email || '';
  root.querySelector('input[name="phone"]').value     = user.phone || '';
  const sel = root.querySelector('select[name="is_active"]');
  sel.value = user.is_active === false ? 'false' : 'true';
  fillPermMatrix(root, user.permissions || {});
  return root;
}

function buildSuccessBody({ username, password, emailSent }) {
  const root = document.createElement('div');
  root.appendChild(cloneTemplate('user-modal-success'));

  const iconEl = root.querySelector('.um-success-icon');
  if (iconEl) iconEl.innerHTML = Icons.checkCircle(40);

  const note = root.querySelector('.um-success-note');
  note.textContent = emailSent
    ? 'Письмо с реквизитами отправлено на email.'
    : 'Email не доставлен — передайте реквизиты вручную.';
  note.classList.add(emailSent ? 'um-success-note-ok' : 'um-success-note-warn');

  root.querySelector('.um-creds-username').textContent = username;
  root.querySelector('.um-creds-password').textContent = password;

  return root;
}

export function openUserCredentialsModal({ username, password, emailSent, title = 'Данные для входа' } = {}) {
  const ctl = openModal({
    title,
    body: buildSuccessBody({ username, password, emailSent }),
    size: 'md',
    submitText: 'Готово',
    onSubmit: async (_data, c) => { c.close(); },
  });

  const copyBtn = ctl.bodyEl.querySelector('.um-copy-btn');
  copyBtn?.addEventListener('click', () => {
    navigator.clipboard.writeText(`Логин: ${username}\nПароль: ${password}`).catch(() => {});
    copyBtn.textContent = 'Скопировано';
  });
  return ctl;
}

export async function openUserModal({ mode = 'add', id = null, onSaved = null } = {}) {
  let user = {};
  if (mode === 'edit' && id) {
    try { user = await api.get(`/users/${id}`); }
    catch (err) { toast.error('Ошибка загрузки: ' + err.message); return; }
  }

  const body = mode === 'add' ? buildAddBody() : buildEditBody(user);

  openModal({
    title: mode === 'edit' ? 'Редактировать сотрудника' : 'Создать сотрудника',
    body,
    size: 'md',
    submitText: mode === 'edit' ? 'Сохранить' : 'Создать и отправить инвайт',
    onCancel: () => {
      if (onSaved) return;
      if (window.location.hash !== '#/users') window.location.hash = '/users';
    },
    onSubmit: async (data, ctl) => {
      if (mode === 'add') {
        const errors = validateRequired(data, ['full_name', 'email']);
        if (data.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
          errors.email = 'Неверный формат email';
        }
        if (Object.keys(errors).length > 0) {
          applyValidationErrors(ctl, errors);
          ctl.setError('Проверьте корректность полей');
          return;
        }

        const payload = {
          full_name:   data.full_name.trim(),
          email:       data.email.trim(),
          phone:       data.phone?.trim() || null,
          permissions: collectPermissions(ctl.form),
        };

        const result = await api.post('/users', payload);
        const { credentials, email_sent } = result;

        ctl.setBody(buildSuccessBody({
          username:  credentials.username,
          password:  credentials.password,
          emailSent: email_sent,
        }));
        ctl.hideSubmit();

        const copyBtn = ctl.bodyEl.querySelector('.um-copy-btn');
        copyBtn?.addEventListener('click', () => {
          const text = `Логин: ${credentials.username}\nПароль: ${credentials.password}`;
          navigator.clipboard.writeText(text).catch(() => {});
          copyBtn.textContent = 'Скопировано';
        });

        if (onSaved) onSaved();
        return;
      }

      const errors = validateRequired(data, ['full_name']);
      if (Object.keys(errors).length > 0) {
        applyValidationErrors(ctl, errors);
        ctl.setError('Проверьте корректность полей');
        return;
      }

      const payload = {
        full_name:   data.full_name?.trim(),
        permissions: collectPermissions(ctl.form),

        email:       data.email?.trim() || null,
        phone:       data.phone?.trim() || null,
      };
      if (data.is_active !== undefined) payload.is_active = data.is_active === 'true';

      await api.put(`/users/${id}`, payload);
      ctl.close();
      if (onSaved) onSaved();
      else if (window.location.hash !== '#/users') window.location.hash = '/users';
    },
  });
}
