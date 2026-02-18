import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit, Trash2, Clock, User, History } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusTag';
import { useRbac } from '../hooks/useRbac';
import { getKBArticle, getKBVersions, getKBVersion, deleteKBArticle } from '../lib/api';
import type { KBArticle, KBVersionSummary } from '../types';

export function ArticlePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { level } = useRbac();
  const [article, setArticle] = useState<KBArticle | null>(null);
  const [versions, setVersions] = useState<KBVersionSummary[]>([]);
  const [showVersions, setShowVersions] = useState(false);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getKBArticle(id)
      .then(res => setArticle(res.article))
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load article'))
      .finally(() => setLoading(false));
  }, [id]);

  const loadVersions = useCallback(async () => {
    if (!id) return;
    setShowVersions(v => !v);
    if (versions.length === 0) {
      try {
        const res = await getKBVersions(id);
        setVersions(res.versions);
      } catch {
        setError('Failed to load version history');
      }
    }
  }, [id, versions.length]);

  const viewVersion = useCallback(async (ver: number) => {
    if (!id) return;
    try {
      const res = await getKBVersion(id, ver);
      setArticle(res.article);
      setViewingVersion(ver);
    } catch {
      setError(`Failed to load version ${ver}`);
    }
  }, [id]);

  const viewLatest = useCallback(async () => {
    if (!id) return;
    try {
      const res = await getKBArticle(id);
      setArticle(res.article);
      setViewingVersion(null);
    } catch {
      setError('Failed to load latest version');
    }
  }, [id]);

  const handleDelete = useCallback(async () => {
    if (!id) return;
    setDeleting(true);
    try {
      await deleteKBArticle(id);
      navigate('/kb');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete article');
      setDeleting(false);
      setConfirmDelete(false);
    }
  }, [id, navigate]);

  if (loading) return <p className="cb_loading">Loading article...</p>;
  if (error) return <p className="cb_text-error">{error}</p>;
  if (!article) return <p className="cb_text-error">Article not found</p>;

  return (
    <>
      <Link to="/kb" className="cb_back-link"><ArrowLeft /> Back to Knowledge Base</Link>

      <PageHeader
        label={article.service || 'Knowledge Base'}
        title={article.title}
      />

      <div className="cb_kb-article-meta">
        {article.owner && (
          <span className="cb_kb-article-meta__item"><User /> {article.owner}</span>
        )}
        {article.updated_at && <span className="cb_kb-article-meta__item"><Clock /> Updated {article.updated_at.slice(0, 10)}</span>}
        <span className="cb_kb-article-meta__item">v{article.version}</span>
        {article.tags && article.tags.length > 0 && (
          <div className="cb_kb-article-meta__tags">
            {article.tags.map(tag => (
              <StatusTag key={tag} colour="purple">{tag}</StatusTag>
            ))}
          </div>
        )}
      </div>

      {viewingVersion !== null && (
        <div className="cb_warning" style={{ marginBottom: 'var(--cb-space-md)' }}>
          <History />
          <p>Viewing version {viewingVersion}. <button className="cb_link-btn" onClick={viewLatest}>View latest</button></p>
        </div>
      )}

      <div className="cb_kb-actions">
        {level >= 2 && (
          <Link to={`/kb/${id}/edit`} className="cb_button cb_button--secondary">
            <Edit /> Edit
          </Link>
        )}
        <button className="cb_button cb_button--secondary" onClick={loadVersions}>
          <History /> {showVersions ? 'Hide' : 'Show'} History
        </button>
        {level >= 3 && (
          confirmDelete ? (
            <div className="cb_kb-delete-confirm">
              <span>Delete this article and all versions?</span>
              <button className="cb_button cb_button--danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
              <button className="cb_button cb_button--secondary" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button className="cb_button cb_button--danger" onClick={() => setConfirmDelete(true)}>
              <Trash2 /> Delete
            </button>
          )
        )}
      </div>

      {showVersions && versions.length > 0 && (
        <div className="cb_kb-versions">
          <h4>Version History</h4>
          <div className="cb_kb-versions__list">
            {versions.map(v => (
              <button
                key={v.version}
                className={`cb_kb-versions__item${viewingVersion === v.version || (viewingVersion === null && v.is_latest === 'true') ? ' cb_kb-versions__item--active' : ''}`}
                onClick={() => v.is_latest === 'true' ? viewLatest() : viewVersion(v.version)}
              >
                <span className="cb_kb-versions__ver">v{v.version}</span>
                <span className="cb_kb-versions__date">{v.updated_at?.slice(0, 10)}</span>
                <span className="cb_kb-versions__author">{v.updated_by}</span>
                {v.is_latest === 'true' && <StatusTag colour="green">latest</StatusTag>}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="cb_kb-content">
        <Markdown remarkPlugins={[remarkGfm]}>{article.content || ''}</Markdown>
      </div>
    </>
  );
}
