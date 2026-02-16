import { useEffect, useState, useCallback } from 'react';
import { Shield, Search, UserCheck, UserX, CheckCircle, AlertCircle, X } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusTag';
import { Modal } from '../components/Modal';
import { listAdminUsers, disableAdminUser, enableAdminUser, setAdminUserRole } from '../lib/api';
import { useRbac } from '../hooks/useRbac';
import type { AdminUser } from '../types';

const ROLES = ['L1-operator', 'L2-engineer', 'L3-admin'] as const;

const ROLE_COLOUR: Record<string, 'green' | 'orange' | 'blue' | 'grey'> = {
  'L1-operator': 'green',
  'L2-engineer': 'orange',
  'L3-admin': 'blue',
};

type RbacAction = {
  id: string;
  name: string;
  risk: string;
  permissions: Record<string, string | Record<string, boolean>>;
};

function resolvePermission(perms: string | Record<string, boolean> | undefined): 'run' | 'request' | 'locked' {
  if (!perms) return 'locked';
  if (perms === '*') return 'run';
  if (typeof perms === 'object') {
    if (perms.run) return 'run';
    if (perms.request) return 'request';
  }
  return 'locked';
}

const PERM_COLOUR: Record<string, 'green' | 'orange' | 'grey'> = {
  run: 'green',
  request: 'orange',
  locked: 'grey',
};

export function AdminPage() {
  const { role } = useRbac();

  if (role !== 'L3-admin') {
    return (
      <>
        <PageHeader label="Administration" title="Access Denied" subtitle="L3 admin access required." />
        <p>You do not have permission to view this page.</p>
      </>
    );
  }

  return <AdminPageContent />;
}

function AdminPageContent() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [actions, setActions] = useState<RbacAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Modal state
  const [modalUser, setModalUser] = useState<AdminUser | null>(null);
  const [modalAction, setModalAction] = useState<'disable' | 'enable' | 'role' | null>(null);
  const [selectedRole, setSelectedRole] = useState('');
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [executing, setExecuting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    const [usersRes, actionsRes] = await Promise.all([
      listAdminUsers(),
      fetch('/rbac/actions.json').then(r => r.json()),
    ]);
    setUsers(usersRes.users);
    const actionList: RbacAction[] = Object.entries(actionsRes).map(([id, a]) => {
      const action = a as Record<string, unknown>;
      return {
        id,
        name: action.name as string,
        risk: action.risk as string,
        permissions: action.permissions as Record<string, string | Record<string, boolean>>,
      };
    });
    setActions(actionList);
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const openModal = useCallback((user: AdminUser, action: 'disable' | 'enable' | 'role') => {
    setModalUser(user);
    setModalAction(action);
    setSelectedRole(user.role);
    setResult(null);
  }, []);

  const closeModal = useCallback(() => {
    setModalUser(null);
    setModalAction(null);
    setResult(null);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!modalUser || !modalAction) return;
    setExecuting(true);
    try {
      let res: { message: string };
      if (modalAction === 'disable') {
        res = await disableAdminUser(modalUser.email);
      } else if (modalAction === 'enable') {
        res = await enableAdminUser(modalUser.email);
      } else {
        res = await setAdminUserRole(modalUser.email, selectedRole);
      }
      setResult({ ok: true, message: res.message });
      // Refresh user list
      const updated = await listAdminUsers();
      setUsers(updated.users);
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : 'Action failed.' });
    } finally {
      setExecuting(false);
    }
  }, [modalUser, modalAction, selectedRole]);

  const filteredUsers = users.filter(u => {
    if (!search) return true;
    const q = search.toLowerCase();
    return u.name.toLowerCase().includes(q)
      || u.email.toLowerCase().includes(q)
      || u.role.toLowerCase().includes(q)
      || u.team.toLowerCase().includes(q);
  });

  const modalTitle = modalAction === 'disable' ? `Disable: ${modalUser?.name}`
    : modalAction === 'enable' ? `Enable: ${modalUser?.name}`
    : `Change Role: ${modalUser?.name}`;

  return (
    <>
      <PageHeader
        label="Administration"
        title="Admin Panel"
        subtitle="Manage users, roles, and view the RBAC permission matrix. L3-admin only."
      />

      {/* ── User Management ──────────────────────────── */}
      <section className="cb_admin-section">
        <h2><Shield /> User Management</h2>

        <div className="cb_kb-toolbar">
          <div className="cb_kb-search">
            <Search />
            <input
              type="text"
              className="cb_input"
              placeholder="Search users by name, email, role, or team..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <p className="cb_loading">Loading users...</p>
        ) : (
          <div className="cb_admin-table-wrap">
            <table className="cb_admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Team</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map(user => (
                  <tr key={user.email} className={!user.active ? 'cb_admin-table__row--disabled' : ''}>
                    <td>{user.name}</td>
                    <td>{user.email}</td>
                    <td>
                      <StatusTag colour={ROLE_COLOUR[user.role] || 'grey'}>
                        {user.role}
                      </StatusTag>
                    </td>
                    <td>{user.team}</td>
                    <td>
                      <StatusTag colour={user.active ? 'green' : 'red'}>
                        {user.active ? 'Active' : 'Disabled'}
                      </StatusTag>
                    </td>
                    <td className="cb_admin-table__actions">
                      {user.active ? (
                        <button
                          className="cb_button cb_button--small cb_button--danger"
                          onClick={() => openModal(user, 'disable')}
                        >
                          <UserX /> Disable
                        </button>
                      ) : (
                        <button
                          className="cb_button cb_button--small cb_button--secondary"
                          onClick={() => openModal(user, 'enable')}
                        >
                          <UserCheck /> Enable
                        </button>
                      )}
                      <button
                        className="cb_button cb_button--small cb_button--secondary"
                        onClick={() => openModal(user, 'role')}
                      >
                        Change Role
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── RBAC Permission Matrix ───────────────────── */}
      <section className="cb_admin-section">
        <h2><Shield /> RBAC Permission Matrix</h2>
        <p className="cb_admin-section__desc">
          Read-only view of the permission matrix from <code>actions.json</code>. Actions (rows) vs roles (columns).
        </p>

        {actions.length > 0 && (
          <div className="cb_admin-table-wrap">
            <table className="cb_rbac-matrix">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Risk</th>
                  {ROLES.map(r => <th key={r}>{r}</th>)}
                </tr>
              </thead>
              <tbody>
                {actions.map(action => (
                  <tr key={action.id}>
                    <td className="cb_rbac-matrix__action">{action.name}</td>
                    <td>
                      <StatusTag colour={action.risk === 'high' ? 'red' : action.risk === 'medium' ? 'orange' : 'green'}>
                        {action.risk}
                      </StatusTag>
                    </td>
                    {ROLES.map(role => {
                      const perm = resolvePermission(action.permissions[role]);
                      return (
                        <td key={role}>
                          <StatusTag colour={PERM_COLOUR[perm]}>
                            {perm === 'run' ? 'Run' : perm === 'request' ? 'Request' : 'Locked'}
                          </StatusTag>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Confirmation Modal ────────────────────────── */}
      <Modal open={!!modalUser && !!modalAction} onClose={closeModal} title={modalTitle}>
        {modalUser && modalAction && (
          <>
            {modalAction === 'role' ? (
              <div className="cb_form-group">
                <label className="cb_label" htmlFor="admin-role-select">New role for {modalUser.name}</label>
                <select
                  id="admin-role-select"
                  className="cb_input cb_admin-role-select"
                  value={selectedRole}
                  onChange={e => setSelectedRole(e.target.value)}
                >
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            ) : (
              <p className="cb_modal__desc">
                {modalAction === 'disable'
                  ? `Are you sure you want to disable ${modalUser.name} (${modalUser.email})? They will lose access to CommandBridge.`
                  : `Re-enable ${modalUser.name} (${modalUser.email})? They will regain access with their current role.`}
              </p>
            )}

            <div className="cb_modal__actions">
              <button
                className={`cb_button${modalAction === 'disable' ? ' cb_button--danger' : ''}`}
                onClick={handleConfirm}
                disabled={executing}
              >
                {executing ? 'Processing...' : 'Confirm'}
              </button>
              <button className="cb_button cb_button--secondary" onClick={closeModal}><X /> Cancel</button>
            </div>

            {result && (
              <div className="cb_modal__result">
                {result.ok ? (
                  <div className="cb_confirmation" aria-live="polite">
                    <CheckCircle />
                    <p className="cb_confirmation__title">{result.message}</p>
                  </div>
                ) : (
                  <div className="cb_warning">
                    <AlertCircle />
                    <p>{result.message}</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Modal>
    </>
  );
}
