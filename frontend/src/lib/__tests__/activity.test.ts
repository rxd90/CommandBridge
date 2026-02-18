import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock config to non-localDev
vi.mock('../../config', () => ({
  config: {
    localDev: false,
    apiBaseUrl: 'https://fake.api',
  },
}));

vi.mock('../auth', () => ({
  getAccessToken: () => 'fake-token',
}));

describe('activity tracker', () => {
  let activity: typeof import('../activity');

  beforeEach(async () => {
    vi.useFakeTimers();
    globalThis.fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.resetModules();
    activity = await import('../activity');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('trackEvent adds event to queue and flush sends them', () => {
    activity.trackEvent('page_view', { path: '/' });
    activity.trackEvent('button_click', { button: 'execute' });
    activity.flush();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('https://fake.api/activity');
    expect(options.method).toBe('POST');
    const body = JSON.parse(options.body);
    expect(body.events).toHaveLength(2);
    expect(body.events[0].event_type).toBe('page_view');
  });

  it('flush does nothing when queue is empty', () => {
    activity.flush();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('trackPageView creates a page_view event', () => {
    activity.trackPageView('/actions', 'Actions');
    activity.flush();

    const body = JSON.parse((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body.events[0].event_type).toBe('page_view');
    expect(body.events[0].data.path).toBe('/actions');
  });

  it('trackClick creates a button_click event', () => {
    activity.trackClick('execute', { action: 'purge-cache' });
    activity.flush();

    const body = JSON.parse((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body.events[0].event_type).toBe('button_click');
    expect(body.events[0].data.button).toBe('execute');
  });

  it('trackSearch creates a search event', () => {
    activity.trackSearch('login', 'kb');
    activity.flush();

    const body = JSON.parse((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body.events[0].event_type).toBe('search');
    expect(body.events[0].data.query).toBe('login');
    expect(body.events[0].data.section).toBe('kb');
  });

  it('auto-flushes when queue reaches MAX_QUEUE_SIZE', () => {
    for (let i = 0; i < 50; i++) {
      activity.trackEvent('page_view', { i });
    }
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it('swallows fetch errors silently', () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network'));
    activity.trackEvent('page_view');
    expect(() => activity.flush()).not.toThrow();
  });

  it('includes Authorization header and keepalive', () => {
    activity.trackEvent('page_view');
    activity.flush();

    const options = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(options.headers.Authorization).toBe('Bearer fake-token');
    expect(options.keepalive).toBe(true);
  });
});
