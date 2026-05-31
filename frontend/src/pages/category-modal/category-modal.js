
import { categories } from '../../api/client.js';
import { openModal, validateRequired, applyValidationErrors } from '../../components/Modal/Modal.js';
import formTpl from './category-modal.html?raw';

const COLOR_OPTIONS = [
  { label: 'Синий',      value: '#3b82f6' },
  { label: 'Индиго',     value: '#6366f1' },
  { label: 'Зелёный',    value: '#22c55e' },
  { label: 'Жёлтый',     value: '#f59e0b' },
  { label: 'Оранжевый',  value: '#f97316' },
  { label: 'Красный',    value: '#ef4444' },
  { label: 'Розовый',    value: '#ec4899' },
  { label: 'Бирюзовый',  value: '#14b8a6' },
];

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function buildBody(category) {

  const knownColors = new Set(COLOR_OPTIONS.map(c => c.value));
  const selectedColor = category?.color && knownColors.has(category.color)
    ? category.color
    : COLOR_OPTIONS[0].value;

  const tmp = document.createElement('div');
  tmp.innerHTML = formTpl;

  tmp.querySelector('input[name="name"]').value = category?.name || '';

  const colorList = tmp.querySelector('.color-list');
  for (const o of COLOR_OPTIONS) {
    const row = document.createElement('label');
    row.className = 'color-row';

    row.style.setProperty('--swatch', o.value);

    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'color';
    input.value = o.value;
    input.className = 'color-row-input';
    if (selectedColor === o.value) {
      input.checked = true;

      input.setAttribute('checked', '');
      row.classList.add('is-selected');
    }

    const label = document.createElement('span');
    label.className = 'color-row-label';
    label.textContent = o.label;

    row.appendChild(input);
    row.appendChild(label);
    colorList.appendChild(row);
  }

  return tmp;
}

export function openCategoryModal({ category = null, onSaved = null } = {}) {
  const isEdit = !!category;
  const body = buildBody(category);

  openModal({
    title: isEdit ? 'Редактировать категорию' : 'Новая категория',
    body,
    size: 'md',
    submitText: isEdit ? 'Сохранить' : 'Создать',
    onOpen: (ctl) => {

      const colorRows = ctl.bodyEl.querySelectorAll('.color-row');
      colorRows.forEach(row => {
        const input = row.querySelector('.color-row-input');
        input?.addEventListener('change', () => {
          colorRows.forEach(r => r.classList.remove('is-selected'));
          row.classList.add('is-selected');
        });
      });

      ctl.form.querySelectorAll('input, select').forEach(el => {
        el.addEventListener('input',  () => el.classList.remove('has-error'));
        el.addEventListener('change', () => el.classList.remove('has-error'));
      });
    },
    onSubmit: async (data, ctl) => {
      const errors = validateRequired(data, ['name', 'color']);
      if (data.name && data.name.length > 50) errors.name = 'Не более 50 символов';
      if (data.color && !/^#[0-9a-fA-F]{6}$/.test(data.color)) errors.color = 'Неверный hex';

      if (Object.keys(errors).length > 0) {
        applyValidationErrors(ctl, errors);
        ctl.setError('Проверьте корректность полей');
        return;
      }

      const payload = {
        name:  data.name,
        color: data.color,
        icon:  data.icon || null,
      };

      if (isEdit) await categories.update(category.id, payload);
      else        await categories.create(payload);

      ctl.close();
      if (onSaved) onSaved();
    },
  });
}
