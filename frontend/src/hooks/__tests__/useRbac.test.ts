import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useRbac } from '../useRbac';

// We will override the mock return value per test
const mockUseAuth = vi.fn();

vi.mock('../useAuth', () => ({
  useAuth: (...args: unknown[]) => mockUseAuth(...args),
}));

describe('useRbac hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns role, level, and label for an L1 operator', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'op@test.com', name: 'Operator', groups: ['L1-operator'] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBe('L1-operator');
    expect(result.current.level).toBe(1);
    expect(result.current.label).toBe('L1 Operator');
  });

  it('returns role, level, and label for an L2 engineer', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'eng@test.com', name: 'Engineer', groups: ['L2-engineer'] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBe('L2-engineer');
    expect(result.current.level).toBe(2);
    expect(result.current.label).toBe('L2 Engineer');
  });

  it('returns role, level, and label for an L3 admin', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'admin@test.com', name: 'Admin', groups: ['L3-admin'] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBe('L3-admin');
    expect(result.current.level).toBe(3);
    expect(result.current.label).toBe('L3 Admin');
  });

  it('returns null role and level 0 when user is null', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBeNull();
    expect(result.current.level).toBe(0);
    expect(result.current.label).toBe('Unknown');
  });

  it('returns null role and level 0 when user has no groups', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'nogroup@test.com', name: 'No Group', groups: [] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBeNull();
    expect(result.current.level).toBe(0);
    expect(result.current.label).toBe('Unknown');
  });

  it('returns level 0 and raw role string for unknown role', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'x@test.com', name: 'Mystery', groups: ['mystery-role'] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBe('mystery-role');
    expect(result.current.level).toBe(0);
    expect(result.current.label).toBe('mystery-role');
  });

  it('uses only the first group as the role', () => {
    mockUseAuth.mockReturnValue({
      user: { email: 'multi@test.com', name: 'Multi', groups: ['L1-operator', 'L3-admin'] },
      loading: false,
    });

    const { result } = renderHook(() => useRbac());
    expect(result.current.role).toBe('L1-operator');
    expect(result.current.level).toBe(1);
    expect(result.current.label).toBe('L1 Operator');
  });
});
