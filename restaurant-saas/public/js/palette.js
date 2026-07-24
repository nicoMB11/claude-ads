// Extraction de couleurs cote navigateur (aucune connexion) :
//  - depuis un logo / une image  -> lecture des pixels (canvas)
//  - depuis un PDF de charte (DA) -> lecture des operateurs couleur du PDF,
//    en decompressant les flux avec DecompressionStream (natif au navigateur).

const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
const toHex = (r, g, b) => '#' + [r, g, b].map((x) => clamp(x).toString(16).padStart(2, '0')).join('');

// Faut-il retenir cette couleur ? (on ecarte blanc/noir/gris peu satures)
function keep(r, g, b) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const lum = (max + min) / 2;
  if (lum > 240 || lum < 14) return false;
  const sat = max === min ? 0 : (max - min) / (255 - Math.abs(max + min - 255) || 1);
  if (sat < 0.12 && max - min < 18) return false;
  return true;
}

function topSwatches(map, n = 8) {
  const sorted = [...map.entries()].sort((a, b) => b[1] - a[1]);
  const out = [];
  for (const [hex] of sorted) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    // evite les quasi-doublons (distance minimale entre teintes retenues)
    if (out.every((h) => {
      const [r2, g2, b2] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
      return Math.abs(r - r2) + Math.abs(g - g2) + Math.abs(b - b2) > 60;
    })) out.push(hex);
    if (out.length >= n) break;
  }
  return out;
}

// -------- Image / logo -------------------------------------------------------
export async function extractFromImage(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((res, rej) => {
      const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = url;
    });
    const scale = Math.min(1, 160 / Math.max(img.width, img.height));
    const w = Math.max(1, Math.round(img.width * scale));
    const h = Math.max(1, Math.round(img.height * scale));
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, w, h);
    const map = new Map();
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] < 128) continue; // pixel transparent
      const r = data[i], g = data[i + 1], b = data[i + 2];
      if (!keep(r, g, b)) continue;
      // quantification : on regroupe par paliers de 24
      const key = toHex(Math.round(r / 24) * 24, Math.round(g / 24) * 24, Math.round(b / 24) * 24);
      map.set(key, (map.get(key) || 0) + 1);
    }
    return topSwatches(map);
  } finally { URL.revokeObjectURL(url); }
}

// -------- PDF (charte graphique) --------------------------------------------
async function inflate(bytes, fmt) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(fmt));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
async function tryInflate(bytes) {
  for (const fmt of ['deflate', 'deflate-raw']) {
    try { return await inflate(bytes, fmt); } catch { /* essaie le format suivant */ }
  }
  return null;
}
function collectColors(text, map) {
  const N = '(\\d*\\.?\\d+)';
  // rg / RG : RGB 0..1
  for (const m of text.matchAll(new RegExp(`${N}\\s+${N}\\s+${N}\\s+(rg|RG)\\b`, 'g'))) {
    const [r, g, b] = [1, 2, 3].map((i) => +m[i]);
    if (r <= 1 && g <= 1 && b <= 1 && keep(r * 255, g * 255, b * 255)) {
      map.set(toHex(r * 255, g * 255, b * 255), (map.get(toHex(r * 255, g * 255, b * 255)) || 0) + 2);
    }
  }
  // k / K : CMYK 0..1
  for (const m of text.matchAll(new RegExp(`${N}\\s+${N}\\s+${N}\\s+${N}\\s+(k|K)\\b`, 'g'))) {
    const [c, mg, y, k] = [1, 2, 3, 4].map((i) => +m[i]);
    if ([c, mg, y, k].every((v) => v <= 1)) {
      const r = 255 * (1 - c) * (1 - k), g = 255 * (1 - mg) * (1 - k), b = 255 * (1 - y) * (1 - k);
      if (keep(r, g, b)) map.set(toHex(r, g, b), (map.get(toHex(r, g, b)) || 0) + 2);
    }
  }
  // #rrggbb eventuels dans le texte
  for (const m of text.matchAll(/#([0-9a-fA-F]{6})\b/g)) {
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
    if (keep(r, g, b)) map.set('#' + m[1].toLowerCase(), (map.get('#' + m[1].toLowerCase()) || 0) + 1);
  }
}
export async function extractFromPdf(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  // vue latin1 pour reperer les mots-cles (index octet == index caractere)
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const map = new Map();

  // Parcourt chaque flux "stream ... endstream"
  let idx = 0;
  while (true) {
    const s = bin.indexOf('stream', idx);
    if (s === -1) break;
    const e = bin.indexOf('endstream', s);
    if (e === -1) break;
    const dict = bin.slice(Math.max(0, s - 400), s);
    let dataStart = s + 6;
    if (bin[dataStart] === '\r') dataStart++;
    if (bin[dataStart] === '\n') dataStart++;
    const slice = bytes.slice(dataStart, e);
    let text = null;
    if (/\/FlateDecode/.test(dict)) {
      const inf = await tryInflate(slice);
      if (inf) { text = ''; for (let i = 0; i < inf.length; i++) text += String.fromCharCode(inf[i]); }
    } else {
      text = bin.slice(dataStart, e);
    }
    if (text) collectColors(text, map);
    idx = e + 9;
    if (map.size > 400) break; // garde-fou
  }
  // couleurs listees directement dans le corps du PDF (non compresse)
  collectColors(bin, map);
  return topSwatches(map);
}
