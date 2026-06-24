import express from 'express';
import path from 'node:path';
import { Readable } from 'node:stream';
import { fileURLToPath } from 'node:url';

import { rewriteProxyLocation } from './proxyLocation.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 3000;
const BACKEND_URL = (process.env.BACKEND_URL || 'http://backend:8000').replace(/\/+$/, '');
const app = express();

const distPath = path.join(__dirname, 'dist');
const hopByHopHeaders = new Set([
  'connection',
  'content-length',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

app.use('/api', async (req, res) => {
  const targetUrl = `${BACKEND_URL}${req.originalUrl}`;
  const headers = new Headers();

  for (const [name, value] of Object.entries(req.headers)) {
    if (!value || hopByHopHeaders.has(name.toLowerCase())) {
      continue;
    }
    if (Array.isArray(value)) {
      value.forEach((entry) => headers.append(name, entry));
    } else {
      headers.set(name, value);
    }
  }

  try {
    const requestInit = {
      method: req.method,
      headers,
      redirect: 'manual',
    };
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      requestInit.body = req;
      requestInit.duplex = 'half';
    }

    const upstream = await fetch(targetUrl, requestInit);
    res.status(upstream.status);
    upstream.headers.forEach((value, name) => {
      if (hopByHopHeaders.has(name.toLowerCase())) {
        return;
      }
      // A redirect Location built from the internal backend host (backend:8000)
      // is unreachable from the browser; rewrite it to a same-origin path so the
      // browser follows the redirect back through this proxy.
      if (name.toLowerCase() === 'location') {
        res.setHeader(name, rewriteProxyLocation(value, BACKEND_URL));
        return;
      }
      res.setHeader(name, value);
    });

    if (!upstream.body) {
      res.end();
      return;
    }
    Readable.fromWeb(upstream.body).pipe(res);
  } catch (error) {
    console.error(`API proxy failed for ${targetUrl}`, error);
    res.status(502).json({
      detail: `Unable to reach backend API at ${BACKEND_URL}.`,
    });
  }
});

// Serve static assets from the Vite build output
app.use(express.static(distPath));

// All other routes should return the main index.html, allowing
// React Router to handle client side navigation. Express 5 uses
// `path-to-regexp@6`, which does not accept "*" string paths. Use
// a regular expression to match any remaining route instead.
app.get(/.*/, (_req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Frontend running on port ${PORT}`);
});
