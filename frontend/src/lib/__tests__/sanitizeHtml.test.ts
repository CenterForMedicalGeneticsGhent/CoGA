import { describe, expect, it } from 'vitest';

import { sanitizeHtml } from '../sanitizeHtml';

describe('sanitizeHtml', () => {
  it('returns empty for falsy input', () => {
    expect(sanitizeHtml('')).toBe('');
  });

  it('drops script tags but keeps their text inert', () => {
    const out = sanitizeHtml('<b>Gene</b><script>alert(1)</script>');
    expect(out).toContain('<b>Gene</b>');
    expect(out.toLowerCase()).not.toContain('<script');
    // The text survives, but only as text — never as an executable element.
    expect(out).toContain('alert(1)');
  });

  it('strips image error-handler payloads', () => {
    const out = sanitizeHtml('<img src="x" onerror="alert(1)">hello');
    expect(out.toLowerCase()).not.toContain('<img');
    expect(out.toLowerCase()).not.toContain('onerror');
    expect(out).toContain('hello');
  });

  it('removes javascript: hrefs while keeping the anchor text', () => {
    const out = sanitizeHtml('<a href="javascript:alert(1)">click</a>');
    expect(out.toLowerCase()).not.toContain('javascript');
    expect(out).toContain('>click</a>');
  });

  it('keeps safe hrefs and allowlisted formatting', () => {
    const out = sanitizeHtml(
      '<p>See <a href="https://omim.org/entry/1" title="OMIM">OMIM</a><br><em>note</em></p>',
    );
    expect(out).toContain('href="https://omim.org/entry/1"');
    expect(out).toContain('title="OMIM"');
    expect(out).toContain('<em>note</em>');
    expect(out).toContain('<br');
  });

  it('drops disallowed attributes from allowed tags', () => {
    const out = sanitizeHtml('<p class="x" style="color:red" onclick="x()">t</p>');
    expect(out).not.toContain('class');
    expect(out).not.toContain('style');
    expect(out).not.toContain('onclick');
    expect(out).toContain('>t</p>');
  });

  it('unwraps disallowed wrapper tags but preserves inner allowlisted markup', () => {
    const out = sanitizeHtml('<table><tr><td><b>kept</b></td></tr></table>');
    expect(out.toLowerCase()).not.toContain('<table');
    expect(out.toLowerCase()).not.toContain('<td');
    expect(out).toContain('<b>kept</b>');
  });
});
