
import Alpine from 'alpinejs';
import tpl from './users.html?raw';

import { api, users as usersApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { openUserModal, openUserCredentialsModal } from '../user-modal/user-modal.js';

const PAGE_SIZE = 25;

function fmtDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  });
}

function avatarStyle(name) {
  let h = 0;
  const s = String(name || '');
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `background: linear-gradient(135deg, hsl(${hue}, 55%, 60%), hsl(${(hue + 30) % 360}, 60%, 45%));`;
}

function initial(name) {
  return (String(name || '?').charAt(0) || '?').toUpperCase();
}

Alpine.data('usersPage', () => ({
  users: [],
  total: 0,

  page: 1,
  pageSize: PAGE_SIZE,

  sortBy: 'full_name',
  sortOrder: 'asc',

  search: '',
  roleFilter: '',
  statusFilter: '',

  expanded: {},
  loading: false,

  get pages() {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  },
  get visibleUsers() {
    const q = this.search.trim().toLowerCase();
    const r = this.roleFilter;
    const st = this.statusFilter;
    return this.users.filter(u => {
      if (r && u.role !== r) return false;
      if (st === 'active' && !u.is_active) return false;
      if (st === 'inactive' && u.is_active) return false;
      if (q) {
        const blob = [u.username, u.full_name, u.email].filter(Boolean).join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  },
  get activeCount() { return this.users.filter(u => u.is_active).length; },
  get adminCount()  { return this.users.filter(u => u.role === 'admin').length; },

  async init() {
    await this.load();
  },

  async load() {
    this.loading = true;
    const _minLoad = new Promise(r => setTimeout(r, 400));
    try {
      const skip = (this.page - 1) * this.pageSize;
      const url = `/users?skip=${skip}&limit=${this.pageSize}`
        + `&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
      const { items, total } = await api.getPaginated(url);
      this.users = items;
      this.total = total;
    } catch (e) {
      console.error('Ошибка загрузки пользователей:', e);
      this.users = [];
      this.total = 0;
    } finally {
      await _minLoad;
      this.loading = false;
    }
  },

  setSort(field) {
    if (this.sortBy === field) {
      this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = field;
      this.sortOrder = 'asc';
    }
    this.page = 1;
    this.load();
  },
  sortArrow(field) {
    if (this.sortBy !== field) return '↕';
    return this.sortOrder === 'asc' ? '↑' : '↓';
  },

  prevPage() {
    if (this.page <= 1) return;
    this.page -= 1;
    this.load();
  },
  nextPage() {
    if (this.page >= this.pages) return;
    this.page += 1;
    this.load();
  },

  toggleDetails(id) {
    this.expanded[id] = !this.expanded[id];
  },

  roleLabel(role) { return role === 'admin' ? 'Администратор' : 'Пользователь'; },
  roleBadgeClass(role) { return role === 'admin' ? 'badge-warning' : 'badge-info'; },

  openCreate() {
    openUserModal({ mode: 'add', onSaved: () => this.load() });
  },
  openEdit(user) {
    openUserModal({ mode: 'edit', id: user.id, onSaved: () => this.load() });
  },
  isSelf(user) {
    return String(user.id) === String(state.user.id);
  },
  async resetPassword(user) {
    if (!user.email) {
      toast.error('У пользователя не указан email — отправить новый пароль некуда');
      return;
    }
    const ok = confirm(
      `Сменить пароль для «${user.full_name || user.username}»?\n\n`
      + `Будет сгенерирован новый временный пароль и отправлен на ${user.email}. `
      + `При следующем входе пользователь должен будет задать собственный пароль.`
    );
    if (!ok) return;
    try {
      const res = await usersApi.resetPassword(user.id);
      if (res.email_sent) toast.success('Письмо с новым паролем отправлено');
      else toast.info('Письмо не доставлено — передайте данные вручную');
      openUserCredentialsModal({
        username:  res.credentials.username,
        password:  res.credentials.password,
        emailSent: res.email_sent,
        title:     'Пароль сброшен',
      });
      await this.load();
    } catch (e) {
      toast.error('Ошибка: ' + e.message);
    }
  },
  async toggleStatus(user) {
    const newStatus = !user.is_active;
    if (!confirm(`${newStatus ? 'Активировать' : 'Деактивировать'} этого пользователя?`)) return;
    try {
      await usersApi.update(user.id, { is_active: newStatus });
      await this.load();
      toast.success(newStatus ? 'Пользователь активирован' : 'Пользователь деактивирован');
    } catch (e) {
      toast.error(`Ошибка: ${e.message}`);
    }
  },

  fmtDateTime,
  avatarStyle,
  initial,
}));

export async function renderUsersPage() {
  return tpl;
}

export function initUsersEvents() {}
