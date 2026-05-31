
import Alpine from 'alpinejs';
import tpl from './dashboard.html?raw';

import { api } from '../../api/client.js';
import { Icons } from '../../components/icons.js';

const ACCENT = '#008080';
const MUTED  = '#C4C9D4';

const PRIORITY_COLOR = {
  low: '#9ca3af', medium: '#3b82f6', high: '#f59e0b', critical: '#ef4444',
};

function dayStart(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
function startOfWeek(d = new Date()) {
  const date = dayStart(d);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  return date;
}
function fmtRange(start, end) {
  const f = (d) => d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
  return `${f(start)} — ${f(end)}`;
}

const DAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function bucketByDay(items, getDate, days, now) {
  const buckets = new Array(days).fill(0);
  const start = dayStart(now);
  start.setDate(start.getDate() - (days - 1));
  for (const it of items) {
    const raw = getDate(it);
    if (!raw) continue;
    const d = dayStart(raw);
    if (isNaN(d.getTime())) continue;
    const idx = Math.round((d - start) / 86400000);
    if (idx >= 0 && idx < days) buckets[idx] += 1;
  }
  return buckets;
}

function buildPoints(values, w, h, pad, maxOverride) {
  const max = maxOverride || Math.max(1, ...values);
  const stepX = w / (values.length - 1 || 1);
  return values.map((v, i) => ({
    x: i * stepX,
    y: h - pad - (v / max) * (h - 2 * pad),
  }));
}

function smoothPath(points) {
  const n = points.length;
  if (n === 0) return '';
  if (n === 1) return `M${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;

  const dx = [], delta = [];
  for (let i = 0; i < n - 1; i++) {
    const hx = points[i + 1].x - points[i].x;
    dx.push(hx);
    delta.push(hx === 0 ? 0 : (points[i + 1].y - points[i].y) / hx);
  }

  const m = new Array(n);
  m[0] = delta[0];
  m[n - 1] = delta[n - 2];
  for (let i = 1; i < n - 1; i++) {
    m[i] = (delta[i - 1] * delta[i] <= 0) ? 0 : (delta[i - 1] + delta[i]) / 2;
  }

  for (let i = 0; i < n - 1; i++) {
    if (delta[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / delta[i];
    const b = m[i + 1] / delta[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * delta[i];
      m[i + 1] = t * b * delta[i];
    }
  }

  let d = `M${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i];
    const cp1x = points[i].x + h / 3;
    const cp1y = points[i].y + (m[i] * h) / 3;
    const cp2x = points[i + 1].x - h / 3;
    const cp2y = points[i + 1].y - (m[i + 1] * h) / 3;
    d += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${points[i + 1].x.toFixed(1)},${points[i + 1].y.toFixed(1)}`;
  }
  return d;
}

const DOW_LABELS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

Alpine.data('dashboardPage', () => ({
  Icons,

  loading: true,
  assets: [],
  tasks:  [],
  users:  [],
  now:    new Date(),

  activityDays: 30,
  activityZoom: false,
  timelineZoom: false,

  async init() {
    this.now = new Date();
    this.loading = true;
    try {
      const [a, t, u] = await Promise.all([
        api.get('/assets').catch(() => []),
        api.get('/tasks').catch(() => []),
        api.get('/users').catch(() => []),
      ]);
      this.assets = a || [];
      this.tasks  = t || [];
      this.users  = u || [];
    } catch (err) {
      console.error('Dashboard data fetch failed:', err);
    } finally {
      this.loading = false;
    }
  },

  get todayLabel() {
    return this.now.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
  },

  get metrics() {
    const t = this.tasks;
    const now = this.now;
    const getDate = (x) => x.start_date || x.created_at;

    const active   = t.filter(x => x.status === 'pending' || x.status === 'in_progress');
    const closed   = t.filter(x => x.status === 'completed');
    const planned  = t.filter(x => x.status === 'pending' && x.start_date && new Date(x.start_date) > now);
    const critical = t.filter(x => x.priority === 'critical' && x.status !== 'completed' && x.status !== 'cancelled');

    const mk = (arr) => {
      const line = smoothPath(buildPoints(bucketByDay(arr, getDate, 30, now), 100, 50, 4));
      return { sparkPath: line, sparkArea: line ? `${line} L100,50 L0,50 Z` : '' };
    };

    return [
      { title: 'Активные задачи',        value: active.length,   iconHtml: Icons.clock(18),       gradId: 'm1', route: '/tasks', preset: { status: 'in_progress' }, ...mk(active) },
      { title: 'Закрытые задачи',        value: closed.length,   iconHtml: Icons.checkCircle(18), gradId: 'm2', route: '/tasks', preset: { status: 'completed' },   ...mk(closed) },
      { title: 'Запланированные работы', value: planned.length,  iconHtml: Icons.calendar(18),    gradId: 'm3', route: '/tasks', preset: { status: 'pending' },     ...mk(planned) },
      { title: 'Критические задачи',     value: critical.length, iconHtml: Icons.alert(18),       gradId: 'm4', route: '/tasks', preset: { priority: 'critical' },  ...mk(critical) },
    ];
  },

  accentColor: ACCENT,

  openMetric(m) {
    if (m.preset) localStorage.setItem('tasksPreset', JSON.stringify(m.preset));
    window.location.hash = m.route;
  },

  get activity() {
    const days = this.activityDays;
    const now = this.now;
    const created = bucketByDay(this.tasks, x => x.created_at, days, now);
    const closed  = bucketByDay(
      this.tasks.filter(x => x.status === 'completed'),
      x => x.updated_at || x.created_at, days, now,
    );
    const max = Math.max(1, ...created, ...closed);
    const W = 1000, H = 200, PAD = 12;
    const createdPath = smoothPath(buildPoints(created, W, H, PAD, max));
    const closedPath  = smoothPath(buildPoints(closed,  W, H, PAD, max));

    const ticks = Math.min(5, max);
    const yTicks = [];
    for (let i = ticks; i >= 0; i--) yTicks.push(Math.round((max * i) / ticks));

    const start = dayStart(now);
    start.setDate(start.getDate() - (days - 1));
    const xLabels = [];

    const stepLabel = Math.ceil(days / 8);
    for (let i = 0; i < days; i += stepLabel) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      xLabels.push(d.getDate());
    }

    return {
      createdPath,
      createdArea: createdPath ? `${createdPath} L${W},${H} L0,${H} Z` : '',
      closedPath,
      yTicks,
      xLabels,
    };
  },
  toggleActivityRange() { this.activityDays = this.activityDays === 30 ? 7 : 30; },
  get activityRangeLabel() { return this.activityDays === 30 ? '30 дней' : '7 дней'; },
  toggleActivityZoom() { this.activityZoom = !this.activityZoom; },

  get weekDays() {

    const today = dayStart(this.now);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      return {
        iso: d.toISOString(),
        label: DOW_LABELS[d.getDay()],
        num: d.getDate(),
        cls: i === 0 ? 'is-today' : 'is-clickable',
      };
    });
  },
  get scheduleTasks() {
    const today = dayStart(this.now);
    return this.tasks
      .filter(t => t.start_date && !isNaN(new Date(t.start_date).getTime()))
      .map(t => ({ t, d: new Date(t.start_date) }))
      .filter(x => x.d >= today || (x.t.status !== 'completed' && x.t.status !== 'cancelled'))
      .sort((a, b) => a.d - b.d)
      .slice(0, 5)
      .map(({ t, d }) => ({
        id: t.id,
        color: PRIORITY_COLOR[t.priority] || PRIORITY_COLOR.medium,
        title: t.title || 'Без названия',
        time: d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' }),
      }));
  },
  goCalendar() { window.location.hash = '/calendar'; },

  get timelineRangeLabel() {
    const start = dayStart(this.now);
    const end = new Date(start);
    end.setDate(start.getDate() + 21);
    return fmtRange(start, end);
  },
  get timelineRows() {
    const start = dayStart(this.now);
    const end = new Date(start);
    end.setDate(start.getDate() + 21);
    const totalMs = end.getTime() - start.getTime();

    return this.tasks
      .filter(t => {
        const s = t.start_date ? new Date(t.start_date) : null;
        if (!s || isNaN(s.getTime())) return false;
        const e = t.due_date ? new Date(t.due_date) : s;
        return (e || s) >= start && s <= end;
      })
      .slice(0, 6)
      .map(t => {
        const s = new Date(t.start_date);
        const e = t.due_date ? new Date(t.due_date) : new Date(s.getTime() + 86400000);
        const left  = Math.max(0, ((s.getTime() - start.getTime()) / totalMs) * 100);
        const width = Math.max(2, Math.min(100 - left, ((e.getTime() - s.getTime()) / totalMs) * 100));
        return {
          label: t.title || 'Без названия',
          left, width,
          color: PRIORITY_COLOR[t.priority] || PRIORITY_COLOR.medium,
        };
      });
  },
  toggleTimelineZoom() { this.timelineZoom = !this.timelineZoom; },
}));

export async function renderDashboardPage() {
  return tpl;
}

export function initDashboardEvents() {}
