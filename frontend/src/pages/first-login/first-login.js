
import Alpine from 'alpinejs';
import tpl from './first-login.html?raw';

import { api } from '../../api/client.js';

const STRENGTH_COLORS = ['#fc8181', '#f6ad55', '#f6e05e', '#68d391', '#48bb78'];

Alpine.data('firstLoginPage', () => ({

  user: {},

  phone: '',
  password: '',
  passwordConfirm: '',

  showPwd: false,
  showPwdConfirm: false,
  message: { text: '', isError: false },

  resources: [
    { key: 'assets',     label: 'Активы' },
    { key: 'tasks',      label: 'Задачи' },
    { key: 'notes',      label: 'Заметки' },
    { key: 'categories', label: 'Категории' },
  ],
  actions: [
    { key: 'read',   label: 'Просмотр' },
    { key: 'create', label: 'Создание' },
    { key: 'update', label: 'Изменение' },
    { key: 'delete', label: 'Удаление' },
  ],

  async init() {
    try {
      const r = await api.authCheck();
      this.user = r.user || {};
      this.phone = this.user.phone || '';
    } catch {}
  },

  hasPerm(resource, action) {
    return !!this.user.permissions?.[resource]?.[action];
  },

  get strength() {
    const v = this.password;
    let score = 0;
    if (v.length >= 8)  score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/\d/.test(v))   score++;
    if (/[^a-zA-Z0-9]/.test(v)) score++;
    return {
      pct:   (score / 5) * 100,
      color: STRENGTH_COLORS[score - 1] || '#e2e8f0',
    };
  },

  show(text, isError = false) {
    this.message = { text, isError };
    if (!isError) setTimeout(() => { this.message = { text: '', isError: false }; }, 4000);
  },

  async submit() {
    if (this.password !== this.passwordConfirm) {
      this.show('Пароли не совпадают', true);
      return;
    }
    try {
      await api.patch('/auth/me', {
        phone: this.phone || null,
        password: this.password,
        password_confirm: this.passwordConfirm,
      });
      if (window.appRouter?.refreshState) await window.appRouter.refreshState();
      this.show('Аккаунт активирован! Переходим…', false);
      setTimeout(() => { window.location.hash = '/dashboard'; }, 1000);
    } catch (err) {
      this.show(err.message, true);
    }
  },
}));

export async function renderFirstLoginPage() {
  return tpl;
}

export function initFirstLoginEvents(router) {
  if (router) window.appRouter = router;
}
