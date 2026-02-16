import { memo } from 'react';

interface StatusLightProps {
  status: 'good' | 'warn' | 'bad';
}

export const StatusLight = memo(function StatusLight({ status }: StatusLightProps) {
  return <span className={`cb_status-light cb_status-light--${status}`} />;
});
