import { memo } from 'react';

interface StatusTagProps {
  colour?: 'grey' | 'green' | 'teal' | 'blue' | 'purple' | 'pink' | 'red' | 'orange' | 'yellow';
  children: React.ReactNode;
}

export const StatusTag = memo(function StatusTag({ colour, children }: StatusTagProps) {
  const cls = colour ? `cb_tag cb_tag--${colour}` : 'cb_tag';
  return <span className={cls}>{children}</span>;
});
