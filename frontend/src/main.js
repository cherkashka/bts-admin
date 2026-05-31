import Alpine from 'alpinejs';

import { state } from './state.js';
import { renderHeader } from './components/Header/Header.js';
import { renderSidebar } from './components/Sidebar/Sidebar.js';
import { closeModal } from './components/Modal/Modal.js';
import appLayoutTpl from './components/app-layout.html?raw';

import { renderAuthPage, initAuthEvents } from './pages/auth/auth.js';
import { renderFirstLoginPage, initFirstLoginEvents } from './pages/first-login/first-login.js';
import { renderAssetsPage, initAssetsEvents } from './pages/assets/assets.js';
import { renderTasksPage, initTasksEvents } from './pages/tasks/tasks.js';
import { renderUsersPage, initUsersEvents } from './pages/users/users.js';
import { renderNotesPage, initNotesEvents } from './pages/notes/notes.js';
import { renderCalendarPage, initCalendarEvents } from './pages/calendar/calendar.js';
import { renderExportPage, initExportEvents } from './pages/export/export.js';
import { renderCategoriesPage, initCategoriesEvents } from './pages/categories/categories.js';
import { renderDashboardPage, initDashboardEvents } from './pages/dashboard/dashboard.js';
import { renderAuditPage, initAuditEvents } from './pages/audit/audit.js';

window.Alpine = Alpine;

Alpine.store('ui', {
  sidebarOpen: false,
  toggleSidebar() { this.sidebarOpen = !this.sidebarOpen; },
  closeSidebar() { this.sidebarOpen = false; },
});

Alpine.start();

import { openAssetModal } from './pages/asset-modal/asset-modal.js';
import { openUserModal } from './pages/user-modal/user-modal.js';
import { openNoteModal } from './pages/note-modal/note-modal.js';
import { openTaskModal } from './pages/task-modal/task-modal.js';

const MODAL_ROUTES = {
  '/assets/add':  { parent: '/assets',   open: () => openAssetModal({ mode: 'add' }) },
  '/users/add':   { parent: '/users',    open: () => openUserModal({ mode: 'add' }) },
  '/notes/add':   { parent: '/calendar', open: (params) => openNoteModal({ presetDate: params.presetDate || null }) },
  '/tasks/add':   { parent: '/tasks',    open: () => openTaskModal({ mode: 'add' }) },
};

const ROUTE_GUARDS = {
  '/assets':     { type: 'permission', resource: 'assets',     action: 'read' },
  '/tasks':      { type: 'permission', resource: 'tasks',      action: 'read' },
  '/notes':      { type: 'permission', resource: 'notes',      action: 'read' },
  '/users':      { type: 'admin' },
  '/categories': { type: 'permission', resource: 'categories', action: 'read' },
  '/export':     { type: 'admin' },
  '/audit':      { type: 'admin' },
};

function canAccess(route) {
  const g = ROUTE_GUARDS[route];
  if (!g) return true;
  if (g.type === 'admin')      return state.isAdmin;
  if (g.type === 'permission') return state.can(g.resource, g.action);
  return true;
}

class Router {
  constructor() {
    this.routes = {
      '/login':        () => this.loadPage('auth'),
      '/first-login':  () => this.loadPage('first-login'),
      '/dashboard':    () => this.loadPage('dashboard'),
      '/assets':       () => this.loadPage('assets'),
      '/tasks':        () => this.loadPage('tasks'),
      '/users':        () => this.loadPage('users'),
      '/notes':        () => this.loadPage('notes'),
      '/calendar':     () => this.loadPage('calendar'),
      '/categories':   () => this.loadPage('categories'),
      '/export':       () => this.loadPage('export'),
      '/audit':        () => this.loadPage('audit'),
    };

    this.currentPage = null;
    this.isLoggedIn = false;
    this.passwordChangeRequired = false;
    this.init();
  }

  async refreshState() {
    try {
      await state.load();
      this.isLoggedIn = true;
      this.passwordChangeRequired = state.user.passwordChangeRequired;

      if (state.user.theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
      } else if (state.user.theme === 'light') {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
      }
    } catch {
      state.clear();
      this.isLoggedIn = false;
      this.passwordChangeRequired = false;
    }
  }

  async init() {
    await this.refreshState();

    window.addEventListener('hashchange', () => this.handleRoute());

    if (!window.location.hash || window.location.hash === '#') {
      if (!this.isLoggedIn) {
        window.location.hash = '/login';
      } else if (this.passwordChangeRequired) {
        window.location.hash = '/first-login';
      } else {
        window.location.hash = '/dashboard';
      }
    }

    this.handleRoute();
  }

  async handleRoute() {
    closeModal();

    const hash = window.location.hash.substring(1);

    if (!hash) {
      window.location.hash = this.isLoggedIn ? '/dashboard' : '/login';
      return;
    }

    const parts = hash.split('/').filter(Boolean);
    const lvl1 = '/' + (parts[0] || '');
    const lvl2 = parts[1] ? `${lvl1}/${parts[1]}` : lvl1;
    const id = parts[2];

    if (parts[1] === 'edit' && id) {
      if (parts[0] === 'assets') {
        if (!state.can('assets', 'update')) { window.location.hash = '/dashboard'; return; }
        await this.loadPage('assets');
        await openAssetModal({ mode: 'edit', id });
        return;
      }
      if (parts[0] === 'users') {
        if (!state.isAdmin) { window.location.hash = '/dashboard'; return; }
        await this.loadPage('users');
        await openUserModal({ mode: 'edit', id });
        return;
      }
      if (parts[0] === 'notes') {
        await this.loadPage('notes');
        await openNoteModal({ id });
        return;
      }
      if (parts[0] === 'tasks') {
        if (!state.can('tasks', 'update') && !state.isAdmin) {
          window.location.hash = '/dashboard'; return;
        }
        await this.loadPage('tasks');
        await openTaskModal({ mode: 'edit', id });
        return;
      }
    }

    if (MODAL_ROUTES[lvl2]) {
      const cfg = MODAL_ROUTES[lvl2];

      const allowed =
        (lvl2 === '/assets/add' && state.can('assets', 'create')) ||
        (lvl2 === '/users/add'  && state.isAdmin) ||
        (lvl2 === '/notes/add'  && state.can('notes', 'create')) ||
        (lvl2 === '/tasks/add'  && (state.isAdmin || state.can('tasks', 'create')));
      if (!allowed) { window.location.hash = '/dashboard'; return; }
      const presetDate = new URLSearchParams(window.location.search).get('date');
      await this.loadPage(cfg.parent.slice(1));
      await cfg.open({ presetDate });
      return;
    }

    if (this.routes[lvl1]) {
      if (!canAccess(lvl1)) { window.location.hash = '/dashboard'; return; }
      this.routes[lvl1]();
    } else if (this.routes[lvl2]) {
      this.routes[lvl2]();
    } else {
      window.location.hash = this.isLoggedIn ? '/dashboard' : '/login';
    }
  }

  async loadPage(pageName, params = {}) {
    const publicPages = new Set(['auth', 'first-login']);

    if (!publicPages.has(pageName) && !this.isLoggedIn) {
      await this.refreshState();
      if (!this.isLoggedIn) {
        window.location.hash = '/login';
        return;
      }
    }

    if (this.isLoggedIn && this.passwordChangeRequired && pageName !== 'first-login') {
      window.location.hash = '/first-login';
      return;
    }

    const appElement = document.getElementById('app');
    if (!appElement) return;

    const isFullPage = pageName === 'auth' || pageName === 'first-login';

    if (isFullPage) {
      appElement.innerHTML = '';
      if (pageName === 'auth') {
        appElement.innerHTML = await renderAuthPage(params);
        if (typeof initAuthEvents === 'function') initAuthEvents(this);
      } else if (pageName === 'first-login') {
        appElement.innerHTML = await renderFirstLoginPage(params);
        if (typeof initFirstLoginEvents === 'function') initFirstLoginEvents(this);
      }
      this.currentPage = pageName;
      return;
    }

    if (this.currentPage === pageName) return;

    appElement.innerHTML = appLayoutTpl;
    appElement.querySelector('.app-shell-sidebar').innerHTML = renderSidebar();
    appElement.querySelector('.app-shell-header').innerHTML  = renderHeader();

    const contentContainer = document.getElementById('main-content');
    if (!contentContainer) return;

    let html = '';
    if (pageName === 'dashboard')       html = await renderDashboardPage(params);
    else if (pageName === 'assets')     html = await renderAssetsPage(params);
    else if (pageName === 'tasks')      html = await renderTasksPage(params);
    else if (pageName === 'users')      html = await renderUsersPage(params);
    else if (pageName === 'notes')      html = await renderNotesPage(params);
    else if (pageName === 'calendar')   html = await renderCalendarPage(params);
    else if (pageName === 'categories') html = await renderCategoriesPage(params);
    else if (pageName === 'export')     html = await renderExportPage(params);
    else if (pageName === 'audit')      html = await renderAuditPage(params);
    contentContainer.innerHTML = html;

    if (pageName === 'dashboard'  && typeof initDashboardEvents  === 'function') initDashboardEvents();
    if (pageName === 'assets'     && typeof initAssetsEvents     === 'function') initAssetsEvents();
    if (pageName === 'tasks'      && typeof initTasksEvents      === 'function') initTasksEvents();
    if (pageName === 'users'      && typeof initUsersEvents      === 'function') initUsersEvents();
    if (pageName === 'notes'      && typeof initNotesEvents      === 'function') initNotesEvents();
    if (pageName === 'calendar'   && typeof initCalendarEvents   === 'function') initCalendarEvents();
    if (pageName === 'categories' && typeof initCategoriesEvents === 'function') initCategoriesEvents();
    if (pageName === 'export'     && typeof initExportEvents     === 'function') initExportEvents();
    if (pageName === 'audit'      && typeof initAuditEvents      === 'function') initAuditEvents();

    this.currentPage = pageName;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { window.appRouter = new Router(); });
} else {
  window.appRouter = new Router();
}

export default window.appRouter;
