import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Eye, Edit, Save } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PageHeader } from '../components/PageHeader';
import { createKBArticle, updateKBArticle, getKBArticle } from '../lib/api';
import { useRbac } from '../hooks/useRbac';
import { KB_CATEGORIES } from '../lib/constants';

export function ArticleEditorPage() {
  const { level } = useRbac();

  if (level < 2) {
    return (
      <>
        <PageHeader label="Knowledge Base" title="Access Denied" subtitle="L2 engineer access or above required." />
        <p>You do not have permission to edit articles.</p>
      </>
    );
  }
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [title, setTitle] = useState('');
  const [service, setService] = useState('');
  const [owner, setOwner] = useState('');
  const [category, setCategory] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(isEdit);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getKBArticle(id)
      .then(res => {
        const a = res.article;
        setTitle(a.title);
        setService(a.service);
        setOwner(a.owner);
        setCategory(a.category || '');
        setTagsInput(a.tags?.join(', ') || '');
        setContent(a.content || '');
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load article'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setSaving(true);
    setError('');

    const tags = tagsInput
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);

    try {
      if (isEdit && id) {
        const res = await updateKBArticle(id, { title, service, owner, tags, content, category });
        navigate(`/kb/${res.article.id}`);
      } else {
        const res = await createKBArticle({ title, service, owner, tags, content, category });
        navigate(`/kb/${res.article.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save article');
      setSaving(false);
    }
  };

  if (loading) return <p className="cb_loading">Loading article...</p>;

  return (
    <>
      <Link to={isEdit ? `/kb/${id}` : '/kb'} className="cb_back-link">
        <ArrowLeft /> {isEdit ? 'Back to article' : 'Back to Knowledge Base'}
      </Link>

      <PageHeader
        label="Knowledge Base"
        title={isEdit ? 'Edit Article' : 'New Article'}
      />

      {error && <p className="cb_text-error" style={{ marginBottom: 'var(--cb-space-md)' }}>{error}</p>}

      <form onSubmit={handleSubmit} className="cb_kb-editor">
        <div className="cb_kb-editor__fields">
          <div className="cb_form-group">
            <label className="cb_label">Title</label>
            <input
              type="text"
              className="cb_input"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Login Failures"
              required
            />
          </div>
          <div className="cb_form-row">
            <div className="cb_form-group">
              <label className="cb_label">Service</label>
              <input
                type="text"
                className="cb_input"
                value={service}
                onChange={e => setService(e.target.value)}
                placeholder="e.g. ScotAccount Auth (OIDC)"
              />
            </div>
            <div className="cb_form-group">
              <label className="cb_label">Owner</label>
              <input
                type="text"
                className="cb_input"
                value={owner}
                onChange={e => setOwner(e.target.value)}
                placeholder="e.g. Identity Platform"
              />
            </div>
          </div>
          <div className="cb_form-row">
            <div className="cb_form-group">
              <label className="cb_label">Category</label>
              <div className="cb_select-wrapper">
                <select
                  className="cb_select"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                >
                  <option value="">Select category...</option>
                  {KB_CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
                <span className="cb_select-arrow" />
              </div>
            </div>
            <div className="cb_form-group">
              <label className="cb_label">Tags (comma-separated)</label>
              <input
                type="text"
                className="cb_input"
                value={tagsInput}
                onChange={e => setTagsInput(e.target.value)}
                placeholder="e.g. login, oidc, auth, scotaccount"
              />
            </div>
          </div>
        </div>

        <div className="cb_kb-editor__content">
          <div className="cb_kb-editor__toolbar">
            <span className="cb_kb-editor__label">Content (Markdown)</span>
            <button
              type="button"
              className="cb_button cb_button--secondary"
              onClick={() => setPreview(p => !p)}
            >
              {preview ? <><Edit /> Edit</> : <><Eye /> Preview</>}
            </button>
          </div>

          {preview ? (
            <div className="cb_kb-content cb_kb-editor__preview">
              <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
            </div>
          ) : (
            <textarea
              className="cb_input cb_kb-editor__textarea"
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Write your article content in markdown..."
              rows={20}
            />
          )}
        </div>

        <div className="cb_kb-editor__actions">
          <button type="submit" className="cb_button" disabled={saving}>
            <Save /> {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Article'}
          </button>
          <Link to={isEdit ? `/kb/${id}` : '/kb'} className="cb_button cb_button--secondary">
            Cancel
          </Link>
        </div>
      </form>
    </>
  );
}
