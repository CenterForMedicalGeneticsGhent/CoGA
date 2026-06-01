import { render, waitFor } from '@testing-library/react';
import { expect, test } from 'vitest';

import Pedigree from '../visualizations/Pedigree';

const baseRows = [
  { fid: 'F1', iid: 'DAD', pid: '0', mid: '0', sex: '1', phen: '1' },
  { fid: 'F1', iid: 'MOM', pid: '0', mid: '0', sex: '2', phen: '1' },
];

const svgWidth = async (container: HTMLElement): Promise<number> => {
  await waitFor(() => expect(container.querySelector('svg')?.getAttribute('width')).toBeTruthy());
  return Number(container.querySelector('svg')?.getAttribute('width'));
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

  const embryoRender = render(<Pedigree rows={embryoRows} members={embryoMembers} />);
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
  await waitFor(() => expect(result.container.querySelector('svg')?.getAttribute('width')).toBeTruthy());

  const positions = [...result.container.querySelectorAll('[data-pedigree-node]')]
    .map((node) => {
      const transform = node.getAttribute('transform') || '';
      const match = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(transform);
      return match ? { x: Number(match[1]), y: Number(match[2]) } : null;
    })
    .filter((position): position is { x: number; y: number } => position !== null);

  for (let i = 0; i < positions.length; i += 1) {
    for (let j = i + 1; j < positions.length; j += 1) {
      const dx = Math.abs(positions[i].x - positions[j].x);
      const dy = Math.abs(positions[i].y - positions[j].y);
      expect(dx >= 24 || dy >= 24).toBe(true);
    }
  }
});
