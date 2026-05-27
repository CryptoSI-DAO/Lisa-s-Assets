/**
 * Lisa's Assets — Router
 * Simple hash router: #home, #tao, #eth, #hype
 * Pages use .page class (display:none) or #page-home (default visible).
 */
var Router = (() => {
  const pages = ['home', 'tao', 'coming'];

  function init() {
    window.addEventListener('hashchange', route);
    route(); // initial load
  }

  function route() {
    const hash = (window.location.hash || '#home').slice(1);

    // Show/hide sections
    document.getElementById('page-home').setAttribute('aria-hidden', hash !== 'home');
    document.getElementById('page-tao').setAttribute('aria-hidden', hash !== 'tao');

    const coming = document.getElementById('page-coming');
    const isComing = (hash === 'eth' || hash === 'hype');
    coming.style.display = isComing ? '' : 'none';

    // Nav active state
    document.querySelectorAll('.nav-link[data-route]').forEach(l => {
      l.classList.toggle('active', l.getAttribute('data-route') === hash);
    });
  }

  return { init };
})();
