/**
 * Lisa's Assets — Theme Manager
 * Handles dark/light mode toggle with localStorage persistence.
 */
const Theme = (() => {
  const STORAGE_KEY = 'lisa-theme';
  const DARK = 'dark';
  const LIGHT = 'light';
  const html = document.documentElement;

  function init() {
    const saved = localStorage.getItem(STORAGE_KEY);
    const initial = saved || DARK;
    apply(initial);
  }

  function toggle() {
    const current = html.getAttribute('data-theme') || DARK;
    const next = current === DARK ? LIGHT : DARK;
    apply(next);
    localStorage.setItem(STORAGE_KEY, next);
    return next;
  }

  function apply(theme) {
    html.setAttribute('data-theme', theme);
    const btn = document.querySelector('.theme-toggle');
    if (btn) btn.textContent = theme === LIGHT ? '☀️' : '🌙';
  }

  return { init, toggle, apply };
})();
