import { useMemo } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StatusLight } from '../components/StatusLight';

type Status = 'good' | 'warn' | 'bad';

interface Service {
  name: string;
  regions: Status[];
}

interface Category {
  name: string;
  services: Service[];
}

const REGIONS = ['eu-west-1', 'eu-west-2', 'eu-central-1', 'us-east-1', 'us-west-2', 'ap-southeast-2'];

const STATUS_DATA: Category[] = [
  {
    name: 'Networking',
    services: [
      { name: 'API Gateway', regions: ['good', 'good', 'warn', 'good', 'good', 'good'] },
      { name: 'ALB Ingress', regions: ['good', 'good', 'good', 'warn', 'good', 'good'] },
      { name: 'NLB (Edge)', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'Route 53', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'WAF', regions: ['good', 'good', 'good', 'good', 'warn', 'good'] },
    ],
  },
  {
    name: 'Compute',
    services: [
      { name: 'EKS Control Plane', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'ECS Workers', regions: ['good', 'good', 'good', 'warn', 'good', 'good'] },
      { name: 'Lambda (Workers)', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
    ],
  },
  {
    name: 'Data',
    services: [
      { name: 'RDS Primary', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'Aurora Replica', regions: ['good', 'good', 'good', 'good', 'warn', 'good'] },
      { name: 'ElastiCache Redis', regions: ['warn', 'good', 'bad', 'good', 'good', 'good'] },
      { name: 'OpenSearch', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'S3 (Artifacts)', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
    ],
  },
  {
    name: 'Observability',
    services: [
      { name: 'CloudWatch', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'Grafana', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'Prometheus', regions: ['good', 'good', 'good', 'good', 'good', 'warn'] },
    ],
  },
  {
    name: 'Security',
    services: [
      { name: 'Auth / OIDC', regions: ['bad', 'warn', 'good', 'good', 'good', 'good'] },
      { name: 'KMS', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
      { name: 'Secrets Manager', regions: ['good', 'good', 'good', 'good', 'good', 'good'] },
    ],
  },
];

export function StatusPage() {
  const regionHeaders = useMemo(() => REGIONS.map((r) => <th key={r}>{r}</th>), []);

  const statusRows = useMemo(() => STATUS_DATA.map((cat) => (
    <>
      <tr key={cat.name}>
        <td colSpan={7} className="cb_matrix__category">{cat.name}</td>
      </tr>
      {cat.services.map((svc) => (
        <tr key={svc.name}>
          <td className="cb_matrix__svc">{svc.name}</td>
          {svc.regions.map((s, i) => (
            <td key={i}><StatusLight status={s} /></td>
          ))}
        </tr>
      ))}
    </>
  )), []);

  return (
    <>
      <PageHeader
        label="Global Health"
        title="Service Status Wall"
        subtitle="Multi-region service health matrix. In production, status is pulled from CloudWatch alarms and health checks."
      />

      <div className="cb_legend">
        <span><StatusLight status="good" /> Operational</span>
        <span><StatusLight status="warn" /> Degraded</span>
        <span><StatusLight status="bad" /> Outage</span>
        <span className="cb_legend__timestamp">Last updated: 12 Feb 2026 09:36 UTC</span>
      </div>

      <div className="cb_matrix-wrap">
        <table className="cb_matrix">
          <thead>
            <tr>
              <th>Service</th>
              {regionHeaders}
            </tr>
          </thead>
          <tbody>
            {statusRows}
          </tbody>
        </table>
      </div>

      <p className="cb_footer cb_footer--inline">
        In production, status signals are pulled from CloudWatch alarms and Route 53 health checks via the API.
      </p>
    </>
  );
}
