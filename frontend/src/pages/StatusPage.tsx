import { Fragment, useMemo } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StatusLight } from '../components/StatusLight';

type Status = 'good' | 'warn' | 'bad';

interface Service {
  name: string;
  status: Status;
  detail?: string;
}

interface Category {
  name: string;
  services: Service[];
}

const REGION = 'eu-west-2 (London)';

const STATUS_DATA: Category[] = [
  {
    name: 'Identity & Authentication',
    services: [
      { name: 'Cognito User Pool', status: 'good', detail: 'Sign-in & 2FA flows nominal' },
      { name: 'OIDC Provider', status: 'good', detail: 'Token issuance healthy' },
      { name: 'Hosted UI / Login', status: 'good', detail: 'OAuth2 callback responding' },
      { name: 'Identity Verification', status: 'warn', detail: 'Elevated latency on document checks' },
    ],
  },
  {
    name: 'API & Compute',
    services: [
      { name: 'API Gateway', status: 'good', detail: 'All routes healthy' },
      { name: 'Lambda (Actions)', status: 'good', detail: 'Cold starts within SLA' },
      { name: 'Lambda (Authoriser)', status: 'good', detail: 'JWT validation nominal' },
    ],
  },
  {
    name: 'Data & Storage',
    services: [
      { name: 'DynamoDB (Audit)', status: 'good', detail: 'Read/write capacity normal' },
      { name: 'DynamoDB (Sessions)', status: 'good', detail: 'TTL cleanup running' },
      { name: 'S3 (Frontend Assets)', status: 'good', detail: 'Origin access healthy' },
      { name: 'Secrets Manager', status: 'good', detail: 'Rotation on schedule' },
    ],
  },
  {
    name: 'Network & Delivery',
    services: [
      { name: 'CloudFront CDN', status: 'good', detail: 'Edge cache hit ratio 94%' },
      { name: 'WAF', status: 'good', detail: 'No blocked threat spikes' },
      { name: 'Route 53 DNS', status: 'good', detail: 'Health checks passing' },
    ],
  },
  {
    name: 'Observability & Security',
    services: [
      { name: 'CloudWatch Alarms', status: 'good', detail: 'All alarms in OK state' },
      { name: 'CloudTrail', status: 'good', detail: 'Audit logging active' },
      { name: 'KMS', status: 'good', detail: 'Encryption keys available' },
    ],
  },
];

export function StatusPage() {
  const totalServices = useMemo(
    () => STATUS_DATA.reduce((sum, cat) => sum + cat.services.length, 0),
    [],
  );

  const summary = useMemo(() => {
    let good = 0, warn = 0, bad = 0;
    STATUS_DATA.forEach((cat) =>
      cat.services.forEach((svc) => {
        if (svc.status === 'good') good++;
        else if (svc.status === 'warn') warn++;
        else bad++;
      }),
    );
    return { good, warn, bad };
  }, []);

  return (
    <>
      <PageHeader
        label="ScotAccount Health"
        title="Service Status"
        subtitle={`Single-region deployment — ${REGION}. Status signals sourced from CloudWatch alarms and health checks.`}
      />

      <div className="cb_legend">
        <span><StatusLight status="good" /> Operational</span>
        <span><StatusLight status="warn" /> Degraded</span>
        <span><StatusLight status="bad" /> Outage</span>
        <span className="cb_legend__timestamp">Manual snapshot</span>
      </div>

      <div className="cb_status-summary">
        <div className="cb_status-summary__item cb_status-summary__item--good">
          <span className="cb_status-summary__count">{summary.good}</span>
          <span className="cb_status-summary__label">Operational</span>
        </div>
        <div className="cb_status-summary__item cb_status-summary__item--warn">
          <span className="cb_status-summary__count">{summary.warn}</span>
          <span className="cb_status-summary__label">Degraded</span>
        </div>
        <div className="cb_status-summary__item cb_status-summary__item--bad">
          <span className="cb_status-summary__count">{summary.bad}</span>
          <span className="cb_status-summary__label">Outage</span>
        </div>
        <div className="cb_status-summary__item">
          <span className="cb_status-summary__count">{totalServices}</span>
          <span className="cb_status-summary__label">Total Services</span>
        </div>
      </div>

      <div className="cb_matrix-wrap">
        <table className="cb_matrix">
          <thead>
            <tr>
              <th>Service</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {STATUS_DATA.map((cat) => (
              <Fragment key={cat.name}>
                <tr>
                  <td colSpan={3} className="cb_matrix__category">{cat.name}</td>
                </tr>
                {cat.services.map((svc) => (
                  <tr key={svc.name}>
                    <td className="cb_matrix__svc">{svc.name}</td>
                    <td><StatusLight status={svc.status} /></td>
                    <td className="cb_matrix__detail">{svc.detail}</td>
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="cb_footer cb_footer--inline">
        ScotAccount operates exclusively in AWS {REGION}. Status display is manually maintained.
        Live CloudWatch integration is planned.
      </p>
    </>
  );
}
