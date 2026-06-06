import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Breadcrumbs from '../Breadcrumbs';

test('preserves variant filters when navigating from chromosome to genome', () => {
  render(
    <MemoryRouter initialEntries={["/families/123/chromosome/1?af=0.5&start=1&end=2"]}>
      <Breadcrumbs />
    </MemoryRouter>
  );

  const link = screen.getByText('CHROMOSOME').closest('a');
  expect(link).toHaveAttribute('href', '/families/123/genome?af=0.5');
});

test('admin breadcrumb links back to admin dashboard', () => {
  render(
    <MemoryRouter initialEntries={["/admin/users"]}>
      <Breadcrumbs />
    </MemoryRouter>
  );

  const adminLink = screen.getByText('ADMIN').closest('a');
  expect(adminLink).toHaveAttribute('href', '/admin');
});

test('admin access intermediate breadcrumb points to admin dashboard', () => {
  render(
    <MemoryRouter initialEntries={["/admin/access/projects"]}>
      <Breadcrumbs />
    </MemoryRouter>
  );

  const accessLink = screen.getByText('ACCESS').closest('a');
  expect(accessLink).toHaveAttribute('href', '/admin');
});

test('admin family structure id breadcrumb links back to families list', () => {
  render(
    <MemoryRouter initialEntries={["/admin/data/families/F1/structure"]}>
      <Breadcrumbs />
    </MemoryRouter>
  );

  const familyIdLink = screen.getByText('F1').closest('a');
  expect(familyIdLink).toHaveAttribute('href', '/admin/data/families');
});
