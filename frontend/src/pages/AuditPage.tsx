import { useEffect, useState, useCallback } from 'react';
import { Search, FileText, ChevronDown } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusTag';
import { listAuditEntries } from '../lib/api';
import type { AuditEntry } from '../types';

const RESULT_COLOUR: Record<string, 'green' | 'orange' | 'red' | 'grey'> = {
  success: 'green',
  requested: 'orange',
  denied: 'red',
  failed: 'red',
};

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Filters
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const loadEntries = useCallback(async (append = false, nextCursor?: string | null) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    const res = await listAuditEntries({
      user: userFilter || undefined,
      action: actionFilter || undefined,
      limit: 50,
      cursor: nextCursor || undefined,
    });

    if (append) {
      setEntries(prev => [...prev, ...res.entries]);
    } else {
      setEntries(res.entries);
    }
    setCursor(res.cursor);
    setLoading(false);
    setLoadingMore(false);
  }, [userFilter, actionFilter]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleSearch = useCallback(() => {
    loadEntries();
  }, [loadEntries]);

  const handleLoadMore = useCallback(() => {
    if (cursor) loadEntries(true, cursor);
  }, [cursor, loadEntries]);

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  };

  return (
    <>
      <PageHeader
        label="Compliance"
        title="Audit Log"
        subtitle="Action execution history across all users. Every action, request, and denial is recorded."
      />

      <div className="cb_kb-toolbar">
        <div className="cb_kb-search">
          <Search />
          <input
            type="text"
            className="cb_input"
            placeholder="Filter by user email..."
            value={userFilter}
            onChange={e => setUserFilter(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <div className="cb_kb-search">
          <FileText />
          <input
            type="text"
            className="cb_input"
            placeholder="Filter by action ID..."
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
        </div>
      </div>

      {loading ? (
        <p className="cb_loading">Loading audit log...</p>
      ) : entries.length === 0 ? (
        <div className="cb_kb-empty">
          <p>No audit entries found{userFilter ? ` for user "${userFilter}"` : ''}{actionFilter ? ` for action "${actionFilter}"` : ''}.</p>
        </div>
      ) : (
        <>
          <div className="cb_admin-table-wrap">
            <table className="cb_admin-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Ticket</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id}>
                    <td className="cb_audit-table__ts">{formatTimestamp(entry.timestamp)}</td>
                    <td>{entry.user}</td>
                    <td><code>{entry.action}</code></td>
                    <td>{entry.target || '—'}</td>
                    <td>{entry.ticket || '—'}</td>
                    <td>
                      <StatusTag colour={RESULT_COLOUR[entry.result] || 'grey'}>
                        {entry.result}
                      </StatusTag>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {cursor && (
            <div className="cb_audit-load-more">
              <button
                className="cb_button cb_button--secondary"
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? 'Loading...' : (<><ChevronDown /> Load more</>)}
              </button>
            </div>
          )}
        </>
      )}

      <p className="cb_footer cb_footer--inline">
        Audit records are immutable and stored in DynamoDB with point-in-time recovery enabled.
      </p>
    </>
  );
}
