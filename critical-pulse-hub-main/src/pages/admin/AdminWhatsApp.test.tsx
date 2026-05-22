import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AdminWhatsApp from './AdminWhatsApp';

const apiClientMock = vi.fn();

vi.mock('@/lib/apiClient', () => ({
  apiClient: (...args: unknown[]) => apiClientMock(...args),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={client}>
      <AdminWhatsApp />
    </QueryClientProvider>
  );
}

describe('AdminWhatsApp', () => {
  it('submits API bulk send and shows summary', async () => {
    apiClientMock.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/whatsapp/template') return Promise.resolve({ template: 'Hello users' });
      if (endpoint.startsWith('/admin/users?')) {
        return Promise.resolve({
          items: [{ id: 1, name: 'A', contact_number: '9876543210', subscription: 'X', approve: '1' }],
        });
      }
      if (endpoint === '/admin/misc/batches') return Promise.resolve([]);
      if (endpoint === '/admin/whatsapp/bulk-send') {
        return Promise.resolve({ total: 1, sent: 1, failed: 0, failures: [] });
      }
      return Promise.resolve({});
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/WhatsApp Communication/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByRole('button', { name: /Send via API/i }));

    await waitFor(() => {
      expect(screen.getByText(/Result:/i)).toBeInTheDocument();
      expect(screen.getByText(/1\/1 sent/i)).toBeInTheDocument();
    });
  });
});
