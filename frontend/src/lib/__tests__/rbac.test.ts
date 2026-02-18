import { describe, it, expect } from 'vitest';
import { getUserRole, getRoleLevel, getRoleLabel } from '../rbac';
import type { User } from '../../types';

function makeUser(groups: string[]): User {
  return { email: 'test@example.com', name: 'Test User', groups };
}

describe('rbac - getUserRole', () => {
  it('returns the first group as the role', () => {
    const user = makeUser(['L2-engineer', 'L1-operator']);
    expect(getUserRole(user)).toBe('L2-engineer');
  });

  it('returns null for a user with no groups', () => {
    const user = makeUser([]);
    expect(getUserRole(user)).toBeNull();
  });

  it('returns null for a null user', () => {
    expect(getUserRole(null)).toBeNull();
  });
});

describe('rbac - getRoleLevel', () => {
  it('returns 1 for L1-operator', () => {
    const user = makeUser(['L1-operator']);
    expect(getRoleLevel(user)).toBe(1);
  });

  it('returns 2 for L2-engineer', () => {
    const user = makeUser(['L2-engineer']);
    expect(getRoleLevel(user)).toBe(2);
  });

  it('returns 3 for L3-admin', () => {
    const user = makeUser(['L3-admin']);
    expect(getRoleLevel(user)).toBe(3);
  });

  it('returns 0 for a null user', () => {
    expect(getRoleLevel(null)).toBe(0);
  });

  it('returns 0 for a user with no groups', () => {
    const user = makeUser([]);
    expect(getRoleLevel(user)).toBe(0);
  });

  it('returns 0 for an unknown role', () => {
    const user = makeUser(['unknown-role']);
    expect(getRoleLevel(user)).toBe(0);
  });

  it('uses only the first group for level determination', () => {
    const user = makeUser(['L1-operator', 'L3-admin']);
    expect(getRoleLevel(user)).toBe(1);
  });
});

describe('rbac - getRoleLabel', () => {
  it('returns "L1 Operator" for L1-operator', () => {
    const user = makeUser(['L1-operator']);
    expect(getRoleLabel(user)).toBe('L1 Operator');
  });

  it('returns "L2 Engineer" for L2-engineer', () => {
    const user = makeUser(['L2-engineer']);
    expect(getRoleLabel(user)).toBe('L2 Engineer');
  });

  it('returns "L3 Admin" for L3-admin', () => {
    const user = makeUser(['L3-admin']);
    expect(getRoleLabel(user)).toBe('L3 Admin');
  });

  it('returns "Unknown" for a null user', () => {
    expect(getRoleLabel(null)).toBe('Unknown');
  });

  it('returns "Unknown" for a user with no groups', () => {
    const user = makeUser([]);
    expect(getRoleLabel(user)).toBe('Unknown');
  });

  it('returns the raw role string for an unrecognized role', () => {
    const user = makeUser(['custom-role']);
    expect(getRoleLabel(user)).toBe('custom-role');
  });
});
