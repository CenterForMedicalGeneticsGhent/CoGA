import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useGlobalSmallVariantSearchState } from '../globalSmallVariantSearch';

const cursorOf = (queryString: string): string | null =>
  new URLSearchParams(queryString).get('cursor');

describe('useGlobalSmallVariantSearchState keyset pagination', () => {
  it('starts on page 1 with no cursor', () => {
    const { result } = renderHook(() => useGlobalSmallVariantSearchState());
    expect(result.current.pageNumber).toBe(1);
    expect(cursorOf(result.current.requestQueryString)).toBeNull();
    // The legacy offset `page` param must not leak into keyset requests.
    expect(new URLSearchParams(result.current.requestQueryString).has('page')).toBe(false);
  });

  it('walks forward through next cursors and back again', () => {
    const { result } = renderHook(() => useGlobalSmallVariantSearchState());

    act(() => result.current.goToNextPage('C1'));
    expect(result.current.pageNumber).toBe(2);
    expect(cursorOf(result.current.requestQueryString)).toBe('C1');

    act(() => result.current.goToNextPage('C2'));
    expect(result.current.pageNumber).toBe(3);
    expect(cursorOf(result.current.requestQueryString)).toBe('C2');

    act(() => result.current.goToPreviousPage());
    expect(result.current.pageNumber).toBe(2);
    expect(cursorOf(result.current.requestQueryString)).toBe('C1');

    act(() => result.current.goToPreviousPage());
    expect(result.current.pageNumber).toBe(1);
    expect(cursorOf(result.current.requestQueryString)).toBeNull();
  });

  it('never pages before the first page', () => {
    const { result } = renderHook(() => useGlobalSmallVariantSearchState());
    act(() => result.current.goToPreviousPage());
    expect(result.current.pageNumber).toBe(1);
  });

  it('resets to the first page when the sort changes (cursors would be stale)', () => {
    const { result } = renderHook(() => useGlobalSmallVariantSearchState());
    act(() => result.current.goToNextPage('C1'));
    expect(result.current.pageNumber).toBe(2);

    act(() => result.current.setSort('position'));
    expect(result.current.pageNumber).toBe(1);
    expect(cursorOf(result.current.requestQueryString)).toBeNull();
  });
});
