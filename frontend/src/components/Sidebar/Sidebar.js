/**
 * Боковая навигация — Alpine.js компонент.
 * Шаблон в Sidebar.html. В коде HTML нет.
 *
 * Структура меню: верхний уровень — Главная, Активы, Сотрудники, Календарь,
 * Отчёты, Аудит-лог. «Календарь» — раскрывающийся раздел: внутри Задачи,
 * Заметки, Категории (по умолчанию раскрыт, сворачивается стрелкой).
 */
import Alpine from 'alpinejs';
import tpl from './Sidebar.html?raw';

import { Icons } from '../icons.js';
import { state } from '../../state.js';

Alpine.data('appSidebar', () => ({
  Icons,
  currentHash: window.location.hash || '#/dashboard',

  // Меню строится один раз в init() — права за сессию не меняются.
  // Геттер пересоздавал бы массив на каждый ре-рендер, ломая вложенный x-for.
  items: [],

  // Раскрытые разделы. Подпункты «Календаря» открыты по умолчанию.
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
      Alpine.store('ui').closeSidebar(); // навигация закрывает мобильное меню
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
