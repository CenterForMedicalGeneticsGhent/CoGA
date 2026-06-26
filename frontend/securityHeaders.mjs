// Security response headers for the SPA shell (served by server.mjs). Applied to the
// HTML/static responses only — the /api proxy forwards the backend's own headers.
//
// The CSP is enforcing, widened only where the app genuinely needs it:
//   - 'wasm-unsafe-eval'      IGV compiles WebAssembly (e.g. CRAM decoding)
//   - img-src/worker-src blob: IGV/canvas render via blob URLs and web workers
//   - connect-src https:       presigned-S3 host (config-driven) + remote IGV tracks
//   - Google Fonts            style/font from fonts.googleapis.com / fonts.gstatic.com
//   - frame-ancestors 'none'   blocks clickjacking (no view is meant to be embedded)
// If an unforeseen origin is blocked in staging, switch the header name to
// `Content-Security-Policy-Report-Only` to observe before enforcing.
export const CSP = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob:",
  "connect-src 'self' https:",
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

/**
 * Express middleware that sets the SPA security headers. HSTS is read at call time
 * (opt-in via ENABLE_HSTS) so it is only emitted behind a TLS-terminating proxy.
 */
export function securityHeaders(_req, res, next) {
  res.setHeader('Content-Security-Policy', CSP);
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  if (process.env.ENABLE_HSTS === 'true') {
    res.setHeader('Strict-Transport-Security', 'max-age=63072000; includeSubDomains');
  }
  next();
}
