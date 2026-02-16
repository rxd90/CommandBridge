import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from '../../App';

// Mock the useAuth hook to return an authenticated user so AuthGuard allows through
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { email: 'test@example.com', name: 'Test User', groups: ['L2-engineer'] },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    getAccessToken: () => 'fake-token',
  }),
}));

// Mock the auth lib used by api.ts and rbac.ts
vi.mock('../../lib/auth', () => ({
  getAccessToken: () => 'fake-token',
  getCurrentUser: () => ({
    email: 'test@example.com',
    name: 'Test User',
    groups: ['L2-engineer'],
  }),
  login: vi.fn(),
  logout: vi.fn(),
  localDevLogin: vi.fn(),
}));

// Force localDev mode for API stubs
vi.mock('../../config', () => ({
  config: {
    localDev: true,
    apiBaseUrl: 'https://fake.api',
    cognitoRegion: 'eu-west-2',
    cognitoUserPoolId: 'test',
    cognitoClientId: 'test',
    cognitoDomain: 'test',
    redirectUri: 'http://localhost/callback',
    logoutUri: 'http://localhost/login',
  },
}));

// Stub global fetch for any relative URL requests (e.g. /rbac/users.json in LoginPage)
const originalFetch = globalThis.fetch;

beforeAll(() => {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (url.includes('/rbac/users.json')) {
      return Promise.resolve(new Response(JSON.stringify({ users: [] }), { status: 200 }));
    }
    if (url.includes('/rbac/actions.json')) {
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    }
    // Fall through to original for anything else
    return originalFetch(input as RequestInfo);
  }) as typeof globalThis.fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe('App component', () => {
  it('renders without crashing at the root route', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );
    expect(container).toBeTruthy();
  });

  it('renders the login page at /login without errors', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    );
    // The authenticated user mock causes a redirect to /, so we just check it didn't crash
    expect(document.body).toBeTruthy();
  });

  it('renders the layout with navigation for authenticated routes', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );
    const nav = document.querySelector('nav');
    expect(nav).toBeTruthy();
  });

  it('renders navigation links in the layout', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    // Scope assertions to the <nav> element to avoid duplicates from page content
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByText('Home')).toBeInTheDocument();
    expect(within(nav).getByText('Knowledge Base')).toBeInTheDocument();
    expect(within(nav).getByText('Status')).toBeInTheDocument();
    expect(within(nav).getByText('Actions')).toBeInTheDocument();
  });

  it('shows the user name in the navigation', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  it('shows the user role badge', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByText('L2 Engineer')).toBeInTheDocument();
  });
});
