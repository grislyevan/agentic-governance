/**
 * Minimal server: serves the built dashboard and GET /api/events from an NDJSON file.
 * Usage:
 *   NDJSON_PATH=../collector/scan-results.ndjson node server.js
 *   node server.js   (uses default path below)
 *
 * For dev with live NDJSON, run this server (port 3001) and the Vite dev server (proxies /api to 3001).
 */

import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 3001;
const NDJSON_PATH = process.env.NDJSON_PATH || path.join(__dirname, '../collector/scan-results.ndjson');

function send(res, status, body, contentType = 'text/plain') {
  res.writeHead(status, { 'Content-Type': contentType });
  res.end(body);
}

function serveFile(filePath, res, contentType) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === 'ENOENT') return send(res, 404, 'Not found');
      return send(res, 500, err.message);
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', `http://localhost:${PORT}`);

  if (url.pathname === '/api/events') {
    const resolved = path.resolve(__dirname, NDJSON_PATH);
    fs.readFile(resolved, 'utf8', (err, data) => {
      if (err) {
        if (err.code === 'ENOENT') return send(res, 404, 'NDJSON file not found. Set NDJSON_PATH or run the collector first.');
        return send(res, 500, err.message);
      }
      send(res, 200, data, 'application/x-ndjson');
    });
    return;
  }

  // Static: serve from dist if present
  const dist = path.join(__dirname, 'dist');
  let file = url.pathname === '/' ? '/index.html' : url.pathname;
  file = path.join(dist, path.normalize(file).replace(/^(\.\.(\/|\\))+/, ''));
  if (!file.startsWith(dist)) {
    send(res, 404, 'Not found');
    return;
  }
  const ext = path.extname(file);
  const types = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.ico': 'image/x-icon',
  };
  serveFile(file, res, types[ext] || 'application/octet-stream');
});

server.listen(PORT, () => {
  console.log(`Dashboard API: http://127.0.0.1:${PORT}`);
  console.log(`NDJSON path: ${path.resolve(__dirname, NDJSON_PATH)}`);
});
