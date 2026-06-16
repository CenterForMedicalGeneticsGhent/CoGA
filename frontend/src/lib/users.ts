import type { ApiUserRef } from './apiTypes';

/**
 * Human-friendly label for a user reference: "First Last" when a name is set,
 * otherwise the username, otherwise the email, otherwise an em dash.
 */
export const formatUserRef = (user?: ApiUserRef | null): string => {
  if (!user) return '—';
  const name = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  return name || user.username || user.email || '—';
};
