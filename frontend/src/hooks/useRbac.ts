import { useAuth } from './useAuth';
import { getUserRole, getRoleLevel, getRoleLabel } from '../lib/rbac';

export function useRbac() {
  const { user } = useAuth();

  return {
    role: getUserRole(user),
    level: getRoleLevel(user),
    label: getRoleLabel(user),
  };
}
