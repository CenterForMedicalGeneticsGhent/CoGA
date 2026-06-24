// The API proxy forwards browser requests to the backend over an internal
// hostname (e.g. http://backend:8000). When the backend answers with a redirect
// (a 3xx Location), that Location is built from the host the backend saw — the
// internal one — so passing it through verbatim sends the browser to
// `http://backend:8000/...`, which it cannot resolve ("Unable to reach the API").
//
// Rewriting any Location that points at the internal backend origin into a
// same-origin relative path makes the browser follow the redirect back through
// the proxy, which is resilient to *any* backend redirect (trailing-slash
// normalisation, auth, future routes) rather than a single special case.
export function rewriteProxyLocation(location, backendUrl) {
  if (typeof location !== 'string' || location === '') {
    return location;
  }
  const base = String(backendUrl || '').replace(/\/+$/, '');
  if (base && location.startsWith(base)) {
    const rest = location.slice(base.length);
    return rest.startsWith('/') ? rest : `/${rest}`;
  }
  return location;
}
