
import Alpine from 'alpinejs';
import tpl from './assets.html?raw';

import { api, assets as assetsApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { openAssetModal } from '../asset-modal/asset-modal.js';

const PAGE_SIZE = 25;

const ASSET_TYPE_LABELS = {
  laptop: 'Ноутбук',
  desktop: 'ПК',
  monitor: 'Монитор',
  printer: 'Принтер/МФУ',
  peripheral: 'Периферия',
  mobile: 'Смартфон/Планшет',
  other: 'Прочее',
};

const STATUS_LABELS = {
  installed: 'Установлен',
  in_use:    'В использовании',
  repair:    'На ремонте',
  retired:   'Снят с эксплуатации',
};

const STATUS_BADGE = {
  installed: 'badge-info',
  in_use:    'badge-success',
  repair:    'badge-warning',
  retired:   'badge-secondary',
};

function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU');
}

Alpine.data('assetsPage', () => ({
  assets: [],
  total: 0,

  page: 1,
  pageSize: PAGE_SIZE,

  sortBy: 'created_at',
  sortOrder: 'desc',

  search: '',
  statusFilter: '',
  typeFilter: '',

  expanded: {},
  loading: false,

  get pages() {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  },
  get assetTypeList() {
    return Object.entries(ASSET_TYPE_LABELS).map(([value, label]) => ({ value, label }));
  },
  get visibleAssets() {
    const q = this.search.trim().toLowerCase();
    const st = this.statusFilter;
    const tp = this.typeFilter;
    return this.assets.filter(a => {
      if (st && a.status !== st) return false;
      if (tp && a.asset_type !== tp) return false;
      if (q) {
        const blob = [a.name, a.inventory_number, a.serial_number, a.asset_type, a.mol_name]
          .filter(Boolean).join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  },
  get inUseCount()   { return this.assets.filter(a => a.status === 'in_use').length; },
  get repairCount()  { return this.assets.filter(a => a.status === 'repair').length; },
  get retiredCount() { return this.assets.filter(a => a.status === 'retired').length; },
  get canCreate() { return state.can('assets', 'create'); },
  get canEdit()   { return state.can('assets', 'update'); },
  get canDelete() { return state.can('assets', 'delete'); },

  async init() {
    await this.load();
  },

  async load() {
    this.loading = true;
    const _minLoad = new Promise(r => setTimeout(r, 400));
    try {
      const skip = (this.page - 1) * this.pageSize;
      const url = `/assets?skip=${skip}&limit=${this.pageSize}`
        + `&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
      const { items, total } = await api.getPaginated(url);
      this.assets = items;
      this.total = total;
    } catch (e) {
      console.error('Ошибка загрузки активов:', e);
      this.assets = [];
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

  toggleDetails(id) {
    this.expanded[id] = !this.expanded[id];
  },

  assetTypeLabel(t) { return ASSET_TYPE_LABELS[t] || t || '—'; },
  statusLabel(s)    { return STATUS_LABELS[s] || s || '—'; },
  statusBadgeClass(s) { return STATUS_BADGE[s] || 'badge-secondary'; },

  openCreate() {
    openAssetModal({ mode: 'add', onSaved: () => this.load() });
  },
  openEdit(asset) {
    openAssetModal({ mode: 'edit', id: asset.id, onSaved: () => this.load() });
  },
  async remove(asset) {
    if (!confirm('Удалить актив? Это действие необратимо.')) return;
    try {
      await assetsApi.delete(asset.id);
      await this.load();
      toast.success('Актив удалён');
    } catch (e) {
      toast.error(`Ошибка удаления: ${e.message}`);
    }
  },

  fmtDate,
}));

export async function renderAssetsPage() {
  return tpl;
}

export function initAssetsEvents() {}
