/**
 * Страница «Экспорт» — Alpine.js компонент.
 * Шаблон в export.html, в коде нет HTML.
 */
import Alpine from 'alpinejs';
import tpl from './export.html?raw';

import { api } from '../../api/client.js';

Alpine.data('exportPage', () => ({
  types: { assets: true, users: true, tasks: true },
  format: 'csv',
  dateFrom: '',
  dateTo: '',

  busy: false,
  errorMsg: '',

  stats: { assets: 'Загрузка…', users: 'Загрузка…', tasks: 'Загрузка…' },

  async init() {
    try {
      const [a, u, t] = await Promise.all([
        api.get('/assets'),
        api.get('/users'),
        api.get('/tasks'),
      ]);
      this.stats.assets = Array.isArray(a) ? a.length : '—';
      this.stats.users  = Array.isArray(u) ? u.length : '—';
      this.stats.tasks  = Array.isArray(t) ? t.length : '—';
    } catch {
      this.stats = { assets: 'Недоступно', users: 'Недоступно', tasks: 'Недоступно' };
    }
  },

  selectedTypes() {
    const out = [];
    if (this.types.assets) out.push('assets');
    if (this.types.users)  out.push('users');
    if (this.types.tasks)  out.push('tasks');
    return out;
  },

  async doExport() {
    const types = this.selectedTypes();
    if (types.length === 0) {
      this.errorMsg = 'Выберите хотя бы один тип данных для экспорта.';
      return;
    }
    this.errorMsg = '';
    this.busy = true;

    try {
      const resp = await fetch('/api/v1/export', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format: this.format,
          types,
          date_from: this.dateFrom || null,
          date_to:   this.dateTo   || null,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        const msg = Array.isArray(err.detail)
          ? err.detail.map(d => d.msg || JSON.stringify(d)).join('; ')
          : (err.detail || `Ошибка ${resp.status}`);
        this.errorMsg = msg;
        return;
      }

      const blob = await resp.blob();
      const disposition = resp.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="([^"]+)"/);
      const fallback = `export.${this.format === 'xlsx'
        ? 'xlsx'
        : (types.length > 1 ? 'zip' : 'csv')}`;
      const filename = match ? match[1] : fallback;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      this.errorMsg = `Ошибка при экспорте: ${err.message}`;
    } finally {
      this.busy = false;
    }
  },
}));

export async function renderExportPage() {
  return tpl;
}

export function initExportEvents() {}
