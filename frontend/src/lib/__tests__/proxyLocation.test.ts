import { describe, expect, it } from 'vitest';

// The proxy helper lives next to server.mjs (outside src) because it is loaded
// by the production Node server, not the Vite bundle.
import { rewriteProxyLocation } from '../../../proxyLocation.mjs';

const BACKEND = 'http://backend:8000';

describe('rewriteProxyLocation', () => {
  it('rewrites an internal-host redirect to a same-origin path', () => {
    // The bug: the backend returns this on `/api/families` (no trailing slash).
    expect(rewriteProxyLocation('http://backend:8000/api/families/', BACKEND)).toBe(
      '/api/families/',
    );
  });

  it('tolerates a trailing slash on the backend URL', () => {
    expect(rewriteProxyLocation('http://backend:8000/api/x', 'http://backend:8000/')).toBe(
      '/api/x',
    );
  });

  it('leaves same-origin / relative Locations untouched', () => {
    expect(rewriteProxyLocation('/api/families/', BACKEND)).toBe('/api/families/');
  });

  it('leaves external redirects (e.g. OAuth) untouched', () => {
    const external = 'https://login.example.com/authorize?x=1';
    expect(rewriteProxyLocation(external, BACKEND)).toBe(external);
  });

  it('passes through missing / non-string values', () => {
    expect(rewriteProxyLocation(undefined, BACKEND)).toBeUndefined();
    expect(rewriteProxyLocation('', BACKEND)).toBe('');
  });
});
