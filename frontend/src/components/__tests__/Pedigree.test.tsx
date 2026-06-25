import { render, waitFor } from '@testing-library/react';
import { expect, test } from 'vitest';

import Pedigree from '../visualizations/Pedigree';

const baseRows = [
  { fid: 'F1', iid: 'DAD', pid: '0', mid: '0', sex: '1', phen: '1' },
  { fid: 'F1', iid: 'MOM', pid: '0', mid: '0', sex: '2', phen: '1' },
];

const svgWidth = async (container: HTMLElement): Promise<number> => {
  await waitFor(() =>
    expect(container.querySelector('svg')?.getAttribute('width')).toBeTruthy()
  );
  return Number(container.querySelector('svg')?.getAttribute('width'));
};

const pedigreePositions = (container: HTMLElement) => {
  const positions = new Map<
    string,
    { x: number; y: number; generation: number }
  >();
  [...container.querySelectorAll('[data-pedigree-node]')].forEach((node) => {
    const sampleId = node.getAttribute('data-pedigree-node');
    const transform = node.getAttribute('transform') || '';
    const match = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(transform);
    if (!sampleId || !match) return;
    positions.set(sampleId, {
      x: Number(match[1]),
      y: Number(match[2]),
      generation: Number(node.getAttribute('data-generation')),
    });
  });
  return positions;
};

test('draws child sibling groups with compact horizontal spacing', async () => {
  const embryoRows = [
    ...baseRows,
    ...Array.from({ length: 8 }, (_, index) => ({
      fid: 'F1',
      iid: `K25014${index}`,
      pid: 'DAD',
      mid: 'MOM',
      sex: '0',
      phen: '0',
    })),
  ];
  const embryoMembers = embryoRows.map((row) => ({
    sample_id: row.iid,
    role: row.iid.startsWith('K') ? 'embryo' : null,
  }));

  const embryoRender = render(
    <Pedigree rows={embryoRows} members={embryoMembers} />
  );
  const compactWidth = await svgWidth(embryoRender.container);
  embryoRender.unmount();

  const childRows = [
    ...baseRows,
    ...Array.from({ length: 8 }, (_, index) => ({
      fid: 'F1',
      iid: `CHILD${index}`,
      pid: 'DAD',
      mid: 'MOM',
      sex: index % 2 === 0 ? '1' : '2',
      phen: '1',
    })),
  ];
  const childRender = render(<Pedigree rows={childRows} />);
  const regularWidth = await svgWidth(childRender.container);

  expect(compactWidth).toBeLessThan(600);
  expect(regularWidth).toBe(compactWidth);
});

test('centers parent couples above wide sibling groups', async () => {
  const rows = [
    ...baseRows,
    ...Array.from({ length: 8 }, (_, index) => ({
      fid: 'F1',
      iid: `CHILD${index}`,
      pid: 'DAD',
      mid: 'MOM',
      sex: index % 2 === 0 ? '1' : '2',
      phen: '1',
    })),
  ];

  const result = render(<Pedigree rows={rows} />);
  await waitFor(() =>
    expect(
      result.container.querySelector('svg')?.getAttribute('width')
    ).toBeTruthy()
  );

  const positions = pedigreePositions(result.container);
  const parentCenter =
    (positions.get('DAD')!.x + positions.get('MOM')!.x) / 2;
  const childXs = Array.from({ length: 8 }, (_, index) =>
    positions.get(`CHILD${index}`)!.x
  );
  const childCenter = (Math.min(...childXs) + Math.max(...childXs)) / 2;

  expect(Math.abs(parentCenter - childCenter)).toBeLessThanOrEqual(2);
});

test('assigns every generation to a chronological horizontal row', async () => {
  const rows = [
    { fid: 'F1', iid: 'GPA', pid: '0', mid: '0', sex: '1', phen: '1' },
    { fid: 'F1', iid: 'GMA', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'F1', iid: 'FATHER', pid: 'GPA', mid: 'GMA', sex: '1', phen: '1' },
    { fid: 'F1', iid: 'MOTHER', pid: '0', mid: '0', sex: '2', phen: '1' },
    {
      fid: 'F1',
      iid: 'PROBAND',
      pid: 'FATHER',
      mid: 'MOTHER',
      sex: '2',
      phen: '2',
    },
    { fid: 'F1', iid: 'PARTNER', pid: '0', mid: '0', sex: '1', phen: '1' },
    {
      fid: 'F1',
      iid: 'EMBRYO',
      pid: 'PARTNER',
      mid: 'PROBAND',
      sex: '0',
      phen: '0',
    },
  ];

  const result = render(<Pedigree rows={rows} />);
  await waitFor(() =>
    expect(
      result.container.querySelector('svg')?.getAttribute('width')
    ).toBeTruthy()
  );

  const svg = result.container.querySelector('svg');
  const positions = pedigreePositions(result.container);

  expect(svg?.getAttribute('data-generation-count')).toBe('4');
  expect(positions.get('GPA')?.generation).toBe(0);
  expect(positions.get('GMA')?.generation).toBe(0);
  expect(positions.get('FATHER')?.generation).toBe(1);
  expect(positions.get('MOTHER')?.generation).toBe(1);
  expect(positions.get('PROBAND')?.generation).toBe(2);
  expect(positions.get('PARTNER')?.generation).toBe(2);
  expect(positions.get('EMBRYO')?.generation).toBe(3);
  expect(positions.get('FATHER')?.y).toBe(positions.get('MOTHER')?.y);
  expect(positions.get('PROBAND')?.y).toBe(positions.get('PARTNER')?.y);
});

test('draws phenotype badges and active HPO highlights', async () => {
  const rows = [
    { fid: 'F1', iid: 'DAD', pid: '0', mid: '0', sex: '1', phen: '1' },
    { fid: 'F1', iid: 'MOM', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'F1', iid: 'CHILD', pid: 'DAD', mid: 'MOM', sex: '2', phen: '2' },
  ];

  const result = render(
    <Pedigree
      rows={rows}
      phenotypeSampleIds={['CHILD']}
      highlightedSampleIds={['CHILD']}
    />
  );
  await waitFor(() =>
    expect(
      result.container.querySelector('svg')?.getAttribute('width')
    ).toBeTruthy()
  );

  expect(result.container.querySelector('[data-phenotype-badge="CHILD"]')).toBeTruthy();
  expect(result.container.querySelector('[data-phenotype-highlight="CHILD"]')).toBeTruthy();
});

test('keeps multiple partnerships adjacent and centers half-sibling branches', async () => {
  const rows = [
    { fid: 'F1', iid: 'DAD', pid: '0', mid: '0', sex: '1', phen: '1' },
    { fid: 'F1', iid: 'MOM1', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'F1', iid: 'MOM2', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'F1', iid: 'CHILD_A', pid: 'DAD', mid: 'MOM1', sex: '1', phen: '1' },
    { fid: 'F1', iid: 'CHILD_B', pid: 'DAD', mid: 'MOM1', sex: '2', phen: '1' },
    { fid: 'F1', iid: 'CHILD_C', pid: 'DAD', mid: 'MOM2', sex: '1', phen: '1' },
  ];

  const result = render(<Pedigree rows={rows} />);
  await waitFor(() =>
    expect(
      result.container.querySelector('svg')?.getAttribute('width')
    ).toBeTruthy()
  );

  const positions = pedigreePositions(result.container);
  const dad = positions.get('DAD')!;
  const mom1 = positions.get('MOM1')!;
  const mom2 = positions.get('MOM2')!;
  const childA = positions.get('CHILD_A')!;
  const childB = positions.get('CHILD_B')!;
  const childC = positions.get('CHILD_C')!;

  expect(Math.abs(dad.x - mom1.x)).toBeLessThanOrEqual(60);
  expect(Math.abs(dad.x - mom2.x)).toBeLessThanOrEqual(60);
  expect(childA.generation).toBe(1);
  expect(childB.generation).toBe(1);
  expect(childC.generation).toBe(1);

  const firstPartnershipCenter = (dad.x + mom1.x) / 2;
  const secondPartnershipCenter = (dad.x + mom2.x) / 2;
  expect(Math.abs(childA.x - firstPartnershipCenter)).toBeLessThan(90);
  expect(Math.abs(childB.x - firstPartnershipCenter)).toBeLessThan(90);
  expect(Math.abs(childC.x - secondPartnershipCenter)).toBeLessThan(90);
});

test('keeps multi-partner complex pedigrees from overlapping nodes', async () => {
  const rows = [
    { fid: 'test2', iid: 'D1', pid: 'D2', mid: 'D3', sex: '1', phen: '2' },
    { fid: 'test2', iid: 'D2', pid: '0', mid: '0', sex: '1', phen: '1' },
    { fid: 'test2', iid: 'D3', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'test2', iid: 'D4', pid: 'D1', mid: 'D6', sex: '0', phen: '1' },
    { fid: 'test2', iid: 'D6', pid: '0', mid: '0', sex: '2', phen: '1' },
    { fid: 'test2', iid: 'D7', pid: 'D2', mid: 'D3', sex: '2', phen: '1' },
    { fid: 'test2', iid: 'D8', pid: 'D2', mid: 'D3', sex: '0', phen: '1' },
    { fid: 'test2', iid: 'D9', pid: 'D10', mid: 'D7', sex: '0', phen: '1' },
    { fid: 'test2', iid: 'D10', pid: '0', mid: '0', sex: '1', phen: '1' },
  ];

  const result = render(<Pedigree rows={rows} />);
  await waitFor(() =>
    expect(
      result.container.querySelector('svg')?.getAttribute('width')
    ).toBeTruthy()
  );

  const positions = [...pedigreePositions(result.container).values()];

  for (let i = 0; i < positions.length; i += 1) {
    for (let j = i + 1; j < positions.length; j += 1) {
      const dx = Math.abs(positions[i].x - positions[j].x);
      const dy = Math.abs(positions[i].y - positions[j].y);
      expect(dx >= 24 || dy >= 24).toBe(true);
    }
  }
});

test('colours each individual symbol by its QC status with a tooltip', async () => {
  const { container } = render(
    <Pedigree
      rows={baseRows}
      qcStatusBySample={{
        DAD: { status: 'fail', label: 'Sex mismatch: recorded male, genotypes female' },
        MOM: { status: 'pass', label: 'Sex female (matches record)' },
      }}
    />
  );
  await svgWidth(container);

  // Father is a square: its own outline turns red on failure.
  const dad = container.querySelector('[data-pedigree-node="DAD"]');
  expect(dad?.getAttribute('data-qc-status')).toBe('fail');
  expect(dad?.querySelector('rect')?.getAttribute('stroke')).toBe('#dc2626');
  expect(dad?.querySelector('title')?.textContent).toMatch(/Sex mismatch/);

  // Mother is a circle: its outline turns green when checks pass.
  const mom = container.querySelector('[data-pedigree-node="MOM"]');
  expect(mom?.getAttribute('data-qc-status')).toBe('pass');
  expect(mom?.querySelector('circle')?.getAttribute('stroke')).toBe('#16a34a');
});
