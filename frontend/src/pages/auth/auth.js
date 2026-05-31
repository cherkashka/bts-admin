/**
 * Страница «Вход» (полноэкранная) — Alpine.js компонент.
 * Шаблон в auth.html, в коде HTML нет.
 */
import Alpine from 'alpinejs';
import tpl from './auth.html?raw';

import { api } from '../../api/client.js';

Alpine.data('authPage', () => ({
  username: '',
  password: '',
  showPassword: false,
  message: { text: '', isError: false },

  // router передаётся при init — храним для использования после логина
  router: null,

  init(router) {
    // x-init передаёт магический $router от Alpine — нам не подходит,
    // но мы используем именованный аргумент из renderAuth (см. ниже).
    this.router = router?.appRouter || window.appRouter || null;
  },

  show(text, isError = false) {
    this.message = { text, isError };
    setTimeout(() => { this.message = { text: '', isError: false }; }, 5000);
  },

  async submit() {
    try {
      const response = await api.post('/auth/login', {
        username: this.username,
        password: this.password,
      });
      if (response.status === 'success') {
        localStorage.setItem('isLoggedIn', 'true');
        if (this.router?.refreshState) await this.router.refreshState();
        window.location.hash = response.password_change_required
          ? '/first-login'
          : '/dashboard';
      }
    } catch (err) {
      this.show(err.message, true);
    }
  },
}));

export async function renderAuthPage() {
  return tpl;
}

/**
 * Передаёт ссылку на router в Alpine-компонент через window.appRouter.
 * Сам Alpine компонент берёт её в init() — императивная установка не нужна.
 */
export function initAuthEvents(router) {
  if (router) window.appRouter = router;
}
