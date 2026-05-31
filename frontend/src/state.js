
import { api } from './api/client.js';

const _empty = {
  id: null,
  username: '',
  fullName: '',
  email: null,
  phone: null,
  role: 'user',
  isActive: true,
  isActivated: true,
  passwordChangeRequired: false,
  theme: null,
  permissions: {
    assets:     { create: false, read: false, update: false, delete: false },
    tasks:      { create: false, read: false, update: false, delete: false },
    notes:      { create: false, read: false, update: false, delete: false },
    categories: { create: false, read: false, update: false, delete: false },
  },
};

let _state = { ..._empty };

export const state = {
  get user() { return _state; },
  get isAdmin() { return _state.role === 'admin'; },
  get isLoggedIn() { return !!_state.id; },
  get permissions() { return _state.permissions; },

  canSee(resource) {
    if (this.isAdmin) return true;
    return !!_state.permissions?.[resource]?.read;
  },

  can(resource, action) {
    if (this.isAdmin) return true;
    return !!_state.permissions?.[resource]?.[action];
  },

  async load() {
    const r = await api.authCheck();
    if (r.status !== 'authenticated' || !r.user) {
      this.clear();
      throw new Error('Not authenticated');
    }
    const u = r.user;
    _state = {
      id:                      u.id,
      username:                u.username,
      fullName:                u.full_name || '',
      email:                   u.email || null,
      phone:                   u.phone || null,
      role:                    u.role || 'user',
      isActive:                u.is_active !== false,
      isActivated:             u.is_activated !== false,
      passwordChangeRequired:  !!u.password_change_required,
      permissions:             u.permissions || _empty.permissions,
      theme:                   u.theme || null,
    };
    return _state;
  },

  clear() {
    _state = { ..._empty };
  },
};
