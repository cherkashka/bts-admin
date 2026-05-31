/**
 * Страница «Заметки» — Alpine.js компонент.
 *
 * Архитектурное соглашение:
 *   - вся разметка живёт в notes.html;
 *   - этот файл импортирует её строкой (Vite ?raw) и регистрирует поведение
 *     через Alpine.data — в коде нет ни одной HTML-строки.
 */
import Alpine from 'alpinejs';
import tpl from './notes.html?raw';

import { api, notes as notesApi, categories as categoriesApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { openNoteModal } from '../note-modal/note-modal.js';

const PAGE_SIZE = 25;

const SYSTEM_CATEGORY_COLOR = '#3b82f6';
const SYSTEM_CATEGORY_LABEL = 'Без категории';

function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU');
}

function fmtDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  });
}

Alpine.data('notesPage', () => ({
  // Данные
  notes: [],
  total: 0,
  categoriesById: {},

  // Пагинация
  page: 1,
  pageSize: PAGE_SIZE,

  // Сортировка
  sortBy: 'created_at',
  sortOrder: 'desc',

  // UI-состояние
  search: '',
  categoryFilter: '',
  loading: false,

  // Геттеры
  get pages() {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  },
  get categoryOptions() {
    return Object.values(this.categoriesById)
      .sort((a, b) => {
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        return a.name.localeCompare(b.name);
      });
  },
  get visibleNotes() {
    const q = this.search.trim().toLowerCase();
    const cat = this.categoryFilter;
    return this.notes.filter(n => {
      if (q) {
        const blob = [n.title, n.content].filter(Boolean).join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      if (cat === '__none__') {
        if (n.category_id) return false;
      } else if (cat) {
        if (n.category_id !== cat) return false;
      }
      return true;
    });
  },
  get withAssetCount() {
    return this.notes.filter(n => n.related_asset_id).length;
  },
  get withUserCount() {
    return this.notes.filter(n => n.related_user_id).length;
  },
  get canCreate() {
    return state.can('notes', 'create');
  },

  // Lifecycle
  async init() {
    await Promise.all([this.loadCategories(), this.load()]);
  },

  async loadCategories() {
    try {
      const cats = await categoriesApi.getAll(true);
      const map = {};
      for (const c of cats) map[c.id] = c;
      this.categoriesById = map;
    } catch (e) {
      console.error('Ошибка загрузки категорий:', e);
    }
  },

  async load() {
    this.loading = true;
    try {
      const skip = (this.page - 1) * this.pageSize;
      const url = `/notes/?skip=${skip}&limit=${this.pageSize}`
        + `&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
      const { items, total } = await api.getPaginated(url);
      this.notes = items;
      this.total = total;
    } catch (e) {
      console.error('Ошибка загрузки заметок:', e);
      this.notes = [];
      this.total = 0;
    } finally {
      this.loading = false;
    }
  },

  // Сортировка
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

  // Пагинация
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

  // Категории — отображение (иконка + имя, как в календаре/модалке)
  categoryLabel(id) {
    if (!id) return SYSTEM_CATEGORY_LABEL;
    const cat = this.categoriesById[id];
    if (!cat) return SYSTEM_CATEGORY_LABEL;
    return cat.name;
  },
  categoryStyle(id) {
    const color = (id && this.categoriesById[id]?.color) || SYSTEM_CATEGORY_COLOR;
    return `background:${color}20;color:${color};border:1px solid ${color}55;`;
  },

  // Права на строку
  canEdit(note) {
    return state.isAdmin || String(note.created_by) === String(state.user.id);
  },
  canDelete(note) {
    return this.canEdit(note);
  },

  // CRUD-действия
  openCreate() {
    openNoteModal({ onSaved: () => this.load() });
  },
  openEdit(note) {
    openNoteModal({ id: note.id, onSaved: () => this.load() });
  },
  async remove(note) {
    if (!confirm(`Удалить заметку «${note.title}»? Действие необратимо.`)) return;
    try {
      await notesApi.delete(note.id);
      await this.load();
      toast.success('Заметка удалена');
    } catch (e) {
      toast.error(`Ошибка удаления: ${e.message}`);
    }
  },

  // Форматтеры — используются в шаблоне через x-text
  fmtDate,
  fmtDateTime,
}));

/**
 * Возвращает разметку страницы. Никакой HTML внутри функции — только импорт.
 * Alpine автоматически активирует x-data при вставке в DOM.
 */
export async function renderNotesPage() {
  return tpl;
}

/**
 * Заглушка для совместимости с роутером (события навешивает Alpine
 * через декларативные атрибуты, императивный init не нужен).
 */
export function initNotesEvents() {}
