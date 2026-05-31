/**
 * Хедер приложения — Alpine.js компонент.
 * Шаблон в Header.html. В коде HTML нет.
 */
import Alpine from 'alpinejs';
import tpl from './Header.html?raw';

import { Icons } from '../icons.js';
import { state } from '../../state.js';
import { api } from '../../api/client.js';

const DISMISSED_KEY = 'notif:dismissed';

function loadDismissed() {
  try { return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')); }
  catch { return new Set(); }
}
function saveDismissed(set) {
  try { localStorage.setItem(DISMISSED_KEY, JSON.stringify([...set])); } catch {}
}

const ACTION_LABEL = { create: 'создал', update: 'изменил', delete: 'удалил' };
const ENTITY_LABEL = {
  asset: 'актив', user: 'сотрудника', task: 'задачу',
  note: 'заметку', category: 'категорию',
};

function buildNotifications(entries) {
  return entries.map(e => ({
    id:    e.id,
    title: `${e.actor_name || 'Система'} ${ACTION_LABEL[e.action] || e.action} ${ENTITY_LABEL[e.entity_type] || e.entity_type}`,
    sub:   [e.entity_label, new Date(e.timestamp).toLocaleString('ru-RU')]
             .filter(Boolean).join(' • '),
    link:  '#/audit',
  }));
}

const ROUTE_LABELS = {
  '/dashboard':  'Главная',
  '/assets':     'Активы',
  '/tasks':      'Задачи',
  '/users':      'Сотрудники',
  '/notes':      'Заметки',
  '/calendar':   'Календарь',
  '/categories': 'Категории',
  '/export':     'Отчёты',
  '/audit':      'Аудит-лог',
};

function currentPageLabel() {
  const hash = window.location.hash.replace(/^#/, '') || '/dashboard';
  const parts = hash.split('/').filter(Boolean);
  const root = '/' + (parts[0] || 'dashboard');
  return ROUTE_LABELS[root] || 'Главная';
}

Alpine.data('appHeader', () => ({
  Icons,

  pageLabel: 'Главная',
  isDark: document.documentElement.getAttribute('data-theme') === 'dark',

  notifOpen: false,
  notifLoading: false,
  notifications: [],
  dismissed: loadDismissed(),

  get visibleNotifications() {
    return this.notifications.filter(n => !this.dismissed.has(n.id));
  },

  get initial() {
    const src = state.user.fullName || state.user.username || '?';
    return src.trim().charAt(0).toUpperCase();
  },
  get userTitle() {
    return state.user.fullName || state.user.username || 'Выйти';
  },

  init() {
    this.pageLabel = currentPageLabel();
    this._onHashChange = () => { this.pageLabel = currentPageLabel(); };
    window.addEventListener('hashchange', this._onHashChange);
    // Тихо подгружаем уведомления на старте — чтобы индикатор-точка
    // появилась без открытия панели.
    this.loadNotifications();
  },

  async loadNotifications() {
    // Уведомления = последние действия из аудит-лога. Доступ к /audit
    // только у админа, поэтому не-админам просто оставляем пустой список.
    if (state.user.role !== 'admin') { this.notifications = []; return; }
    this.notifLoading = true;
    try {
      const data = await api.get('/audit?limit=10');
      const items = Array.isArray(data) ? data : (data.items || []);
      this.notifications = buildNotifications(items);
    } catch {
      this.notifications = [];
    } finally {
      this.notifLoading = false;
    }
  },

  toggleNotifications() {
    this.notifOpen = !this.notifOpen;
    if (this.notifOpen) this.loadNotifications();
  },

  dismiss(id) {
    this.dismissed.add(id);
    saveDismissed(this.dismissed);
  },

  dismissAll() {
    for (const n of this.notifications) this.dismissed.add(n.id);
    saveDismissed(this.dismissed);
    this.notifOpen = false;
  },
  destroy() {
    window.removeEventListener('hashchange', this._onHashChange);
  },

  async toggleTheme() {
    this.isDark = !this.isDark;
    const theme = this.isDark ? 'dark' : 'light';

    if (this.isDark) document.documentElement.setAttribute('data-theme', 'dark');
    else             document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('theme', theme);

    // Сохраняем тему на сервере — чтобы следовала за пользователем
    // между устройствами. Ошибки молча игнорируем (тема локально применена).
    try { await api.patch('/auth/me', { theme }); } catch {}
  },

  async logout() {
    try { await api.post('/auth/logout', {}); } catch {}
    state.clear();
    localStorage.removeItem('isLoggedIn');
    if (window.appRouter) {
      window.appRouter.isLoggedIn = false;
      window.appRouter.passwordChangeRequired = false;
      window.appRouter.currentPage = null;
    }
    window.location.hash = '/login';
  },
}));

export function renderHeader() {
  return tpl;
}
