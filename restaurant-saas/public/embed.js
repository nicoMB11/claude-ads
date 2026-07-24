/*
 * Snippet d'integration site web (comme Zenchef / TheFork).
 * A coller sur n'importe quelle page :
 *
 *   <div id="resa-widget"></div>
 *   <script src="https://VOTRE-DOMAINE/embed.js"
 *           data-restaurant="petit-comptoir"
 *           data-target="#resa-widget"></script>
 *
 * Le widget est isole dans une iframe (styles du site non impactes) et
 * s'auto-redimensionne.
 */
(function () {
  var cur = document.currentScript;
  var slug = (cur && cur.getAttribute('data-restaurant')) || 'petit-comptoir';
  var target = (cur && cur.getAttribute('data-target')) || null;
  var origin = cur ? new URL(cur.src).origin : location.origin;

  var mount = target ? document.querySelector(target) : null;
  if (!mount) { mount = document.createElement('div'); (cur && cur.parentNode || document.body).insertBefore(mount, cur); }

  var iframe = document.createElement('iframe');
  iframe.src = origin + '/book.html?r=' + encodeURIComponent(slug);
  iframe.setAttribute('title', 'Reservation en ligne');
  iframe.style.cssText = 'width:100%;border:0;min-height:520px;overflow:hidden;background:transparent';
  iframe.setAttribute('scrolling', 'no');
  mount.appendChild(iframe);
})();
