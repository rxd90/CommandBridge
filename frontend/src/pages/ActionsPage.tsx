import { useEffect, useState, useCallback } from 'react';
import { Play, Send, Lock, Server, FileText, X, CheckCircle, AlertCircle, Monitor, HardDrive, Shield } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusTag';
import { Modal } from '../components/Modal';
import { getPermissions } from '../lib/rbac';
import { executeAction, requestAction } from '../lib/api';
import type { Action, KBCategory } from '../types';

const RISK_COLOUR = {
  low: 'green',
  medium: 'orange',
  high: 'red',
} as const;

const CATEGORIES: { key: KBCategory; label: string; icon: typeof Monitor; colour: string }[] = [
  { key: 'Frontend', label: 'Frontend', icon: Monitor, colour: 'blue' },
  { key: 'Backend', label: 'Backend', icon: Server, colour: 'purple' },
  { key: 'Infrastructure', label: 'Infrastructure', icon: HardDrive, colour: 'orange' },
  { key: 'Security', label: 'Security', icon: Shield, colour: 'red' },
];

const CATEGORY_COLOUR: Record<string, string> = {
  Frontend: 'blue',
  Backend: 'purple',
  Infrastructure: 'orange',
  Security: 'red',
};

export function ActionsPage() {
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<KBCategory | null>(null);

  // Modal state
  const [modalAction, setModalAction] = useState<Action | null>(null);
  const [isRequest, setIsRequest] = useState(false);
  const [ticket, setTicket] = useState('');
  const [reason, setReason] = useState('');
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    getPermissions().then((data) => {
      setActions(data.actions);
      setLoading(false);
    });
  }, []);

  const openModal = useCallback((action: Action, requestMode: boolean) => {
    setModalAction(action);
    setIsRequest(requestMode);
    setTicket('');
    setReason('');
    setResult(null);
  }, []);

  const handleCategoryClick = useCallback((key: KBCategory) => {
    setActiveCategory(prev => prev === key ? null : key);
  }, []);

  const closeModal = useCallback(() => {
    setModalAction(null);
    setResult(null);
  }, []);

  const handleExecute = useCallback(async () => {
    if (!modalAction) return;
    if (!ticket.trim() || !reason.trim()) {
      setResult({ ok: false, message: 'Ticket and reason are required.' });
      return;
    }

    setExecuting(true);
    try {
      const fn = isRequest ? requestAction : executeAction;
      const res = await fn(modalAction.id, ticket.trim(), reason.trim());
      setResult({ ok: true, message: res.message });
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : 'Action failed.' });
    } finally {
      setExecuting(false);
    }
  }, [modalAction, ticket, reason, isRequest]);

  const filteredActions = activeCategory
    ? actions.filter(a => a.category === activeCategory)
    : actions;

  return (
    <>
      <PageHeader
        label="Operations"
        title="Actions"
        subtitle="Pre-approved operational actions. Permissions are enforced server-side based on your role. Every execution is audited."
      />

      <div className="cb_kb-categories">
        {CATEGORIES.map(({ key, label, icon: Icon, colour }) => (
          <button
            key={key}
            className={`cb_kb-category-chip cb_kb-category-chip--${colour}${activeCategory === key ? ' cb_kb-category-chip--active' : ''}`}
            onClick={() => handleCategoryClick(key)}
          >
            <Icon />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <p className="cb_loading">Loading actions…</p>
      ) : filteredActions.length === 0 ? (
        <div className="cb_kb-empty">
          <p>No actions found{activeCategory ? ` in ${activeCategory}` : ''}.</p>
        </div>
      ) : (
        <div className="cb_actions-list">
          {filteredActions.map((action) => (
            <div key={action.id} className="cb_action-card">
              <div className="cb_action-card__body">
                <h3 className="cb_action-card__title">{action.name}</h3>
                <p className="cb_action-card__desc">{action.description}</p>
                <div className="cb_action-card__meta">
                  <StatusTag colour={RISK_COLOUR[action.risk]}>
                    {action.risk.charAt(0).toUpperCase() + action.risk.slice(1)} risk
                  </StatusTag>
                  {action.category && (
                    <StatusTag colour={CATEGORY_COLOUR[action.category] || 'blue'}>
                      {action.category}
                    </StatusTag>
                  )}
                  <span className="cb_action-card__target"><Server /> {action.target}</span>
                  {action.runbook && (
                    <a href={`/kb/${action.runbook}`} className="cb_action-card__runbook">
                      <FileText /> Runbook
                    </a>
                  )}
                </div>
              </div>

              {action.permission === 'run' && (
                <button
                  className={`cb_button${action.risk === 'high' ? ' cb_button--danger' : ' cb_button--secondary'}`}
                  onClick={() => openModal(action, false)}
                >
                  <Play /> Run
                </button>
              )}
              {action.permission === 'request' && (
                <button
                  className="cb_button cb_button--secondary"
                  onClick={() => openModal(action, true)}
                >
                  <Send /> Request
                </button>
              )}
              {action.permission === 'locked' && (
                <button className="cb_button" disabled><Lock /> Locked</button>
              )}
            </div>
          ))}
        </div>
      )}

      <Modal
        open={!!modalAction}
        onClose={closeModal}
        title={modalAction ? (isRequest ? `Request: ${modalAction.name}` : `Confirm: ${modalAction.name}`) : ''}
      >
        {modalAction && (
          <>
            <p className="cb_modal__desc">
              {modalAction.description}<br />
              <strong>Target:</strong> {modalAction.target} | <strong>Risk:</strong> {modalAction.risk}
            </p>

            <div className="cb_form-group">
              <label className="cb_label" htmlFor="modal-ticket">Incident / Change ticket</label>
              <input
                type="text"
                className="cb_input"
                id="modal-ticket"
                placeholder="INC-2026-0212-001 or CHG-1234"
                value={ticket}
                onChange={(e) => setTicket(e.target.value)}
              />
            </div>

            <div className="cb_form-group">
              <label className="cb_label" htmlFor="modal-reason">Reason</label>
              <textarea
                className="cb_input"
                id="modal-reason"
                rows={3}
                placeholder="Why is this action needed?"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>

            <div className="cb_modal__actions">
              <button
                className="cb_button"
                onClick={handleExecute}
                disabled={executing}
              >
                {executing ? 'Processing…' : isRequest ? (<><Send /> Submit request</>) : (<><Play /> Execute</>)}
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

      <p className="cb_footer cb_footer--inline">
        Actions are enforced server-side via API Gateway + Lambda. Client-side filtering is for display only.
      </p>
    </>
  );
}
