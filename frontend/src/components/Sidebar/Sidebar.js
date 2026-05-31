
import Alpine from 'alpinejs';
import tpl from './Sidebar.html?raw';

import { Icons } from '../icons.js';
import { state } from '../../state.js';

Alpine.data('appSidebar', () => ({
  Icons,
  currentHash: window.location.hash || '#/dashboard',

  items: [],

  expanded: { '/calendar': true },

  buildMenu() {
    return [
      { route: '/dashboard', label: 'Главная',    iconHtml: Icons.home(),     visible: true },
      { route: '/assets',    label: 'Активы',     iconHtml: Icons.box(),      visible: state.canSee('assets') },
      { route: '/users',     label: 'Сотрудники', iconHtml: Icons.users(),    visible: state.isAdmin },
      {
        route: '/calendar',  label: 'Календарь',  iconHtml: Icons.calendar(), visible: true,
        children: [
          { route: '/tasks',      label: 'Задачи',    iconHtml: Icons.checkCircle(), visible: state.canSee('tasks') },
          { route: '/notes',      label: 'Заметки',   iconHtml: Icons.pencil(),      visible: state.canSee('notes') },
          { route: '/categories', label: 'Категории', iconHtml: Icons.tag(),         visible: state.canSee('categories') },
        ].filter(c => c.visible),
      },
      { route: '/export',    label: 'Отчёты',     iconHtml: Icons.file(),     visible: state.isAdmin },
      { route: '/audit',     label: 'Аудит-лог',  iconHtml: Icons.clock(),    visible: state.isAdmin },
    ].filter(it => it.visible);
  },

  hasChildren(item) {
    return Array.isArray(item.children) && item.children.length > 0;
  },
  isExpanded(route) {
    return this.expanded[route] !== false;
  },
  toggle(route) {
    this.expanded[route] = !this.isExpanded(route);
  },

  isActive(route) {
    const h = this.currentHash || '#/dashboard';
    return h === `#${route}` || h.startsWith(`#${route}/`);
  },

  init() {
    this.items = this.buildMenu();
    this._onHashChange = () => {
      this.currentHash = window.location.hash;
      Alpine.store('ui').closeSidebar();
    };
    window.addEventListener('hashchange', this._onHashChange);
  },
  destroy() {
    window.removeEventListener('hashchange', this._onHashChange);
  },
}));

export function renderSidebar() {
  return tpl;
}
