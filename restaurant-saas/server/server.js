// Serveur HTTP minimal (node:http) : API JSON + service des fichiers statiques.
// Zero dependance -> `npm start` suffit.
import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, normalize, extname } from 'node:path';
import { migrate } from './db.js';
import { registerRoutes } from './routes/index.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = join(__dirname, '..', 'public');
const PORT = Number(process.env.PORT || 3000);

migrate();

// --- Mini routeur -----------------------------------------------------------
const routes = []; // { method, regex, keys, handler }
export function route(method, path, handler) {
  const keys = [];
  const regex = new RegExp(
    '^' + path.replace(/:[^/]+/g, (m) => { keys.push(m.slice(1)); return '([^/]+)'; }) + '$'
  );
  routes.push({ method, regex, keys, handler });
}

function send(res, status, body, headers = {}) {
  const payload = typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': typeof body === 'object' && !Buffer.isBuffer(body) ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8',
    'Access-Control-Allow-Origin': '*', // widget embarquable multi-domaines (demo)
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
    ...headers,
  });
  res.end(payload);
}

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.png': 'image/png',
};

async function serveStatic(req, res, urlPath) {
  let rel = decodeURIComponent(urlPath.split('?')[0]);
  if (rel === '/') rel = '/index.html';
  const filePath = normalize(join(PUBLIC_DIR, rel));
  if (!filePath.startsWith(PUBLIC_DIR)) return send(res, 403, 'Forbidden'); // anti path-traversal
  try {
    const s = await stat(filePath);
    if (s.isDirectory()) return send(res, 404, 'Not found');
    const data = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    send(res, 404, 'Not found');
  }
}

function readBody(req) {
  return new Promise((resolve) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
    req.on('end', () => {
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); } catch { resolve({}); }
    });
  });
}

registerRoutes(route);

const server = http.createServer(async (req, res) => {
  const { method } = req;
  const url = req.url;
  if (method === 'OPTIONS') return send(res, 204, '');

  if (url.startsWith('/api/')) {
    const pathname = url.split('?')[0];
    for (const r of routes) {
      if (r.method !== method) continue;
      const m = r.regex.exec(pathname);
      if (!m) continue;
      const params = {};
      r.keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
      const query = Object.fromEntries(new URL(url, 'http://x').searchParams);
      const body = method === 'GET' ? {} : await readBody(req);
      try {
        const result = await r.handler({ params, query, body, req });
        const status = result?.__status || 200;
        if (result && result.__status) delete result.__status;
        return send(res, status, result ?? {});
      } catch (err) {
        console.error(err);
        return send(res, 500, { error: 'server_error', message: String(err.message || err) });
      }
    }
    return send(res, 404, { error: 'not_found' });
  }

  return serveStatic(req, res, url);
});

server.listen(PORT, () => {
  console.log(`\n  Resa SaaS (demo) -> http://localhost:${PORT}`);
  console.log(`  Reservation client : http://localhost:${PORT}/`);
  console.log(`  Admin restaurant   : http://localhost:${PORT}/admin.html`);
  console.log(`  Widget embarquable : http://localhost:${PORT}/embed-demo.html\n`);
});
