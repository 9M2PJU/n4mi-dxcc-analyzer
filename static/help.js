// Help page (D58): the user guide, rendered by the server from User_Guide.md.
// This script only draws the header and highlights the contents entry for the
// section being read.
'use strict';

renderChrome({
  title: 'User guide',
  subtitle: 'How to use the analyzer · the same guide as User_Guide.md on GitHub',
  actions: '<button class="btn" type="button" onclick="window.print()">Print</button>',
});

(function highlightContents() {
  const links = [...document.querySelectorAll('.toc a')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const byId = new Map(links.map((a) => [decodeURIComponent(a.hash.slice(1)), a]));
  const mark = (a) => { links.forEach((l) => l.removeAttribute('aria-current')); a.setAttribute('aria-current', 'true'); };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting && byId.has(e.target.id)) mark(byId.get(e.target.id)); });
  }, { rootMargin: '0px 0px -75% 0px' });
  document.querySelectorAll('article.doc h2[id], article.doc h3[id]').forEach((h) => io.observe(h));
})();
