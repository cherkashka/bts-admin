
import Alpine from 'alpinejs';
import tpl from './tasks.html?raw';

import { api, tasks as tasksApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { openTaskModal } from '../task-modal/task-modal.js';

const PAGE_SIZE = 25;

const STATUS_LABELS = {
  pending:     'Ожидает',
  in_progress: 'В работе',
  completed:   'Выполнена',
  cancelled:   'Отменена',
};
const STATUS_BADGE = {
  pending:     'badge-info',
  in_progress: 'badge-warning',
  completed:   'badge-success',
  cancelled:   'badge-secondary',
};

const PRIORITY_LABELS = {
  low:      'Низкий',
  medium:   'Средний',
  high:     'Высокий',
  critical: 'Критический',
};
const PRIORITY_BADGE = {
  low:      'badge-secondary',
  medium:   'badge-info',
  high:     'badge-warning',
  critical: 'badge-danger',
};

const PRIORITY_COLOR = {
  low:      '#9ca3af',
  medium:   '#3b82f6',
  high:     '#f59e0b',
  critical: '#ef4444',
};

function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU');
}

function isOverdue(task) {
  if (!task.due_date) return false;
  if (task.status === 'completed' || task.status === 'cancelled') return false;
  return new Date(task.due_date) < new Date();
}

Alpine.data('tasksPage', () => ({
  tasks: [],
  total: 0,

  page: 1,
  pageSize: PAGE_SIZE,

  sortBy: 'start_date',
  sortOrder: 'asc',

  search: '',
  statusFilter: '',
  priorityFilter: '',
  onlyMine: false,
  onlyOverdue: false,

  loading: false,

  get pages() {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  },
  get visibleTasks() {
    const q = this.search.trim().toLowerCase();
    const st = this.statusFilter;
    const pr = this.priorityFilter;
    const mine = this.onlyMine;
    const overdueOnly = this.onlyOverdue;
    const myId = state.user.id;
    return this.tasks.filter(t => {
      if (st && t.status !== st) return false;
      if (pr && t.priority !== pr) return false;
      if (mine && t.assigned_to !== myId) return false;
      if (overdueOnly && !isOverdue(t)) return false;
      if (q) {
        const blob = [t.title, t.description, t.assigned_to_name]
          .filter(Boolean).join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  },
  get inProgressCount() { return this.tasks.filter(t => t.status === 'in_progress').length; },
  get completedCount()  { return this.tasks.filter(t => t.status === 'completed').length; },
  get criticalCount() {
    return this.tasks.filter(t => t.priority === 'critical'
      && t.status !== 'completed' && t.status !== 'cancelled').length;
  },
  get canCreate() { return state.isAdmin || state.can('tasks', 'create'); },

  async init() {

    try {
      const raw = localStorage.getItem('tasksPreset');
      if (raw) {
        localStorage.removeItem('tasksPreset');
        const preset = JSON.parse(raw);
        if (preset.status)   this.statusFilter = preset.status;
        if (preset.priority) this.priorityFilter = preset.priority;
      }
    } catch {  }
    await this.load();
  },

  async load() {
    this.loading = true;
    try {
      const skip = (this.page - 1) * this.pageSize;
      const url = `/tasks?skip=${skip}&limit=${this.pageSize}`
        + `&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
      const { items, total } = await api.getPaginated(url);
      this.tasks = items;
      this.total = total;
    } catch (e) {
      console.error('Ошибка загрузки задач:', e);
      this.tasks = [];
      this.total = 0;
    } finally {
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

  statusLabel(s) { return STATUS_LABELS[s] || s || '—'; },
  statusBadgeClass(s) { return STATUS_BADGE[s] || 'badge-secondary'; },
  priorityLabel(p) { return PRIORITY_LABELS[p] || p || '—'; },
  priorityBadgeClass(p) { return PRIORITY_BADGE[p] || 'badge-secondary'; },
  priorityColor(p) { return PRIORITY_COLOR[p] || '#9ca3af'; },

  descPreview(text) {
    if (!text) return '';
    return text.length > 80 ? `${text.slice(0, 80)}…` : text;
  },

  canEditFull(_task) {
    return state.isAdmin || state.can('tasks', 'update');
  },
  canChangeStatus(task) {
    return this.canEditFull(task) || task.assigned_to === state.user.id;
  },
  canDelete(_task) {
    return state.isAdmin || state.can('tasks', 'delete');
  },

  openCreate() {
    openTaskModal({ mode: 'add', onSaved: () => this.load() });
  },
  openEdit(task) {
    openTaskModal({ mode: 'edit', id: task.id, onSaved: () => this.load() });
  },
  openStatus(task) {
    openTaskModal({ mode: 'status', id: task.id, onSaved: () => this.load() });
  },
  async remove(task) {
    if (!confirm('Удалить задачу? Это действие необратимо.')) return;
    try {
      await tasksApi.delete(task.id);
      await this.load();
      toast.success('Задача удалена');
    } catch (e) {
      toast.error(`Ошибка удаления: ${e.message}`);
    }
  },

  fmtDate,
  isOverdue,
}));

export async function renderTasksPage() {
  return tpl;
}

export function initTasksEvents() {}
