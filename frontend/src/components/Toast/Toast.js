/**
 * Тосты — неблокирующие всплывающие уведомления (замена alert()).
 *
 * Разметка карточки — в Toast.html (template), здесь только DOM-операции:
 * клонируем шаблон, заполняем textContent, вставляем в контейнер, через
 * таймаут убираем. Иконка — SVG из icons.js (инфраструктурное исключение,
 * как и везде вставляется через innerHTML иконки).
 *
 *   import { toast } from '.../components/Toast/Toast.js';
 *   toast.success('Актив сохранён');
 *   toast.error('Не удалось удалить');
 */
import tpl from './Toast.html?raw';
import { Icons } from '../icons.js';

let _tplHost = null;
let _container = null;

function tplHost() {
  if (_tplHost) return _tplHost;
  _tplHost = document.createElement('div');
  _tplHost.innerHTML = tpl;
  return _tplHost;
}

function container() {
  if (_container && document.body.contains(_container)) return _container;
  _container = document.createElement('div');
  _container.className = 'toast-container';
  document.body.appendChild(_container);
  return _container;
}

const ICON = {
  success: () => Icons.checkCircle(18),
  error:   () => Icons.alert(18),
  info:    () => Icons.bell(18),
};

const DEFAULT_TIMEOUT = 3500;

export function showToast(message, type = 'info', timeout = DEFAULT_TIMEOUT) {
  const node = tplHost().querySelector('#toast-item').content.cloneNode(true);
  const el = node.querySelector('.toast');
  el.classList.add(`toast-${type}`);

  const iconEl = el.querySelector('.toast-icon');
  if (ICON[type]) iconEl.innerHTML = ICON[type]();
  else iconEl.remove();

  el.querySelector('.toast-message').textContent = message;

  container().appendChild(el);
  requestAnimationFrame(() => el.classList.add('is-visible'));

  const dismiss = () => {
    el.classList.remove('is-visible');
    setTimeout(() => el.remove(), 250);
  };
  const timer = setTimeout(dismiss, timeout);
  el.addEventListener('click', () => { clearTimeout(timer); dismiss(); });

  return dismiss;
}

export const toast = {
  success: (m, ms) => showToast(m, 'success', ms),
  error:   (m, ms) => showToast(m, 'error', ms),
  info:    (m, ms) => showToast(m, 'info', ms),
};
