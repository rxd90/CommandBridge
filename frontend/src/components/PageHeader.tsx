import { memo } from 'react';

interface PageHeaderProps {
  label?: string;
  title: string;
  subtitle?: string;
}

export const PageHeader = memo(function PageHeader({ label, title, subtitle }: PageHeaderProps) {
  return (
    <header className="cb_page-header">
      {label && <span className="cb_page-header__label">{label}</span>}
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </header>
  );
});
