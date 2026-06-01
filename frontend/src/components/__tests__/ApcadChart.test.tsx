import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ApcadChart from '../visualizations/ApcadChart';

const createCanvasContext = (): CanvasRenderingContext2D =>
  ({
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
  }) as unknown as CanvasRenderingContext2D;

describe('ApcadChart', () => {
  let canvasContext: CanvasRenderingContext2D;

  beforeEach(() => {
    canvasContext = createCanvasContext();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => canvasContext);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not refetch APCAD data when only width and layout change', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            { chr: '1', start: 0, end: 50, value: 0.25, origin: 'paternal' },
            { chr: '1', start: 50, end: 100, value: 0.75, origin: 'maternal' },
          ],
        }),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { rerender } = render(
      <ApcadChart
        apcadUrls={['https://example.test/apcad']}
        chroms={['1']}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    rerender(
      <ApcadChart
        apcadUrls={['https://example.test/apcad']}
        chroms={['1']}
        width={640}
        height={120}
        layout={{ offsets: { '1': 0 }, lengths: { '1': 100 }, total: 100 }}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it('fetches PCF segment overlays separately from raw APCAD points', async () => {
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          items: url.endsWith('/pcf')
            ? [{ chr: '1', start: 0, end: 100, value: 0.5, origin: 'maternal' }]
            : [{ chr: '1', start: 0, end: 50, value: 0.25, origin: 'paternal' }],
        }),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(
      <ApcadChart
        apcadUrls={['https://example.test/apcad']}
        pcfUrls={['https://example.test/pcf']}
        chroms={['1']}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(canvasContext.arc).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      'https://example.test/pcf',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
