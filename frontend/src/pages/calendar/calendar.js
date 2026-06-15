
import Alpine from 'alpinejs';
import tpl from './calendar.html?raw';

import { api, categories as categoriesApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { Icons } from '../../components/icons.js';
import { openNoteModal } from '../note-modal/note-modal.js';

const ONLY_MINE_KEY = 'calendar.only_mine';

const SYSTEM_EVENT_TYPES = {
  task:     { label: 'Задачи',   color: '#6b7280' },
  warranty: { label: 'Гарантии', color: '#8b5cf6' },
};
const NOTE_DEFAULT_COLOR = '#3b82f6';

const MONTH_NAMES = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

function pad2(n) { return String(n).padStart(2, '0'); }

function eventDotColor(ev, categoriesById) {
  if (ev.type === 'note') {
    if (ev.color) return ev.color;
    if (ev.category_id && categoriesById[ev.category_id]) return categoriesById[ev.category_id].color;
    return NOTE_DEFAULT_COLOR;
  }
  if (ev.type === 'task_due' || ev.type === 'task_start') return SYSTEM_EVENT_TYPES.task.color;
  if (ev.type === 'warranty_end' || ev.type === 'commission') return SYSTEM_EVENT_TYPES.warranty.color;
  return '#999';
}

function eventTypeLabel(ev) {
  if (ev.type === 'task_due' || ev.type === 'task_start') return SYSTEM_EVENT_TYPES.task.label;
  if (ev.type === 'warranty_end' || ev.type === 'commission') return SYSTEM_EVENT_TYPES.warranty.label;
  if (ev.type === 'note') return 'Запись';
  return ev.type;
}

Alpine.data('calendarPage', () => ({
  Icons,

  allEvents: [],
  categoriesById: {},

  currentDate: new Date(),
  realToday: new Date(),

  onlyMine: localStorage.getItem(ONLY_MINE_KEY) === '1',
  monthDropdownOpen: false,
  monthNames: MONTH_NAMES,
  loading: true,
  mobileFiltersOpen: false,
  selectedDate: null,   // выбранный день (YYYY-MM-DD) для просмотра событий в панели

  filters: {},

  async init() {
    await this.loadCategories();
    this.initFilters();
    await this.loadMonth();

    this._docClick = () => { this.monthDropdownOpen = false; };
    this._docEsc   = (e) => { if (e.key === 'Escape') this.monthDropdownOpen = false; };
    document.addEventListener('click', this._docClick);
    document.addEventListener('keydown', this._docEsc);
  },

  destroy() {
    document.removeEventListener('click', this._docClick);
    document.removeEventListener('keydown', this._docEsc);
  },

  async loadCategories() {
    try {
      const cats = await categoriesApi.getAll(true);
      const map = {};
      for (const c of cats) {
        map[c.id] = {
          id: c.id,
          color: c.color,
          label: c.name,
          is_default: c.is_default,
        };
      }
      this.categoriesById = map;
    } catch (e) {
      console.error('Ошибка загрузки категорий:', e);
    }
  },

  initFilters() {
    const f = {};
    for (const k of Object.keys(SYSTEM_EVENT_TYPES)) f[k] = true;
    for (const id of Object.keys(this.categoriesById)) f[`category-${id}`] = true;
    this.filters = f;
  },

  async loadMonth() {
    this.loading = true;
    this.selectedDate = null;   // при смене месяца сбрасываем выбранный день
    const _minLoad = new Promise(r => setTimeout(r, 400));
    const y = this.currentDate.getFullYear();
    const m = this.currentDate.getMonth();
    const start = `${y}-${pad2(m + 1)}-01`;
    const lastDay = new Date(y, m + 1, 0).getDate();
    const end = `${y}-${pad2(m + 1)}-${lastDay}`;

    try {
      const tzOffset = -new Date().getTimezoneOffset();
      const onlyMineParam = this.onlyMine ? '&only_mine=true' : '';
      this.allEvents = await api.get(`/calendar/events?start=${start}&end=${end}&tz_offset=${tzOffset}${onlyMineParam}`);
    } catch {
      this.allEvents = [];
    } finally {
      await _minLoad;
      this.loading = false;
    }
  },

  get monthYearLabel() {
    return this.currentDate.toLocaleString('ru-RU', { month: 'long', year: 'numeric' });
  },
  get taskCount()  { return this.allEvents.filter(e => e.source === 'task').length; },
  get assetCount() { return this.allEvents.filter(e => e.source === 'asset').length; },
  get noteCount()  { return this.allEvents.filter(e => e.source === 'note').length; },

  get systemFilters() {
    return Object.entries(SYSTEM_EVENT_TYPES).map(([key, cfg]) => ({
      key, label: cfg.label, color: cfg.color,
    }));
  },
  get categoryList() {
    return Object.values(this.categoriesById)
      .sort((a, b) => a.label.localeCompare(b.label));
  },
  get adminMasterActive() {
    return Object.keys(SYSTEM_EVENT_TYPES).every(k => this.filters[k]);
  },
  get notesMasterActive() {
    const ids = Object.keys(this.categoriesById);
    return ids.length > 0 && ids.every(id => this.filters[`category-${id}`]);
  },

  get canCreateNote() { return state.can('notes', 'create'); },

  shouldShowEvent(ev) {
    if (ev.type === 'task_due' || ev.type === 'task_start') return !!this.filters['task'];
    if (ev.type === 'warranty_end' || ev.type === 'commission') return !!this.filters['warranty'];
    if (ev.type === 'note') {
      if (ev.category_id) return !!this.filters[`category-${ev.category_id}`];

      const catKeys = Object.keys(this.filters).filter(k => k.startsWith('category-'));
      if (catKeys.length === 0) return true;
      return catKeys.some(k => this.filters[k]);
    }
    return !!this.filters[ev.type];
  },

  eventCoversDay(ev, dateStr) {
    if (ev.end_date) return ev.date <= dateStr && dateStr <= ev.end_date;
    return ev.date === dateStr;
  },

  enrich(ev, idx) {
    return {
      ...ev,
      uid: `${ev.source || 't'}-${ev.related_id || ev.id || idx}-${ev.date || ''}-${ev.type || ''}`,
      dotColor: eventDotColor(ev, this.categoriesById),
      typeLabel: eventTypeLabel(ev),
      titleAttr: ev.title || '',
    };
  },

  get visibleEvents() {
    return this.allEvents
      .filter(e => this.shouldShowEvent(e))
      .map((e, i) => this.enrich(e, i));
  },

  get startOffset() {
    const y = this.currentDate.getFullYear();
    const m = this.currentDate.getMonth();
    const firstDay = new Date(y, m, 1).getDay();
    return firstDay === 0 ? 6 : firstDay - 1;
  },

  get gridDays() {
    const y = this.currentDate.getFullYear();
    const m = this.currentDate.getMonth();
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${pad2(today.getMonth() + 1)}-${pad2(today.getDate())}`;
    const todayDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    const days = [];
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${y}-${pad2(m + 1)}-${pad2(d)}`;
      const cellDate = new Date(y, m, d);
      const dayEvents = this.allEvents
        .filter(e => this.shouldShowEvent(e))
        .filter(e => this.eventCoversDay(e, dateStr))
        .map((e, i) => this.enrich(e, i));
      days.push({
        dateStr,
        num: d,
        isToday: dateStr === todayStr,
        isPast:  cellDate < todayDate,
        events:  dayEvents.slice(0, 3),
        extra:   Math.max(0, dayEvents.length - 3),
      });
    }
    return days;
  },

  toggleOnlyMine() {
    this.onlyMine = !this.onlyMine;
    localStorage.setItem(ONLY_MINE_KEY, this.onlyMine ? '1' : '0');
    this.loadMonth();
  },

  prevMonth() {
    const d = new Date(this.currentDate);
    d.setMonth(d.getMonth() - 1);
    this.currentDate = d;
    this.loadMonth();
  },
  nextMonth() {
    const d = new Date(this.currentDate);
    d.setMonth(d.getMonth() + 1);
    this.currentDate = d;
    this.loadMonth();
  },
  jumpToday() {
    this.currentDate = new Date();
    this.loadMonth();
  },

  get dropdownYears() {
    const y = this.currentDate.getFullYear();
    return [y - 1, y, y + 1];
  },
  toggleMonthDropdown() {
    this.monthDropdownOpen = !this.monthDropdownOpen;
  },
  isSelectedMonth(y, idx) {
    return this.currentDate.getFullYear() === y && this.currentDate.getMonth() === idx;
  },
  isRealCurrentMonth(y, idx) {
    return this.realToday.getFullYear() === y && this.realToday.getMonth() === idx;
  },
  selectMonth(y, idx) {
    this.currentDate = new Date(y, idx, 1);
    this.monthDropdownOpen = false;
    this.loadMonth();
  },

  toggleFilter(key) {
    this.filters[key] = !this.filters[key];
  },
  toggleMaster(master) {
    const children = master === 'admin'
      ? Object.keys(SYSTEM_EVENT_TYPES)
      : Object.keys(this.categoriesById).map(id => `category-${id}`);
    const wasActive = master === 'admin' ? this.adminMasterActive : this.notesMasterActive;
    for (const c of children) this.filters[c] = !wasActive;
  },

  openCreateNote() {
    openNoteModal({ onSaved: () => this.loadMonth() });
  },

  onCellClick(e, day) {
    if (e.target.closest('.cal-event-dot') || e.target.closest('.cal-more')) return;
    const hasEvents = (day.events && day.events.length) || day.extra > 0;
    if (hasEvents) {
      // день с событиями — показываем их в правой панели (повторный клик снимает выбор)
      this.selectedDate = this.selectedDate === day.dateStr ? null : day.dateStr;
    } else {
      // пустой день — сразу создаём запись на эту дату
      openNoteModal({ presetDate: day.dateStr, onSaved: () => this.loadMonth() });
    }
  },
  clearSelectedDate() { this.selectedDate = null; },
  addNoteForSelected() {
    openNoteModal({ presetDate: this.selectedDate, onSaved: () => this.loadMonth() });
  },
  get selectedDateLabel() {
    if (!this.selectedDate) return '';
    const [y, m, d] = this.selectedDate.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('ru-RU',
      { day: '2-digit', month: 'long', year: 'numeric' });
  },
  get displayedEvents() {
    if (!this.selectedDate) return this.visibleEvents;
    return this.visibleEvents.filter(ev => this.eventCoversDay(ev, this.selectedDate));
  },

  onDotClick(e, ev) {
    const href = ev.link || '';
    const m = href.match(/#\/notes\/edit\/([^/?#]+)/);
    if (m) {
      e.preventDefault();
      e.stopPropagation();
      openNoteModal({ id: m[1], onSaved: () => this.loadMonth() });
    }
  },

  onListItemClick(e, ev) {
    const href = ev.link || '';
    const m = href.match(/#\/notes\/edit\/([^/?#]+)/);
    if (m) {
      e.preventDefault();
      e.stopPropagation();
      openNoteModal({ id: m[1], onSaved: () => this.loadMonth() });
    }
  },

  canDeleteNote(ev) {
    if (ev.type !== 'note') return false;
    return state.isAdmin || (ev.created_by === state.user.id && state.can('notes', 'delete'));
  },

  async deleteNote(ev) {
    if (!ev.related_id) return;
    if (!confirm('Вы уверены, что хотите удалить эту запись?')) return;
    try {
      await api.delete(`/notes/${ev.related_id}`);
      await this.loadMonth();
      toast.success('Запись удалена');
    } catch (e) {
      toast.error(`Ошибка удаления: ${e.message}`);
    }
  },
}));

export async function renderCalendarPage() {
  return tpl;
}

export function initCalendarEvents() {}
