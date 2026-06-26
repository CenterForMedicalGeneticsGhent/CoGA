import { describe, expect, it, vi } from 'vitest';

import { CSP, securityHeaders } from '../../securityHeaders.mjs';

function mockRes() {
  const headers: Record<string, string> = {};
  return {
    headers,
    setHeader(name: string, value: string) {
      headers[name] = value;
    },
  };
}

describe('SPA securityHeaders middleware', () => {
  it('sets the hardening headers and an IGV/S3-aware enforcing CSP', () => {
    const res = mockRes();
    const next = vi.fn();

    securityHeaders({}, res, next);

    expect(res.headers['X-Content-Type-Options']).toBe('nosniff');
    expect(res.headers['X-Frame-Options']).toBe('DENY');
    expect(res.headers['Referrer-Policy']).toBe('no-referrer');
    expect(res.headers['Cross-Origin-Opener-Policy']).toBe('same-origin');
    expect(res.headers['Content-Security-Policy']).toBe(CSP);
    // Enforcing but widened where the app genuinely needs it.
    expect(CSP).toContain("frame-ancestors 'none'"); // clickjacking
    expect(CSP).toContain("'wasm-unsafe-eval'"); // IGV/CRAM WebAssembly
    expect(CSP).toContain('connect-src'); // presigned S3 / remote tracks
    expect(next).toHaveBeenCalledOnce();
  });

  it('omits HSTS by default (never over plain HTTP)', () => {
    const res = mockRes();
    vi.stubEnv('ENABLE_HSTS', '');
    securityHeaders({}, res, () => {});
    expect(res.headers['Strict-Transport-Security']).toBeUndefined();
    vi.unstubAllEnvs();
  });

  it('emits HSTS only when ENABLE_HSTS=true (TLS-terminated opt-in)', () => {
    const res = mockRes();
    vi.stubEnv('ENABLE_HSTS', 'true');
    securityHeaders({}, res, () => {});
    expect(res.headers['Strict-Transport-Security']).toContain('max-age=');
    vi.unstubAllEnvs();
  });
});
