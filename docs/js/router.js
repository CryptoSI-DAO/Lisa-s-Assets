/**
 * Lisa's Assets — Router
 * Simple hash router: #home, #tao, #eth, #hype
 * Pages use .page class (display:none) or #page-home (default visible).
 */
var Router = (() => {
  const pages = ['home', 'tao', 'eth', 'hype'];

  function init() {
    window.addEventListener('hashchange', route);
    route(); // initial load
  }

  function route() {
    const hash = (window.location.hash || '#home').slice(1);

    // Show/hide sections
    document.getElementById('page-home').setAttribute('aria-hidden', hash !== 'home');
    document.getElementById('page-tao').setAttribute('aria-hidden', hash !== 'tao');
    document.getElementById('page-eth').setAttribute('aria-hidden', hash !== 'eth');
    document.getElementById('page-hype').setAttribute('aria-hidden', hash !== 'hype');

    // Nav active state
    document.querySelectorAll('.nav-link[data-route]').forEach(l => {
      l.classList.toggle('active', l.getAttribute('data-route') === hash);
    });
  }

  function showProject(id) {
    // Scroll to project card within a page
    const el = document.getElementById('card-' + id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return { init, showProject };
})();
