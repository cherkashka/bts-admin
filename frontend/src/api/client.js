const API_BASE = '/api/v1';

async function request(endpoint, options = {}, isRetry = false) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        credentials: 'include',
        ...options,
    };

    // Запросы самой авторизации (вход, обновление токена) НЕ должны
    // запускать авто-рефреш и редирект на /login — их 401 означает
    // «неверные данные», и ошибку нужно показать на форме как есть.
    const isAuthCall = endpoint.startsWith('/auth/login')
                    || endpoint.startsWith('/auth/refresh');

    try {
        const response = await fetch(url, config);

        if (response.status === 401 && !isRetry && !isAuthCall) {
            try {
                const refreshResponse = await fetch(`${API_BASE}/auth/refresh`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                });
                if (refreshResponse.ok) {
                    return request(endpoint, options, true);
                }
                throw new Error('Refresh failed');
            } catch {
                localStorage.removeItem('isLoggedIn');
                if (window.location.hash !== '#/login') window.location.hash = '/login';
                throw new Error('Unauthorized');
            }
        }

        if (response.status === 401 && !isAuthCall) {
            localStorage.removeItem('isLoggedIn');
            if (window.location.hash !== '#/login') window.location.hash = '/login';
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));

            let message;
            if (Array.isArray(err.detail)) {
                message = err.detail
                    .map(d => d.msg || JSON.stringify(d))
                    .join('; ');
            } else if (typeof err.detail === 'string') {
                message = err.detail;
            } else {
                message = `HTTP ${response.status}`;
            }
            throw new Error(message);
        }

        if (options.raw) return response;

        if (response.status === 204) return null;
        const data = await response.json();

        if (options.includeMeta) {
            const total = Number(response.headers.get('x-total-count') ?? (Array.isArray(data) ? data.length : 0));
            return { items: data, total };
        }
        return data;
    } catch (error) {
        throw error;
    }
}

export const api = {
    get:       (url, opts)       => request(url, { ...opts, method: 'GET' }),
    post:      (url, body, opts) => request(url, { ...opts, method: 'POST',   body: JSON.stringify(body) }),
    put:       (url, body, opts) => request(url, { ...opts, method: 'PUT',    body: JSON.stringify(body) }),
    patch:     (url, body, opts) => request(url, { ...opts, method: 'PATCH',  body: JSON.stringify(body) }),
    delete:    (url, opts)       => request(url, { ...opts, method: 'DELETE' }),

    getPaginated: (url)          => request(url, { method: 'GET', includeMeta: true }),
    authCheck: ()                => request('/auth/me', { method: 'GET' }),
};

export const auth = {
    login:    (data) => api.post('/auth/login', data),
    logout:   ()     => api.post('/auth/logout'),
    refresh:  ()     => api.post('/auth/refresh'),
    me:       ()     => api.get('/auth/me'),
};

export const assets = {
    getAll:          ()          => api.get('/assets'),
    getById:         (id)        => api.get(`/assets/${id}`),
    create:          (data)      => api.post('/assets', data),
    patch:           (id, data)  => api.patch(`/assets/${id}`, data),
    delete:          (id)        => api.delete(`/assets/${id}`),
};

export const users = {
    getAll:          ()          => api.get('/users'),
    options:         ()          => api.get('/users/options'),
    getById:         (id)        => api.get(`/users/${id}`),
    create:          (data)      => api.post('/users', data),
    update:          (id, data)  => api.put(`/users/${id}`, data),
    delete:          (id)        => api.delete(`/users/${id}`),
    resetPassword:   (id)        => api.post(`/users/${id}/reset-password`, {}),
};

export const tasks = {
    getAll:  (params = '') => api.get(`/tasks${params}`),
    getById: (id)          => api.get(`/tasks/${id}`),
    create:  (data)        => api.post('/tasks', data),
    update:  (id, data)    => api.put(`/tasks/${id}`, data),
    delete:  (id)          => api.delete(`/tasks/${id}`),
};

export const calendar = {
    getEvents: (start, end) => api.get(`/calendar/events?start=${start}&end=${end}`),
};

export const notes = {
    getAll:          ()         => api.get('/notes/'),
    getById:         (id)       => api.get(`/notes/${id}`),
    create:          (data)     => api.post('/notes/', data),
    update:          (id, data) => api.put(`/notes/${id}`, data),
    delete:          (id)       => api.delete(`/notes/${id}`),
};

export const categories = {
    getAll:  (includeSystem = true) => api.get(`/categories/?include_system=${includeSystem}`),
    getById: (id)                   => api.get(`/categories/${id}`),
    create:  (data)                 => api.post('/categories/', data),
    update:  (id, data)             => api.put(`/categories/${id}`, data),
    delete:  (id)                   => api.delete(`/categories/${id}`),
};
