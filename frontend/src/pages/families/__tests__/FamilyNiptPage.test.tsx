import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import FamilyNiptPage from '../FamilyNiptPage';
import { createTestQueryClient } from '../../../test/createTestQueryClient';

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../../../lib/api', () => ({
  default: apiMock,
}));

const renderPage = (familyId: string) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/families/${familyId}/nipt`]}>
        <Routes>
          <Route path="/families/:familyId/nipt" element={<FamilyNiptPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('FamilyNiptPage', () => {
  it('shows the NIPT analysis placeholder for a monogenic NIPT family', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'NIPT001',
        members: [],
        metadata: { analysis_type: 'monogenic_nipt' },
      },
    });

    renderPage('NIPT001');

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /monogenic nipt analysis — NIPT001/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/fetal-fraction estimation/i)).toBeInTheDocument();
  });

  it('shows a not-configured message for a non-NIPT family', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM001',
        members: [],
        metadata: {},
      },
    });

    renderPage('FAM001');

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /not a monogenic nipt family/i }),
      ).toBeInTheDocument();
    });
  });
});
