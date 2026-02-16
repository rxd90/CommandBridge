import { memo } from 'react';
import { Terminal } from 'lucide-react';

export const SiteHeader = memo(function SiteHeader() {
  return (
    <div className="cb_site-header">
      <div className="cb_site-header__inner">
        <span className="cb_site-header__logo"><Terminal size={28} /></span>
        <h2 className="cb_site-header__title">CommandBridge</h2>
        <span className="cb_site-header__subtitle">Digital Identity Ops</span>
      </div>
    </div>
  );
});
