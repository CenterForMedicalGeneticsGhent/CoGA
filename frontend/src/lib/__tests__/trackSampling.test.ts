import {
  getAdaptiveTrackWindow,
  getTrackBinLimit,
  getTrackSegmentLimit,
  getTrackVariantLimit,
  SMALL_VARIANT_TRACK_RESULT_LIMIT,
  shouldShowSmallVariantDetails,
} from '../trackSampling';

describe('trackSampling', () => {
  it('bounds variant limits to a viewport-scaled range', () => {
    expect(getTrackVariantLimit(100)).toBe(400);
    expect(getTrackVariantLimit(600)).toBe(1200);
    expect(getTrackVariantLimit(4000)).toBe(4000);
  });

  it('bounds bed bin and segment limits', () => {
    expect(getTrackBinLimit(100)).toBe(300);
    expect(getTrackBinLimit(700)).toBe(1400);
    expect(getTrackSegmentLimit(100)).toBe(200);
    expect(getTrackSegmentLimit(700)).toBe(1050);
  });

  it('expands the aggregation window for wide genomic spans', () => {
    expect(getAdaptiveTrackWindow(250_000_000, 1200, 10_000)).toBeGreaterThan(10_000);
    expect(getAdaptiveTrackWindow(100_000, 1200, 10_000)).toBe(10_000);
    expect(getAdaptiveTrackWindow(0, 1200, 10_000)).toBe(10_000);
  });

  it('only enables individual small variants in high-resolution windows', () => {
    expect(shouldShowSmallVariantDetails(5_000_000)).toBe(true);
    expect(shouldShowSmallVariantDetails(5_000_001)).toBe(false);
    expect(shouldShowSmallVariantDetails(0)).toBe(false);
  });

  it('uses a strict small-variant track display threshold', () => {
    expect(SMALL_VARIANT_TRACK_RESULT_LIMIT).toBe(1000);
  });
});
