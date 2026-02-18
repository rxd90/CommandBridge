import { config } from '../config';
import { getAccessToken } from './auth';

export type ActivityEventType =
  | 'page_view'
  | 'button_click'
  | 'action_execute'
  | 'action_request'
  | 'search'
  | 'filter_change'
  | 'modal_open'
  | 'modal_close'
  | 'kb_article_view'
  | 'admin_action'
  | 'logout';

interface QueuedEvent {
  event_type: ActivityEventType;
  timestamp: number;
  data?: Record<string, unknown>;
}

let eventQueue: QueuedEvent[] = [];
let flushTimer: ReturnType<typeof setInterval> | null = null;
const FLUSH_INTERVAL_MS = 30_000;
const MAX_QUEUE_SIZE = 50;

export function trackEvent(
  eventType: ActivityEventType,
  data?: Record<string, unknown>,
): void {
  if (config.localDev) return;

  eventQueue.push({
    event_type: eventType,
    timestamp: Date.now(),
    data,
  });

  if (eventQueue.length >= MAX_QUEUE_SIZE) {
    flush();
  }
}

export function trackPageView(path: string, pageName?: string): void {
  trackEvent('page_view', { path, page: pageName });
}

export function trackClick(buttonId: string, context?: Record<string, unknown>): void {
  trackEvent('button_click', { button: buttonId, ...context });
}

export function trackSearch(query: string, section: string): void {
  trackEvent('search', { query, section });
}

export function trackFilterChange(filter: string, value: string, section: string): void {
  trackEvent('filter_change', { filter, value, section });
}

export function flush(): void {
  if (eventQueue.length === 0) return;

  const batch = [...eventQueue];
  eventQueue = [];

  const token = getAccessToken();
  if (!token) return;

  const payload = JSON.stringify({ events: batch });

  fetch(`${config.apiBaseUrl}/activity`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: payload,
    keepalive: true,
  }).catch(() => {
    // Silent - activity tracking must never break the app
  });
}

function onVisibilityChange(): void {
  if (document.visibilityState === 'hidden') flush();
}

export function initActivityTracker(): void {
  if (config.localDev) return;

  stopActivityTracker();
  flushTimer = setInterval(flush, FLUSH_INTERVAL_MS);

  window.addEventListener('visibilitychange', onVisibilityChange);
  window.addEventListener('beforeunload', flush);
}

export function stopActivityTracker(): void {
  flush();
  if (flushTimer) {
    clearInterval(flushTimer);
    flushTimer = null;
  }
  window.removeEventListener('visibilitychange', onVisibilityChange);
  window.removeEventListener('beforeunload', flush);
}
