
import Alpine from 'alpinejs';
import tpl from './categories.html?raw';

import { categories as categoriesApi } from '../../api/client.js';
import { toast } from '../../components/Toast/Toast.js';
import { state } from '../../state.js';
import { openCategoryModal } from '../category-modal/category-modal.js';

Alpine.data('categoriesPage', () => ({
  categories: [],
  loading: false,

  get canCreate() { return state.can('categories', 'create'); },
  get canEdit()   { return state.can('categories', 'update'); },
  get canDelete() { return state.can('categories', 'delete'); },

  async init() {
    await this.load();
  },

  async load() {
    this.loading = true;
    const _minLoad = new Promise(r => setTimeout(r, 400));
    try {
      const list = await categoriesApi.getAll(true);
      list.sort((a, b) => {
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        return a.name.localeCompare(b.name);
      });
      this.categories = list;
    } catch (e) {
      console.error('Ошибка загрузки категорий:', e);
      toast.error('Не удалось загрузить категории');
    } finally {
      await _minLoad;
      this.loading = false;
    }
  },

  openCreate() {
    openCategoryModal({ onSaved: () => this.load() });
  },
  openEdit(cat) {
    openCategoryModal({ category: cat, onSaved: () => this.load() });
  },
  async remove(cat) {
    const ok = confirm(
      `Удалить категорию «${cat.name}»?\n\nКатегорию с привязанными записями удалить нельзя — сначала уберите её у записей.`
    );
    if (!ok) return;
    try {
      await categoriesApi.delete(cat.id);
      await this.load();
      toast.success('Категория удалена');
    } catch (e) {
      toast.error('Ошибка удаления: ' + e.message);
    }
  },
}));

export async function renderCategoriesPage() {
  return tpl;
}

export function initCategoriesEvents() {}
