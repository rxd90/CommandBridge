import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, BookOpen, Clock, User } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { useRbac } from '../hooks/useRbac';
import { listKBArticles } from '../lib/api';
import { CATEGORIES } from '../lib/constants';
import type { KBArticle, KBCategory } from '../types';

export function KnowledgeBasePage() {
  const { level } = useRbac();
  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<KBCategory | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const fetchArticles = useCallback(async (
    searchTerm: string,
    category: KBCategory | null,
    append = false,
    nextCursor?: string,
  ) => {
    try {
      if (append) setLoadingMore(true);
      else setLoading(true);

      const result = await listKBArticles({
        search: searchTerm || undefined,
        category: category || undefined,
        cursor: nextCursor || undefined,
      });

      if (append) {
        setArticles(prev => [...prev, ...result.articles]);
      } else {
        setArticles(result.articles);
      }
      setCursor(result.cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load articles');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchArticles('', null);
  }, [fetchArticles]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchArticles(search, activeCategory);
    }, 300);
    return () => clearTimeout(timeout);
  }, [search, activeCategory, fetchArticles]);

  const handleCategoryClick = (key: KBCategory) => {
    setActiveCategory(prev => prev === key ? null : key);
  };

  return (
    <>
      <PageHeader
        label="Knowledge Base"
        title="Runbooks & Documentation"
        subtitle="Searchable operational runbooks for troubleshooting ScotAccount services. Create, edit, and version articles."
      />

      <div className="cb_kb-toolbar">
        <div className="cb_kb-search">
          <Search />
          <input
            type="text"
            className="cb_input"
            placeholder="Search articles by title, service, tag, or owner..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {level >= 2 && (
          <Link to="/kb/new" className="cb_button">
            <Plus /> New Article
          </Link>
        )}
      </div>

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

      {error && <p className="cb_text-error">{error}</p>}

      {loading ? (
        <p className="cb_loading">Loading articles...</p>
      ) : articles.length === 0 ? (
        <div className="cb_kb-empty">
          <BookOpen />
          <p>No articles found{search ? ` matching "${search}"` : ''}{activeCategory ? ` in ${activeCategory}` : ''}.</p>
        </div>
      ) : (
        <div className="cb_kb-list">
          {articles.map((article, i) => (
            <Link
              to={`/kb/${article.id}`}
              key={article.id}
              className="cb_kb-card"
              style={{ animationDelay: `${i * 0.03}s` }}
            >
              <div className="cb_kb-card__header">
                <h3 className="cb_kb-card__title">{article.title}</h3>
                {article.service && (
                  <span className="cb_tag cb_tag--teal">{article.service}</span>
                )}
              </div>
              <div className="cb_kb-card__meta">
                {article.owner && (
                  <span className="cb_kb-card__meta-item"><User /> {article.owner}</span>
                )}
                <span className="cb_kb-card__meta-item"><Clock /> {article.updated_at?.slice(0, 10)}</span>
              </div>
              {article.tags && article.tags.length > 0 && (
                <div className="cb_kb-card__tags">
                  {article.tags.slice(0, 5).map(tag => (
                    <span key={tag} className="cb_kb-card__tag">{tag}</span>
                  ))}
                  {article.tags.length > 5 && (
                    <span className="cb_kb-card__tag">+{article.tags.length - 5}</span>
                  )}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      {cursor && !loading && (
        <div className="cb_kb-load-more">
          <button
            className="cb_button cb_button--secondary"
            disabled={loadingMore}
            onClick={() => fetchArticles(search, activeCategory, true, cursor)}
          >
            {loadingMore ? 'Loading...' : 'Load more articles'}
          </button>
        </div>
      )}
    </>
  );
}
