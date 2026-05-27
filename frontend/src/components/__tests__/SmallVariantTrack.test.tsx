import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';

const { apiGetMock, useQueryMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  useQueryMock: vi.fn(),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: useQueryMock,
}));

vi.mock('../../lib/api', () => ({
  default: {
    get: apiGetMock,
  },
}));
import SmallVariantTrack from '../visualizations/SmallVariantTrack';

beforeEach(() => {
  apiGetMock.mockReset();
  useQueryMock.mockReset();
});

test('renders message when no small variants', () => {
  useQueryMock.mockReturnValue({ data: { variants: [] }, isLoading: false });
  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />
  );
  expect(
    screen.getByText(/no small variants for this region \/ sample/i)
  ).toBeInTheDocument();
});

test('renders loader while small variants are loading', () => {
  useQueryMock.mockReturnValue({ data: undefined, isLoading: true });
  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />
  );
  expect(screen.getByText(/loading small variants/i)).toBeInTheDocument();
});

test('does not request broad unfiltered chromosome small variants', () => {
  useQueryMock.mockReturnValue({ data: undefined, isLoading: false });

  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={10_000_000}
      width={100}
      height={20}
    />
  );

  expect(useQueryMock.mock.calls[0][0].enabled).toBe(false);
  expect(useQueryMock.mock.calls[1][0].enabled).toBe(false);
  expect(screen.getByText(/too many variants to display/i)).toBeInTheDocument();
});

test('renders too many message when bounded track count reaches the limit', () => {
  useQueryMock.mockImplementation(({ queryKey }) =>
    queryKey[0] === 'small-variant-track-tags'
      ? { data: [], isLoading: false }
      : {
          data: {
            total: 1000,
            total_is_estimated: true,
            count_limit: 1000,
            variants: [],
          },
          isLoading: false,
        },
  );

  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />,
  );

  expect(screen.getByText(/too many variants to display/i)).toBeInTheDocument();
});

test('requests small variants carried by the displayed sample before pagination', async () => {
  useQueryMock.mockReturnValue({ data: { variants: [] }, isLoading: false });
  apiGetMock.mockResolvedValue({ data: { variants: [] } });

  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />
  );

  await useQueryMock.mock.calls[0][0].queryFn();

  expect(apiGetMock).toHaveBeenCalledWith(
    '/families/F1/small-variants',
    expect.objectContaining({
      params: expect.objectContaining({
        sample_filter: 'S1:0/1|1/0|0|1|1|0|1/1|1|1',
        page_size: 999,
        track_result_limit: 1000,
      }),
    }),
  );
});

test('preserves an explicit small-variant sample filter', async () => {
  useQueryMock.mockReturnValue({ data: { variants: [] }, isLoading: false });
  apiGetMock.mockResolvedValue({ data: { variants: [] } });

  render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
      filters={{ sample_filter: 'S1:1/1', source: 'glimpse2' }}
    />
  );

  await useQueryMock.mock.calls[0][0].queryFn();

  expect(apiGetMock).toHaveBeenCalledWith(
    '/families/F1/small-variants',
    expect.objectContaining({
      params: expect.objectContaining({
        sample_filter: 'S1:1/1',
        source: 'glimpse2',
        page_size: 999,
        track_result_limit: 1000,
      }),
    }),
  );
});

test('colors variants by review tag before ClinVar annotation', async () => {
  useQueryMock.mockImplementation(({ queryKey }) =>
    queryKey[0] === 'small-variant-track-tags'
      ? { data: [{ key: 'priority', color: '#123456' }], isLoading: false }
      : {
          data: {
            total: 2,
            variants: [
              {
                chr: '1',
                start: 10,
                end: 10,
                type: 'SNV',
                clinvar: 'Pathogenic',
                genotypes: [{ sample: 'S1', gt: '0/1' }],
                review: { tags: ['priority'] },
              },
              {
                chr: '1',
                start: 20,
                end: 20,
                type: 'SNV',
                clinvar: 'Pathogenic',
                genotypes: [{ sample: 'S1', gt: '0/1' }],
                review: { tags: [] },
              },
            ],
          },
          isLoading: false,
        },
  );

  const { container } = render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('line')).toHaveLength(2));
  const [tagged, pathogenic] = Array.from(container.querySelectorAll('line'));
  expect(tagged).toHaveAttribute('stroke', '#123456');
  expect(pathogenic).toHaveAttribute('stroke', '#b42318');
});

test('colors ClinVar annotations by pathogenicity category', async () => {
  useQueryMock.mockImplementation(({ queryKey }) =>
    queryKey[0] === 'small-variant-track-tags'
      ? { data: [], isLoading: false }
      : {
          data: {
            total: 3,
            variants: [
              {
                chr: '1',
                start: 10,
                end: 10,
                type: 'SNV',
                clinvar: 'Likely pathogenic',
                genotypes: [{ sample: 'S1', gt: '0/1' }],
              },
              {
                chr: '1',
                start: 20,
                end: 20,
                type: 'SNV',
                clinvar: 'Likely benign',
                genotypes: [{ sample: 'S1', gt: '0/1' }],
              },
              {
                chr: '1',
                start: 30,
                end: 30,
                type: 'SNV',
                clinvar: 'Conflicting interpretations of pathogenicity',
                genotypes: [{ sample: 'S1', gt: '0/1' }],
              },
            ],
          },
          isLoading: false,
        },
  );

  const { container } = render(
    <SmallVariantTrack
      familyId="F1"
      sampleId="S1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('line')).toHaveLength(3));
  const [likelyPathogenic, likelyBenign, conflicting] = Array.from(
    container.querySelectorAll('line'),
  );
  expect(likelyPathogenic).toHaveAttribute('stroke', '#ea580c');
  expect(likelyBenign).toHaveAttribute('stroke', '#2f855a');
  expect(conflicting).toHaveAttribute('stroke', '#ca8a04');
});
