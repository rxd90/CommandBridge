import { describe, it, expect, vi } from 'vitest';

// Mock the config module to force localDev: true
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

// Mock the auth module so request() doesn't fail
vi.mock('../auth', () => ({
  getAccessToken: () => 'fake-token',
  getCurrentUser: () => ({
    email: 'test@example.com',
    name: 'Test User',
    groups: ['L2-engineer'],
  }),
}));

import {
  listKBArticles,
  getKBArticle,
  createKBArticle,
  deleteKBArticle,
  executeAction,
  requestAction,
  getKBVersions,
  getKBVersion,
  updateKBArticle,
} from '../api';

describe('KB API — localDev mode', () => {
  describe('listKBArticles', () => {
    it('returns a list of articles', async () => {
      const result = await listKBArticles();
      expect(result.articles).toBeDefined();
      expect(result.articles.length).toBeGreaterThan(0);
      expect(result.cursor).toBeNull();
    });

    it('each article has required fields', async () => {
      const result = await listKBArticles();
      for (const article of result.articles) {
        expect(article).toHaveProperty('id');
        expect(article).toHaveProperty('title');
        expect(article).toHaveProperty('service');
        expect(article).toHaveProperty('tags');
      }
    });

    it('filters articles by search term', async () => {
      const result = await listKBArticles({ search: 'login' });
      expect(result.articles.length).toBe(1);
      expect(result.articles[0].id).toBe('login-failures');
    });

    it('returns empty array when search matches nothing', async () => {
      const result = await listKBArticles({ search: 'nonexistent-xyz' });
      expect(result.articles).toEqual([]);
    });

    it('search is case-insensitive', async () => {
      const result = await listKBArticles({ search: 'MFA' });
      expect(result.articles.length).toBe(2);
      const ids = result.articles.map(a => a.id);
      expect(ids).toContain('mfa-issues');
      expect(ids).toContain('2fa-sms-delivery');
    });

    it('can search by service name', async () => {
      const result = await listKBArticles({ search: 'Document Verification' });
      expect(result.articles.length).toBe(2);
      const ids = result.articles.map(a => a.id);
      expect(ids).toContain('idv-failures');
      expect(ids).toContain('idv-provider-failover');
    });
  });

  describe('getKBArticle', () => {
    it('returns a matching article by id', async () => {
      const result = await getKBArticle('login-failures');
      expect(result.article).toBeDefined();
      expect(result.article.id).toBe('login-failures');
      expect(result.article.title).toBe('Login Failures');
    });

    it('returns article with content populated', async () => {
      const result = await getKBArticle('login-failures');
      expect(result.article.content).toBeDefined();
      expect(typeof result.article.content).toBe('string');
      expect(result.article.content!.length).toBeGreaterThan(0);
    });

    it('falls back to first article for unknown id but preserves requested id', async () => {
      const result = await getKBArticle('unknown-article');
      expect(result.article.id).toBe('unknown-article');
      expect(result.article.content).toBeDefined();
    });
  });

  describe('createKBArticle', () => {
    it('returns a created article with matching fields', async () => {
      const data = {
        title: 'New Test Article',
        service: 'Test Service',
        owner: 'Test Team',
        tags: ['test', 'unit'],
        content: '# Test\n\nTest content',
      };

      const result = await createKBArticle(data);
      expect(result.article).toBeDefined();
      expect(result.article.title).toBe('New Test Article');
      expect(result.article.service).toBe('Test Service');
      expect(result.article.owner).toBe('Test Team');
      expect(result.article.tags).toEqual(['test', 'unit']);
      expect(result.article.content).toBe('# Test\n\nTest content');
    });

    it('generates slug from title', async () => {
      const result = await createKBArticle({
        title: 'My Great Article',
        service: 'svc',
        owner: 'owner',
        tags: [],
        content: 'body',
      });
      expect(result.article.slug).toBe('my-great-article');
      expect(result.article.id).toBe('my-great-article');
    });

    it('sets version to 1 for new articles', async () => {
      const result = await createKBArticle({
        title: 'Version Test',
        service: 'svc',
        owner: 'owner',
        tags: [],
        content: 'body',
      });
      expect(result.article.version).toBe(1);
    });

    it('sets created_by to local-dev', async () => {
      const result = await createKBArticle({
        title: 'Creator Test',
        service: 'svc',
        owner: 'owner',
        tags: [],
        content: 'body',
      });
      expect(result.article.created_by).toBe('local-dev');
      expect(result.article.updated_by).toBe('local-dev');
    });
  });

  describe('deleteKBArticle', () => {
    it('returns a success message', async () => {
      const result = await deleteKBArticle('login-failures');
      expect(result.message).toBeDefined();
      expect(result.message).toContain('login-failures');
      expect(result.message).toContain('deleted');
    });

    it('includes the article id in the message', async () => {
      const result = await deleteKBArticle('custom-id');
      expect(result.message).toContain('custom-id');
    });
  });

  describe('updateKBArticle', () => {
    it('returns the article for the given id', async () => {
      const result = await updateKBArticle('mfa-issues', { title: 'Updated' });
      expect(result.article).toBeDefined();
      expect(result.article.id).toBe('mfa-issues');
    });
  });

  describe('getKBVersions', () => {
    it('returns a versions array', async () => {
      const result = await getKBVersions('login-failures');
      expect(result.versions).toBeDefined();
      expect(result.versions.length).toBeGreaterThan(0);
      expect(result.versions[0].version).toBe(1);
    });
  });

  describe('getKBVersion', () => {
    it('returns an article response', async () => {
      const result = await getKBVersion('login-failures', 1);
      expect(result.article).toBeDefined();
      expect(result.article.content).toBeDefined();
    });
  });
});

describe('Action API — localDev mode', () => {
  describe('executeAction', () => {
    it('returns a simulated result', async () => {
      const result = await executeAction('restart-pods', 'INC-001', 'test reason');
      expect(result.message).toContain('restart-pods');
      expect(result.message).toContain('INC-001');
      expect(result.status).toBe('simulated');
    });
  });

  describe('requestAction', () => {
    it('returns a pending approval result', async () => {
      const result = await requestAction('scale-up', 'CHG-002', 'need more capacity');
      expect(result.message).toContain('scale-up');
      expect(result.message).toContain('CHG-002');
      expect(result.status).toBe('pending_approval');
    });
  });
});
