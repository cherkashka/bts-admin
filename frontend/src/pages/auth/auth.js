
import Alpine from 'alpinejs';
import tpl from './auth.html?raw';

import { api } from '../../api/client.js';

Alpine.data('authPage', () => ({
  username: '',
  password: '',
  showPassword: false,
  message: { text: '', isError: false },

  router: null,

  init(router) {

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

export function initAuthEvents(router) {
  if (router) window.appRouter = router;
}
