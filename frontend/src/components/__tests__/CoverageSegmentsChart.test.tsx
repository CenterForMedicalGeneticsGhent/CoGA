import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CoverageSegmentsChart from '../visualizations/CoverageSegmentsChart';
import { storage } from '../../lib/storage';

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

describe('CoverageSegmentsChart', () => {
  let canvasContext: CanvasRenderingContext2D;

  beforeEach(() => {
    canvasContext = createCanvasContext();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => canvasContext);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not refetch coverage data when only width and layout change', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('segments')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ chr: '1', start: 0, end: 100, value: 0.2 }],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            { chr: '1', start: 0, end: 50, value: 0.1 },
            { chr: '1', start: 50, end: 100, value: -0.1 },
          ],
        }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { rerender } = render(
      <CoverageSegmentsChart
        coverageUrls={['https://example.test/coverage']}
        segmentsUrls={['https://example.test/segments']}
        chroms={['1']}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    rerender(
      <CoverageSegmentsChart
        coverageUrls={['https://example.test/coverage']}
        segmentsUrls={['https://example.test/segments']}
        chroms={['1']}
        width={640}
        height={120}
        layout={{ offsets: { '1': 0 }, lengths: { '1': 100 }, total: 100 }}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it('renders coverage from raw array BED payloads', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => [{ chr: '1', start: 0, end: 100, value: 0.2 }],
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(
      <CoverageSegmentsChart
        coverageUrls={['https://example.test/coverage']}
        chroms={['1']}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(canvasContext.arc).toHaveBeenCalled());
  });

  // Regression: with no stored coverageRange, getCoverageRange() used to return 0,
  // collapsing the y-scale so every coverage point was drawn at a non-finite
  // coordinate (invisible) even though the data loaded correctly.
  it('draws coverage at finite coordinates when coverageRange is unset', async () => {
    storage.clear();
    const ys: number[] = [];
    canvasContext.arc = vi.fn((_x: number, y: number) => {
      ys.push(y);
    }) as unknown as CanvasRenderingContext2D['arc'];

    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ chr: '1', start: 0, end: 100, value: 0.1 }] }),
        }),
      ),
    );

    render(
      <CoverageSegmentsChart
        coverageUrls={['https://example.test/coverage']}
        chroms={['1']}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(ys.length).toBeGreaterThan(0));
    expect(ys.every((y) => Number.isFinite(y))).toBe(true);
  });

  // A missing/empty coverage response must not blank a track that still has
  // segment data to show.
  it('renders segments even when coverage is empty', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('segments')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ chr: '1', start: 0, end: 100, value: 0.2 }] }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ items: [] }) });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <CoverageSegmentsChart
        coverageUrls={['https://example.test/coverage']}
        segmentsUrls={['https://example.test/segments']}
        chroms={['1']}
        regionStart={0}
        regionEnd={100}
        width={320}
        height={120}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    // Segment lines are stroked even though there are no coverage bins.
    await waitFor(() => expect(canvasContext.stroke).toHaveBeenCalled());
  });
});
