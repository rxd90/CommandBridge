import { Link } from 'react-router-dom';
import { BookOpen, Activity, Zap } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';

export function HomePage() {
  return (
    <>
      <PageHeader
        label="Ops Console"
        title="CommandBridge"
        subtitle="Internal operations portal for ScotAccount digital identity services. Run pre-approved actions and search runbooks."
      />

      <div className="cb_dashboard-grid">
        <Link to="/kb" className="cb_dashboard-card">
          <div className="cb_dashboard-card__icon"><BookOpen /></div>
          <h3>Knowledge Base</h3>
          <p>Searchable runbooks for troubleshooting auth, MFA, IDV, enrolment, and infrastructure.</p>
          <span className="cb_dashboard-card__meta">Dynamic articles &bull; Full-text search</span>
        </Link>

        <Link to="/status" className="cb_dashboard-card">
          <div className="cb_dashboard-card__icon"><Activity /></div>
          <h3>Status Wall</h3>
          <p>Multi-region service health matrix across networking, compute, data, and security.</p>
          <span className="cb_dashboard-card__meta">6 regions &bull; 24 services</span>
        </Link>

        <Link to="/actions" className="cb_dashboard-card">
          <div className="cb_dashboard-card__icon"><Zap /></div>
          <h3>Actions</h3>
          <p>Pre-approved operational actions with role-based access, risk tagging, and audit trail.</p>
          <span className="cb_dashboard-card__meta">RBAC-enforced &bull; 10 actions</span>
        </Link>
      </div>
    </>
  );
}
