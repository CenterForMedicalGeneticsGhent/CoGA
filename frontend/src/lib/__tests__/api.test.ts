import { describe, expect, it } from 'vitest';

import { hasAuthorizationHeader, normalizeApiTransportError, shouldAttachStoredToken } from '../api';

describe('api auth header handling', () => {
  it('detects authorization headers regardless of casing', () => {
    expect(hasAuthorizationHeader({ Authorization: 'Bearer fresh-token' })).toBe(true);
    expect(hasAuthorizationHeader({ authorization: 'Bearer fresh-token' })).toBe(true);
    expect(hasAuthorizationHeader({ 'X-Test': 'value' })).toBe(false);
  });

  it('does not attach stored tokens to auth endpoints', () => {
    expect(shouldAttachStoredToken('/auth/login')).toBe(false);
    expect(shouldAttachStoredToken('/auth/signup')).toBe(false);
  });

  it('does not override an explicit authorization header', () => {
    expect(
      shouldAttachStoredToken('/auth/me', {
        Authorization: 'Bearer fresh-token',
      })
    ).toBe(false);
  });

  it('still attaches the stored token to normal API requests without headers', () => {
    expect(shouldAttachStoredToken('/families/F1')).toBe(true);
  });

  it('normalizes raw transport errors before callers inspect the message', () => {
    const error = Object.assign(new Error('Network Error'), { request: {} });

    normalizeApiTransportError(error, '/api');

    expect(error.message).toBe(
      'Unable to reach the API at /api. Check that the backend, Postgres, and ClickHouse services are running.'
    );
  });
});
