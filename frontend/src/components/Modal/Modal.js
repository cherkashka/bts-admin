
import { Icons } from '../icons.js';
import shellHtml from './Modal.html?raw';

let activeModal = null;
let _shellTemplate = null;

function ensureShellTemplate() {
  if (_shellTemplate) return _shellTemplate;
  const host = document.createElement('div');
  host.innerHTML = shellHtml;
  _shellTemplate = host.querySelector('#modal-shell');
  if (!_shellTemplate) throw new Error('Modal shell template missing');
  return _shellTemplate;
}

export function openModal({
  title       = '',
  body        = '',
  size        = 'md',
  submitText  = 'Сохранить',
  cancelText  = 'Отмена',
  showFooter  = true,
  onSubmit    = null,
  onCancel    = null,
  onOpen      = null,
} = {}) {
  if (activeModal) closeModal();

  const fragment = ensureShellTemplate().content.cloneNode(true);
  const overlay  = fragment.querySelector('.modal-overlay');
  const window_  = fragment.querySelector('.modal-window');

  window_.classList.add(`modal-size-${size}`);

  overlay.querySelector('.modal-title').textContent = title;

  overlay.querySelector('.modal-close-btn').innerHTML = Icons.close(20);

  const bodyEl = overlay.querySelector('.modal-body');
  if (body instanceof Node) bodyEl.appendChild(body);
  else bodyEl.innerHTML = body;

  const footEl = overlay.querySelector('.modal-foot');
  if (!showFooter) {
    footEl.remove();
  } else {
    overlay.querySelector('.modal-cancel-btn').textContent = cancelText;
    overlay.querySelector('.modal-submit-label').textContent = submitText;
    overlay.querySelector('.modal-submit-spinner').innerHTML = Icons.clock(14);
  }

  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';

  requestAnimationFrame(() => overlay.classList.add('is-open'));

  const ctl = {
    overlay,
    form:          overlay.querySelector('.modal-form'),
    bodyEl,
    errorEl:       overlay.querySelector('.modal-error'),
    submitBtn:     overlay.querySelector('.modal-submit-btn'),
    submitLabel:   overlay.querySelector('.modal-submit-label'),
    submitSpinner: overlay.querySelector('.modal-submit-spinner'),

    close() { closeModal(); },

    setError(msg) {
      if (!msg) {
        this.errorEl.hidden = true;
        this.errorEl.textContent = '';
        return;
      }
      this.errorEl.hidden = false;
      this.errorEl.textContent = msg;
      this.errorEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    },

    setLoading(loading) {
      if (!this.submitBtn || this._submitHidden) return;
      this.submitBtn.disabled = loading;
      this.submitLabel.hidden = loading;
      this.submitSpinner.hidden = !loading;
    },

    fieldError(name, msg) {
      const el = this.form.elements[name];
      if (!el) return;
      el.classList.add('has-error');
      const group = el.closest('.form-group');
      if (group) {
        let hint = group.querySelector('.field-error');
        if (!hint) {
          hint = document.createElement('small');
          hint.className = 'field-error';
          group.appendChild(hint);
        }
        hint.textContent = msg;
      }
    },

    clearFieldErrors() {
      this.form.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));
      this.form.querySelectorAll('.field-error').forEach(el => el.remove());
    },

    setBody(content) {
      if (content instanceof Node) {
        this.bodyEl.innerHTML = '';
        this.bodyEl.appendChild(content);
      } else {
        this.bodyEl.innerHTML = content;
      }
    },

    hideSubmit() {
      this._submitHidden = true;
      if (this.submitBtn) this.submitBtn.hidden = true;
    },
  };

  activeModal = ctl;

  overlay.querySelector('.modal-close-btn').addEventListener('click', () => {
    if (onCancel) onCancel();
    closeModal();
  });
  const cancelBtn = overlay.querySelector('.modal-cancel-btn');
  if (cancelBtn) cancelBtn.addEventListener('click', () => {
    if (onCancel) onCancel();
    closeModal();
  });

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      if (onCancel) onCancel();
      closeModal();
    }
  });

  const escHandler = (e) => {
    if (e.key === 'Escape') {
      if (onCancel) onCancel();
      closeModal();
    }
  };
  document.addEventListener('keydown', escHandler);
  ctl._escHandler = escHandler;

  if (onSubmit) {
    ctl.form.addEventListener('submit', async (e) => {
      e.preventDefault();
      ctl.clearFieldErrors();
      ctl.setError(null);

      const formData = new FormData(ctl.form);
      const data = {};
      for (const [k, v] of formData.entries()) data[k] = v;

      ctl.setLoading(true);
      try {
        await onSubmit(data, ctl);
      } catch (err) {
        ctl.setError(err.message || 'Ошибка отправки');
      } finally {
        ctl.setLoading(false);
      }
    });
  }

  if (onOpen) setTimeout(() => onOpen(ctl), 0);

  return ctl;
}

export function closeModal() {
  if (!activeModal) return;
  const { overlay, _escHandler } = activeModal;

  document.removeEventListener('keydown', _escHandler);
  overlay.classList.remove('is-open');

  setTimeout(() => {
    overlay.remove();
    document.body.style.overflow = '';
  }, 200);

  activeModal = null;
}

export function getActiveModal() {
  return activeModal;
}

export function validateRequired(data, fields) {
  const errors = {};
  for (const f of fields) {
    if (!data[f] || String(data[f]).trim() === '') {
      errors[f] = 'Поле обязательно';
    }
  }
  return errors;
}

export function validateRegex(data, field, regex, msg) {
  if (data[field] && !regex.test(data[field])) {
    return { [field]: msg };
  }
  return {};
}

export function applyValidationErrors(modal, errors) {
  Object.entries(errors).forEach(([field, msg]) => modal.fieldError(field, msg));
}
