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

test('draws PGT embryo sibling groups with compact horizontal spacing', async () => {
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
  expect(compactWidth).toBeLessThan(regularWidth / 2);
});
