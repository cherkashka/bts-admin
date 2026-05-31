
import Alpine from 'alpinejs';
import tpl from './audit.html?raw';

import { api } from '../../api/client.js';

const PAGE_SIZE = 50;

const ENTITY_LABELS = {
  asset:    'Актив',
  task:     'Задача',
  user:     'Сотрудник',
  note:     'Заметка',
  category: 'Категория',
};

const ACTION_LABELS = {
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление',
};

const ACTION_COLORS = {
  create: '#10b981',
  update: '#f59e0b',
  delete: '#ef4444',
};

const FIELD_LABELS = {
  name: 'Название', inventory_number: 'Инв. номер', serial_number: 'Серийный номер',
  asset_type: 'Тип', status: 'Статус', mol_user_id: 'МОЛ (id)', mol_name: 'МОЛ',
  mac_address: 'MAC-адрес', location: 'Расположение', comments: 'Комментарии',
  commission_date: 'Дата ввода', warranty_end_date: 'Конец гарантии',
  warranty_months: 'Гарантия (мес.)',
  title: 'Заголовок', description: 'Описание', priority: 'Приоритет',
  task_type: 'Тип задачи', assigned_to: 'Исполнитель (id)',
  assigned_to_name: 'Исполнитель', start_date: 'Начало', due_date: 'Срок',
  related_asset_id: 'Связанный актив', related_user_id: 'Связанный сотрудник',
  full_name: 'ФИО', email: 'Email', phone: 'Телефон', role: 'Роль',
  is_active: 'Активен', permissions: 'Права',
  content: 'Текст', event_start: 'Начало события', event_end: 'Конец события',
  category_id: 'Категория (id)',
  color: 'Цвет', icon: 'Иконка',
};

const CHANGE_HINTS = {
  create: 'Создано со значениями:',
  update: 'Изменённые поля:',
  delete: 'Удалено (значения на момент удаления):',
};

function fmtDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtVal(v) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'да' : 'нет';
  if (typeof v === 'object') return JSON.stringify(v);

  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    const d = new Date(v);
    if (!isNaN(d.getTime())) return d.toLocaleString('ru-RU');
  }
  return String(v);
}

Alpine.data('auditPage', () => ({
  entries: [],
  total: 0,
  page: 1,
  pageSize: PAGE_SIZE,
  loading: false,

  entityType: '',
  action: '',
  days: '',

  openIds: [],

  get pages() {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  },

  async init() {
    await this.load();
  },

  async load() {
    this.loading = true;
    try {
      const skip = (this.page - 1) * this.pageSize;
      let url = `/audit?skip=${skip}&limit=${this.pageSize}`;
      if (this.entityType) url += `&entity_type=${this.entityType}`;
      if (this.action)     url += `&action=${this.action}`;
      if (this.days)       url += `&days=${this.days}`;
      const { items, total } = await api.getPaginated(url);
      this.entries = items;
      this.total = total;
    } catch (e) {
      console.error('Ошибка загрузки аудит-лога:', e);
      this.entries = [];
      this.total = 0;
    } finally {
      this.loading = false;
    }
  },

  applyFilters() {
    this.page = 1;
    this.openIds = [];
    this.load();
  },

  prevPage() {
    if (this.page <= 1) return;
    this.page -= 1;
    this.openIds = [];
    this.load();
  },
  nextPage() {
    if (this.page >= this.pages) return;
    this.page += 1;
    this.openIds = [];
    this.load();
  },

  toggle(id) {
    const i = this.openIds.indexOf(id);
    if (i === -1) this.openIds.push(id);
    else this.openIds.splice(i, 1);
  },
  isOpen(id) {
    return this.openIds.includes(id);
  },

  entityLabel(t) { return ENTITY_LABELS[t] || t; },
  actionLabel(a) { return ACTION_LABELS[a] || a; },
  actionStyle(a) {
    const c = ACTION_COLORS[a] || '#6b7280';
    return `background:${c}20;color:${c};border:1px solid ${c}55;`;
  },
  changeHint(a) { return CHANGE_HINTS[a] || ''; },

  changeRows(entry) {
    const before = entry.before || {};
    const after = entry.after || {};
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
    return keys.map(k => ({
      field: FIELD_LABELS[k] || k,
      from: fmtVal(before[k]),
      to: fmtVal(after[k]),
    }));
  },

  fmtDateTime,
}));

export async function renderAuditPage() {
  return tpl;
}

export function initAuditEvents() {}
