import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthGuard } from './components/AuthGuard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoginPage } from './pages/LoginPage';

// Lazy load all authenticated pages
const HomePage = lazy(() => import('./pages/HomePage').then(m => ({ default: m.HomePage })));
const ActionsPage = lazy(() => import('./pages/ActionsPage').then(m => ({ default: m.ActionsPage })));
const StatusPage = lazy(() => import('./pages/StatusPage').then(m => ({ default: m.StatusPage })));
const KnowledgeBasePage = lazy(() => import('./pages/KnowledgeBasePage').then(m => ({ default: m.KnowledgeBasePage })));
const ArticlePage = lazy(() => import('./pages/ArticlePage').then(m => ({ default: m.ArticlePage })));
const ArticleEditorPage = lazy(() => import('./pages/ArticleEditorPage').then(m => ({ default: m.ArticleEditorPage })));
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })));
const ActivityPage = lazy(() => import('./pages/ActivityPage').then(m => ({ default: m.ActivityPage })));

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AuthGuard><Layout /></AuthGuard>}>
        <Route index element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><HomePage /></Suspense></ErrorBoundary>} />
        <Route path="actions" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><ActionsPage /></Suspense></ErrorBoundary>} />
        <Route path="status" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><StatusPage /></Suspense></ErrorBoundary>} />
        <Route path="kb" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><KnowledgeBasePage /></Suspense></ErrorBoundary>} />
        <Route path="kb/new" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticleEditorPage /></Suspense></ErrorBoundary>} />
        <Route path="kb/:id" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticlePage /></Suspense></ErrorBoundary>} />
        <Route path="kb/:id/edit" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><ArticleEditorPage /></Suspense></ErrorBoundary>} />
        <Route path="audit" element={<Navigate to="/activity" replace />} />
        <Route path="admin" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><AdminPage /></Suspense></ErrorBoundary>} />
        <Route path="activity" element={<ErrorBoundary><Suspense fallback={<p className="cb_loading">Loading...</p>}><ActivityPage /></Suspense></ErrorBoundary>} />
        <Route path="*" element={<div className="cb_error-boundary"><h2>Page Not Found</h2><p>The page you requested does not exist.</p><a href="/" className="cb_button">Back to Home</a></div>} />
      </Route>
    </Routes>
  );
}
