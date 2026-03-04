/**
 * Weekly Engagement Digest Email
 *
 * Sent to product team every Monday morning with:
 * - Cohort distribution summary
 * - User transition metrics
 * - At-risk user count and trending cohorts
 * - Experiment results snapshot
 *
 * Uses React Email for type-safe, testable email templates
 */

import React from 'react';
import {
  Body,
  Button,
  Column,
  Container,
  Head,
  Hr,
  Html,
  Link,
  Preview,
  Row,
  Section,
  Text,
} from '@react-email/components';

interface CohortStats {
  lifestageStage: string;
  behavioralCohort: string;
  userCount: number;
  avgEngagementScore: number;
}

interface ExperimentResult {
  experimentId: string;
  name: string;
  primaryMetric: string;
  controlMean: number;
  treatmentMean: number;
  lift: number;
  confidence: number;
  status: 'running' | 'completed' | 'inconclusive';
}

interface EngagementDigestProps {
  week: string;
  cohortDistribution: CohortStats[];
  totalUsers: number;
  atRiskCount: number;
  transitionMetrics: {
    newToActivated: number;
    activatedToDrifting: number;
    driftingToRechurned: number;
  };
  topTrendingCohorts: Array<{
    cohort: string;
    growth: number;
  }>;
  experiments: ExperimentResult[];
  dashboardUrl: string;
}

const baseUrl = process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : '';

export const EngagementDigest = ({
  week,
  cohortDistribution,
  totalUsers,
  atRiskCount,
  transitionMetrics,
  topTrendingCohorts,
  experiments,
  dashboardUrl,
}: EngagementDigestProps) => (
  <Html>
    <Head />
    <Preview>Weekly Engagement Digest: {week}</Preview>
    <Body style={main}>
      <Container style={container}>
        {/* Header */}
        <Section style={headerSection}>
          <Text style={logo}>Engagement Engine</Text>
          <Text style={subtitle}>Weekly Digest {week}</Text>
        </Section>

        {/* Executive Summary */}
        <Section style={section}>
          <Text style={heading2}>Executive Summary</Text>

          <Row>
            <Column style={columnHalf}>
              <Text style={metric}>
                <span style={metricValue}>{totalUsers.toLocaleString()}</span>
                <br />
                Total Users
              </Text>
            </Column>
            <Column style={columnHalf}>
              <Text style={metric}>
                <span style={metricValue} style={{ color: '#ef4444' }}>
                  {atRiskCount.toLocaleString()}
                </span>
                <br />
                At-Risk Users
              </Text>
            </Column>
          </Row>

          <Hr style={hr} />

          <Text style={label}>Cohort Transitions</Text>
          <Text style={metricSmall}>
            New → Activated: <strong>{transitionMetrics.newToActivated}</strong> users
          </Text>
          <Text style={metricSmall}>
            Activated → Drifting: <strong>{transitionMetrics.activatedToDrifting}</strong> users
          </Text>
          <Text style={metricSmall}>
            Drifting → Reactivated: <strong>{transitionMetrics.driftingToRechurned}</strong> users
          </Text>
        </Section>

        {/* Cohort Distribution */}
        <Section style={section}>
          <Text style={heading2}>Cohort Distribution</Text>

          <table style={table}>
            <thead>
              <tr style={tableHeader}>
                <th style={tableHeaderCell}>Lifecycle Stage</th>
                <th style={tableHeaderCell}>Behavioral Cohort</th>
                <th style={tableHeaderCell}>User Count</th>
                <th style={tableHeaderCell}>Avg Engagement</th>
              </tr>
            </thead>
            <tbody>
              {cohortDistribution.slice(0, 10).map((cohort, idx) => (
                <tr key={idx} style={idx % 2 === 0 ? tableRowAlt : tableRow}>
                  <td style={tableCell}>{cohort.lifestageStage}</td>
                  <td style={tableCell}>{cohort.behavioralCohort}</td>
                  <td style={tableCell}>{cohort.userCount.toLocaleString()}</td>
                  <td style={tableCell}>{cohort.avgEngagementScore.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        {/* Top Trending Cohorts */}
        <Section style={section}>
          <Text style={heading2}>Top Trending Cohorts (Growth Rate)</Text>

          {topTrendingCohorts.map((trend, idx) => (
            <Row key={idx} style={{ marginBottom: '12px' }}>
              <Column style={{ width: '60%' }}>
                <Text style={metricSmall}>{trend.cohort}</Text>
              </Column>
              <Column style={{ width: '40%', textAlign: 'right' }}>
                <Text
                  style={{
                    ...metricSmall,
                    color: trend.growth > 0 ? '#10b981' : '#ef4444',
                    fontWeight: 'bold',
                  }}
                >
                  {trend.growth > 0 ? '+' : ''}
                  {(trend.growth * 100).toFixed(1)}%
                </Text>
              </Column>
            </Row>
          ))}
        </Section>

        {/* Active Experiments */}
        <Section style={section}>
          <Text style={heading2}>Active Experiments</Text>

          {experiments.map((exp, idx) => (
            <Section key={idx} style={experimentCard}>
              <Text style={experimentTitle}>{exp.name}</Text>

              <Row>
                <Column style={columnThird}>
                  <Text style={smallLabel}>Primary Metric</Text>
                  <Text style={metricSmall}>{exp.primaryMetric}</Text>
                </Column>
                <Column style={columnThird}>
                  <Text style={smallLabel}>Lift</Text>
                  <Text style={{ ...metricSmall, color: exp.lift > 0 ? '#10b981' : '#ef4444' }}>
                    {exp.lift > 0 ? '+' : ''}
                    {(exp.lift * 100).toFixed(1)}%
                  </Text>
                </Column>
                <Column style={columnThird}>
                  <Text style={smallLabel}>Confidence</Text>
                  <Text style={metricSmall}>{(exp.confidence * 100).toFixed(0)}%</Text>
                </Column>
              </Row>

              <Row style={{ marginTop: '12px' }}>
                <Column>
                  <Text style={smallLabel}>Status</Text>
                  <Text
                    style={{
                      ...metricSmall,
                      padding: '4px 8px',
                      backgroundColor: exp.status === 'running' ? '#dbeafe' : '#f0fdf4',
                      color: exp.status === 'running' ? '#1e40af' : '#166534',
                      borderRadius: '4px',
                      display: 'inline-block',
                      fontSize: '12px',
                    }}
                  >
                    {exp.status.charAt(0).toUpperCase() + exp.status.slice(1)}
                  </Text>
                </Column>
              </Row>
            </Section>
          ))}
        </Section>

        {/* Call to Action */}
        <Section style={section}>
          <Button style={button} href={dashboardUrl}>
            View Full Dashboard
          </Button>
        </Section>

        {/* Footer */}
        <Section style={footerSection}>
          <Text style={footerText}>
            This digest is automatically generated every Monday at 9 AM UTC.
            <br />
            Questions? Contact the data team.
          </Text>
          <Text style={{ ...footerText, fontSize: '12px' }}>
            © {new Date().getFullYear()} Engagement Engine. All rights reserved.
          </Text>
        </Section>
      </Container>
    </Body>
  </Html>
);

// Styles
const main = {
  backgroundColor: '#f3f4f6',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
};

const container = {
  backgroundColor: '#ffffff',
  margin: '0 auto',
  marginBottom: '64px',
  padding: '20px 0 48px',
};

const headerSection = {
  backgroundColor: '#1f2937',
  padding: '48px 20px',
  textAlign: 'center' as const,
};

const logo = {
  color: '#ffffff',
  fontSize: '32px',
  fontWeight: 'bold',
  margin: '0 0 16px 0',
};

const subtitle = {
  color: '#d1d5db',
  fontSize: '16px',
  margin: '0',
};

const section = {
  padding: '40px 20px',
};

const heading2 = {
  color: '#1f2937',
  fontSize: '24px',
  fontWeight: 'bold',
  margin: '0 0 24px 0',
};

const label = {
  color: '#4b5563',
  fontSize: '12px',
  fontWeight: 'bold',
  letterSpacing: '0.05em',
  margin: '16px 0 8px 0',
  textTransform: 'uppercase' as const,
};

const smallLabel = {
  color: '#6b7280',
  fontSize: '11px',
  fontWeight: '600',
  margin: '0 0 4px 0',
};

const metric = {
  color: '#1f2937',
  fontSize: '16px',
  lineHeight: '24px',
};

const metricValue = {
  color: '#2563eb',
  fontSize: '32px',
  fontWeight: 'bold',
};

const metricSmall = {
  color: '#374151',
  fontSize: '14px',
  lineHeight: '20px',
  margin: '8px 0',
};

const columnHalf = {
  width: '50%',
  paddingRight: '20px',
};

const columnThird = {
  width: '33.33%',
  paddingRight: '16px',
};

const hr = {
  borderColor: '#e5e7eb',
  margin: '24px 0',
};

const table = {
  width: '100%',
  borderCollapse: 'collapse' as const,
};

const tableHeader = {
  backgroundColor: '#f9fafb',
  borderBottom: '2px solid #e5e7eb',
};

const tableHeaderCell = {
  color: '#374151',
  fontSize: '12px',
  fontWeight: '600',
  padding: '12px 8px',
  textAlign: 'left' as const,
};

const tableRow = {
  borderBottom: '1px solid #f3f4f6',
};

const tableRowAlt = {
  backgroundColor: '#fafbfc',
  borderBottom: '1px solid #f3f4f6',
};

const tableCell = {
  color: '#4b5563',
  fontSize: '13px',
  padding: '12px 8px',
};

const experimentCard = {
  backgroundColor: '#f9fafb',
  border: '1px solid #e5e7eb',
  borderRadius: '6px',
  padding: '16px',
  marginBottom: '16px',
};

const experimentTitle = {
  color: '#1f2937',
  fontSize: '16px',
  fontWeight: '600',
  margin: '0 0 12px 0',
};

const button = {
  backgroundColor: '#2563eb',
  borderRadius: '6px',
  color: '#ffffff',
  display: 'block',
  fontSize: '16px',
  fontWeight: 'bold',
  padding: '12px 32px',
  textAlign: 'center' as const,
  textDecoration: 'none',
  margin: '20px auto',
  width: 'fit-content',
};

const footerSection = {
  backgroundColor: '#f3f4f6',
  padding: '40px 20px',
  textAlign: 'center' as const,
};

const footerText = {
  color: '#6b7280',
  fontSize: '13px',
  lineHeight: '20px',
  margin: '0 0 8px 0',
};

export default EngagementDigest;
