
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

  notes: [],
  total: 0,
  stats: { total: 0, with_asset: 0, with_user: 0 },
  categoriesById: {},

  page: 1,
  pageSize: PAGE_SIZE,

  sortBy: 'created_at',
  sortOrder: 'desc',

  search: '',
  categoryFilter: '',
  loading: false,

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
  get visibleNotes() { return this.notes; },
  get totalAll()       { return this.stats.total; },
  get withAssetCount() { return this.stats.with_asset; },
  get withUserCount()  { return this.stats.with_user; },
  get canCreate() {
    return state.can('notes', 'create');
  },

  async init() {
    this.$watch('categoryFilter', () => this.applyFilters());
    this.$watch('search', () => {
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(() => this.applyFilters(), 350);
    });
    await Promise.all([this.loadCategories(), this.load()]);
  },

  applyFilters() {
    this.page = 1;
    this.load();
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
    const _minLoad = new Promise(r => setTimeout(r, 400));
    try {
      const skip = (this.page - 1) * this.pageSize;
      let url = `/notes/?skip=${skip}&limit=${this.pageSize}`
        + `&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
      if (this.search.trim())   url += `&search=${encodeURIComponent(this.search.trim())}`;
      if (this.categoryFilter)  url += `&category=${encodeURIComponent(this.categoryFilter)}`;

      const [{ items, total }, stats] = await Promise.all([
        api.getPaginated(url),
        api.get('/notes/stats').catch(() => this.stats),
      ]);
      this.notes = items;
      this.total = total;
      this.stats = stats;
    } catch (e) {
      console.error('Ошибка загрузки заметок:', e);
      this.notes = [];
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

  canEdit(note) {
    if (state.isAdmin) return true;
    return String(note.created_by) === String(state.user.id) && state.can('notes', 'update');
  },
  canDelete(note) {
    if (state.isAdmin) return true;
    return String(note.created_by) === String(state.user.id) && state.can('notes', 'delete');
  },

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

  fmtDate,
  fmtDateTime,
}));

export async function renderNotesPage() {
  return tpl;
}

export function initNotesEvents() {}
