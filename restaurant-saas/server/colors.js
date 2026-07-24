// Extraction de palette a partir d'une URL de site (seul module qui sort sur
// le reseau). Best-effort : lit le HTML + CSS lies, collecte les couleurs,
// filtre les gris/quasi-blanc/noir et renvoie les teintes dominantes.

// Garde-fou SSRF minimal : bloque les hotes locaux / IP privees.
function isBlockedHost(host) {
  const h = host.toLowerCase();
  return (
    h === 'localhost' || h.endsWith('.local') ||
    /^127\./.test(h) || /^10\./.test(h) || /^192\.168\./.test(h) ||
    /^169\.254\./.test(h) || /^::1$/.test(h) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(h)
  );
}

const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
const toHex = (r, g, b) => '#' + [r, g, b].map((x) => clamp(x).toString(16).padStart(2, '0')).join('');

function pushColor(map, r, g, b, weight = 1) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const lum = (max + min) / 2;
  const sat = max === min ? 0 : (max - min) / (255 - Math.abs(max + min - 255) || 1);
  // On ignore le quasi-blanc, le quasi-noir et les gris peu satures.
  if (lum > 238 || lum < 16) return;
  if (sat < 0.12 && Math.abs(max - min) < 18) return;
  const hex = toHex(r, g, b);
  map.set(hex, (map.get(hex) || 0) + weight);
}

function harvest(text, map) {
  // #rrggbb et #rgb
  for (const m of text.matchAll(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)) {
    let hex = m[1];
    if (hex.length === 3) hex = hex.split('').map((c) => c + c).join('');
    pushColor(map, parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16));
  }
  // rgb()/rgba()
  for (const m of text.matchAll(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/g)) {
    pushColor(map, +m[1], +m[2], +m[3]);
  }
}

export async function extractFromUrl(rawUrl) {
  let url;
  try { url = new URL(rawUrl); } catch { return { error: 'URL invalide' }; }
  if (!/^https?:$/.test(url.protocol)) return { error: 'URL invalide (http/https attendu)' };
  if (isBlockedHost(url.hostname)) return { error: 'Hote non autorise' };

  const map = new Map();
  const fetchText = async (u) => {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 6000);
    try {
      const res = await fetch(u, { signal: ctrl.signal, redirect: 'follow', headers: { 'User-Agent': 'ResaSaaS-Branding/1.0' } });
      if (!res.ok) return '';
      const buf = await res.arrayBuffer();
      return Buffer.from(buf.slice(0, 1_500_000)).toString('utf8'); // cap 1.5 Mo
    } catch { return ''; } finally { clearTimeout(t); }
  };

  const html = await fetchText(url.href);
  if (!html) return { error: 'Page inaccessible' };

  // theme-color -> poids fort (couleur de marque volontaire)
  const theme = html.match(/<meta[^>]+name=["']theme-color["'][^>]+content=["']([^"']+)["']/i);
  if (theme) harvest(theme[1], map);

  harvest(html, map);

  // Quelques CSS lies (meme origine), pour enrichir la palette.
  const links = [...html.matchAll(/<link[^>]+rel=["']stylesheet["'][^>]*>/gi)]
    .map((m) => (m[0].match(/href=["']([^"']+)["']/i) || [])[1])
    .filter(Boolean).slice(0, 3);
  for (const href of links) {
    try {
      const cssUrl = new URL(href, url.href);
      if (isBlockedHost(cssUrl.hostname)) continue;
      harvest(await fetchText(cssUrl.href), map);
    } catch { /* ignore */ }
  }

  const swatches = [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([hex]) => hex);
  if (!swatches.length) return { error: 'Aucune couleur exploitable trouvee' };
  return { swatches };
}
