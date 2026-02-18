import { useEffect, useState, useCallback, useRef } from 'react';
import { Search, Users, Activity, ChevronDown, Clock, FileText } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusTag';
import { listActivity, getActiveUsers, listAuditEntries } from '../lib/api';
import { trackSearch, flush as flushActivity } from '../lib/activity';
import { useRbac } from '../hooks/useRbac';
import type { ActivityEvent, ActiveUser, AuditEntry } from '../types';

const EVENT_TYPE_LABELS: Record<string, string> = {
  page_view: 'Page View',
  button_click: 'Button Click',
  action_execute: 'Action Execute',
  action_request: 'Action Request',
  search: 'Search',
  filter_change: 'Filter Change',
  modal_open: 'Modal Open',
  modal_close: 'Modal Close',
  kb_article_view: 'KB Article View',
  admin_action: 'Admin Action',
  logout: 'Logout',
};

const EVENT_COLOURS: Record<string, 'green' | 'orange' | 'blue' | 'grey' | 'red'> = {
  page_view: 'blue',
  button_click: 'grey',
  action_execute: 'green',
  action_request: 'orange',
  search: 'grey',
  filter_change: 'grey',
  modal_open: 'grey',
  modal_close: 'grey',
  kb_article_view: 'blue',
  admin_action: 'orange',
  logout: 'red',
};

const RESULT_COLOUR: Record<string, 'green' | 'orange' | 'red' | 'grey'> = {
  success: 'green',
  requested: 'orange',
  denied: 'red',
  failed: 'red',
};

export function ActivityPage() {
  const { role } = useRbac();

  if (role !== 'L3-admin') {
    return (
      <>
        <PageHeader label="Activity" title="Access Denied" subtitle="L3 admin access required." />
        <p>You do not have permission to view this page.</p>
      </>
    );
  }

  return <ActivityPageContent />;
}

function ActivityPageContent() {
  const [tab, setTab] = useState<'activity' | 'audit'>('activity');

  return (
    <>
      <PageHeader
        label="Administration"
        title="Activity & Audit"
        subtitle="User interaction tracking and action execution history. L3-admin only."
      />

      <div className="cb_tabs">
        <button
          className={`cb_tab${tab === 'activity' ? ' cb_tab--active' : ''}`}
          onClick={() => setTab('activity')}
        >
          <Activity size={16} /> User Activity
        </button>
        <button
          className={`cb_tab${tab === 'audit' ? ' cb_tab--active' : ''}`}
          onClick={() => setTab('audit')}
        >
          <FileText size={16} /> Audit Log
        </button>
      </div>

      {tab === 'activity' ? <ActivityTab /> : <AuditTab />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Activity Tab
// ---------------------------------------------------------------------------
function ActivityTab() {
  const [activeUsers, setActiveUsers] = useState<ActiveUser[]>([]);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Filters
  const [userFilter, setUserFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [dateRange, setDateRange] = useState<'1h' | '24h' | '7d' | '30d'>('24h');

  const getTimeRange = useCallback((range: string) => {
    const now = Date.now();
    const ranges: Record<string, number> = {
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
    };
    return { start: now - (ranges[range] || ranges['24h']), end: now };
  }, []);

  const loadData = useCallback(async (append = false, nextCursor?: string | null) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    try {
      const { start, end } = getTimeRange(dateRange);

      const activityRes = await listActivity({
        user: userFilter || undefined,
        event_type: eventTypeFilter || undefined,
        start,
        end,
        limit: 50,
        cursor: nextCursor || undefined,
      });

      if (append) {
        setEvents(prev => [...prev, ...activityRes.events]);
      } else {
        setEvents(activityRes.events);
      }
      setCursor(activityRes.cursor);

      // Fetch active users separately so a failure doesn't break the timeline
      if (!append) {
        try {
          const activeRes = await getActiveUsers(15);
          setActiveUsers(activeRes.active_users);
        } catch { /* active users is non-critical */ }
      }
    } catch (err) {
      console.error('[Activity] loadData error:', err);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [userFilter, eventTypeFilter, dateRange, getTimeRange]);

  // Initial load: flush pending events first, then fetch
  const initialized = useRef(false);
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      flushActivity();
      const t = setTimeout(() => loadData(), 500);
      return () => clearTimeout(t);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch when filters change (skip initial - handled above)
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    loadData();
  }, [loadData]);

  // Auto-refresh active users every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await getActiveUsers(15);
        setActiveUsers(res.active_users);
      } catch { /* silent */ }
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  const handleApplyFilters = useCallback(() => {
    flushActivity();
    setTimeout(() => loadData(), 300);
  }, [loadData]);

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts);
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  };

  const timeAgo = (ts: number) => {
    const diff = Date.now() - ts;
    if (diff < 60_000) return 'just now';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return `${Math.floor(diff / 86_400_000)}d ago`;
  };

  return (
    <>
      {/* Active Users Section */}
      <section className="cb_admin-section">
        <h2><Users size={20} /> Active Users ({activeUsers.length})</h2>
        {activeUsers.length === 0 ? (
          <p className="cb_kb-empty"><span>No users active in the last 15 minutes.</span></p>
        ) : (
          <div className="cb_admin-table-wrap">
            <table className="cb_admin-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>User</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {activeUsers.map(u => (
                  <tr key={u.user}>
                    <td><StatusTag colour="green">Online</StatusTag></td>
                    <td>{u.user}</td>
                    <td><Clock size={14} /> {timeAgo(u.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Activity Timeline with Filters */}
      <section className="cb_admin-section">
        <h2><Activity size={20} /> Activity Timeline</h2>
        <div className="cb_kb-toolbar">
          <div className="cb_kb-search">
            <Search />
            <input
              type="text"
              className="cb_input"
              placeholder="Filter by user email..."
              value={userFilter}
              onChange={e => setUserFilter(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleApplyFilters()}
            />
          </div>
          <select
            className="cb_input"
            value={eventTypeFilter}
            onChange={e => { setEventTypeFilter(e.target.value); }}
          >
            <option value="">All event types</option>
            {Object.entries(EVENT_TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
          <select
            className="cb_input"
            value={dateRange}
            onChange={e => { setDateRange(e.target.value as typeof dateRange); }}
          >
            <option value="1h">Last hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
          <button className="cb_button cb_button--secondary" onClick={handleApplyFilters}>
            <Search size={16} /> Apply
          </button>
        </div>

        {loading ? (
          <p className="cb_loading">Loading activity...</p>
        ) : events.length === 0 ? (
          <div className="cb_kb-empty">
            <p>No activity events found for the selected filters.</p>
          </div>
        ) : (
          <>
            <div className="cb_admin-table-wrap">
              <table className="cb_admin-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>User</th>
                    <th>Event</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((evt, i) => (
                    <tr key={`${evt.user}-${evt.timestamp}-${i}`}>
                      <td className="cb_audit-table__ts">{formatTimestamp(evt.timestamp)}</td>
                      <td>{evt.user}</td>
                      <td>
                        <StatusTag colour={EVENT_COLOURS[evt.event_type] || 'grey'}>
                          {EVENT_TYPE_LABELS[evt.event_type] || evt.event_type}
                        </StatusTag>
                      </td>
                      <td>
                        {evt.data && Object.keys(evt.data).length > 0 ? (
                          <code>{JSON.stringify(evt.data)}</code>
                        ) : '\u2014'}
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
                  onClick={() => loadData(true, cursor)}
                  disabled={loadingMore}
                >
                  {loadingMore ? 'Loading...' : (<><ChevronDown /> Load more</>)}
                </button>
              </div>
            )}
          </>
        )}
      </section>

      <p className="cb_footer cb_footer--inline">
        Activity records auto-expire after 90 days via DynamoDB TTL.
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
// Audit Tab
// ---------------------------------------------------------------------------
function AuditTab() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Filters
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const [error, setError] = useState<string | null>(null);

  const loadEntries = useCallback(async (append = false, nextCursor?: string | null) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
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
    } catch (err) {
      console.error('[Audit] loadEntries error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load audit entries.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [userFilter, actionFilter]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleSearch = useCallback(() => {
    if (userFilter) trackSearch(userFilter, 'audit_user');
    if (actionFilter) trackSearch(actionFilter, 'audit_action');
    loadEntries();
  }, [loadEntries, userFilter, actionFilter]);

  const handleLoadMore = useCallback(() => {
    if (cursor) loadEntries(true, cursor);
  }, [cursor, loadEntries]);

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  };

  return (
    <>
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

      {error && (
        <div className="cb_warning" role="alert">
          <p>Failed to load audit entries: {error}</p>
        </div>
      )}

      {loading ? (
        <p className="cb_loading">Loading audit log...</p>
      ) : entries.length === 0 && !error ? (
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
                    <td>{entry.target || '\u2014'}</td>
                    <td>{entry.ticket || '\u2014'}</td>
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
