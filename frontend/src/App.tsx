import { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthGuard } from './components/AuthGuard';
import { LoginPage } from './pages/LoginPage';

// Lazy load all authenticated pages
const HomePage = lazy(() => import('./pages/HomePage').then(m => ({ default: m.HomePage })));
const ActionsPage = lazy(() => import('./pages/ActionsPage').then(m => ({ default: m.ActionsPage })));
const StatusPage = lazy(() => import('./pages/StatusPage').then(m => ({ default: m.StatusPage })));
const KnowledgeBasePage = lazy(() => import('./pages/KnowledgeBasePage').then(m => ({ default: m.KnowledgeBasePage })));
const ArticlePage = lazy(() => import('./pages/ArticlePage').then(m => ({ default: m.ArticlePage })));
const ArticleEditorPage = lazy(() => import('./pages/ArticleEditorPage').then(m => ({ default: m.ArticleEditorPage })));
const AuditPage = lazy(() => import('./pages/AuditPage').then(m => ({ default: m.AuditPage })));
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })));

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AuthGuard><Layout /></AuthGuard>}>
        <Route index element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><HomePage /></Suspense>} />
        <Route path="actions" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><ActionsPage /></Suspense>} />
        <Route path="status" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><StatusPage /></Suspense>} />
        <Route path="kb" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><KnowledgeBasePage /></Suspense>} />
        <Route path="kb/new" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticleEditorPage /></Suspense>} />
        <Route path="kb/:id" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticlePage /></Suspense>} />
        <Route path="kb/:id/edit" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticleEditorPage /></Suspense>} />
        <Route path="audit" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><AuditPage /></Suspense>} />
        <Route path="admin" element={<Suspense fallback={<p className="cb_loading">Loading...</p>}><AdminPage /></Suspense>} />
      </Route>
    </Routes>
  );
}
