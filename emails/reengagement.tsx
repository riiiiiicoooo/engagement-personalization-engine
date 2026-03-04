/**
 * Re-engagement Email Template
 *
 * Personalized email for at-risk and drifting users with:
 * - Dynamic content blocks based on engagement patterns
 * - Personalized recommendations
 * - Clear CTA with incentive
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
  Image,
  Link,
  Preview,
  Row,
  Section,
  Text,
} from '@react-email/components';

interface RecommendationBlock {
  id: string;
  title: string;
  description: string;
  category: string;
  duration?: string;
  imageUrl?: string;
}

interface ReengagementEmailProps {
  userName: string;
  userEmail: string;
  daysSinceActive: number;
  engagementTier: number;
  previousActivities: string[];
  recommendations: RecommendationBlock[];
  appUrl: string;
  incentive?: string;
  personalizedMessage?: string;
}

const baseUrl = process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : '';

export const ReengagementEmail = ({
  userName,
  userEmail,
  daysSinceActive,
  engagementTier,
  previousActivities,
  recommendations,
  appUrl,
  incentive,
  personalizedMessage,
}: ReengagementEmailProps) => {
  // Determine messaging based on engagement tier
  const isMostDrifted = engagementTier >= 4;
  const primaryHeading = isMostDrifted ? "We miss you! Let's get you back on track." : 'Ready to continue your wellness journey?';

  const bodyText = personalizedMessage || getDefaultBodyText(daysSinceActive, engagementTier, previousActivities);

  return (
    <Html>
      <Head />
      <Preview>{primaryHeading}</Preview>
      <Body style={main}>
        <Container style={container}>
          {/* Header with brand */}
          <Section style={headerSection}>
            <Text style={logo}>Wellness Platform</Text>
          </Section>

          {/* Main content */}
          <Section style={contentSection}>
            <Text style={greeting}>Hi {userName},</Text>

            <Text style={bodyTextStyle}>{bodyText}</Text>

            {/* Previous activity callout */}
            {previousActivities.length > 0 && (
              <>
                <Hr style={hr} />
                <Section style={calloutSection}>
                  <Text style={calloutLabel}>You've been working on:</Text>
                  {previousActivities.slice(0, 3).map((activity, idx) => (
                    <Text key={idx} style={calloutItem}>
                      • {activity}
                    </Text>
                  ))}
                </Section>
              </>
            )}

            {/* Personalized recommendations */}
            {recommendations.length > 0 && (
              <>
                <Hr style={hr} />
                <Section style={recommendationsSection}>
                  <Text style={sectionHeading}>
                    {isMostDrifted ? 'Start Here' : 'Personalized for You'}
                  </Text>

                  {recommendations.slice(0, 3).map((rec, idx) => (
                    <Section key={idx} style={recommendationCard}>
                      <Row>
                        {rec.imageUrl && (
                          <Column style={{ width: '100px', paddingRight: '16px' }}>
                            <Image
                              src={rec.imageUrl}
                              alt={rec.title}
                              style={{
                                borderRadius: '6px',
                                height: '100px',
                                objectFit: 'cover',
                                width: '100px',
                              }}
                            />
                          </Column>
                        )}
                        <Column>
                          <Text style={recommendationTitle}>{rec.title}</Text>
                          <Text style={recommendationDesc}>{rec.description}</Text>
                          {rec.duration && (
                            <Text style={recommendationMeta}>⏱️ {rec.duration}</Text>
                          )}
                          <Link href={`${appUrl}/content/${rec.id}`} style={inlineLink}>
                            View →
                          </Link>
                        </Column>
                      </Row>
                    </Section>
                  ))}
                </Section>
              </>
            )}

            {/* Incentive section if applicable */}
            {incentive && (
              <>
                <Hr style={hr} />
                <Section style={incentiveSection}>
                  <Text style={incentiveLabel}>Special Offer</Text>
                  <Text style={incentiveText}>{incentive}</Text>
                </Section>
              </>
            )}
          </Section>

          {/* CTA Section */}
          <Section style={ctaSection}>
            <Button
              href={appUrl}
              style={{
                ...button,
                backgroundColor: isMostDrifted ? '#ef4444' : '#2563eb',
              }}
            >
              {isMostDrifted ? 'Get Started Now' : 'Continue Your Journey'}
            </Button>
            <Text style={ctaSubtext}>
              <Link href={appUrl} style={lightLink}>
                or visit the app
              </Link>
            </Text>
          </Section>

          {/* Questions section */}
          <Section style={supportSection}>
            <Text style={supportText}>
              Have questions? Reply to this email or visit our{' '}
              <Link href={`${appUrl}/help`} style={lightLink}>
                help center
              </Link>
              .
            </Text>
          </Section>

          {/* Footer */}
          <Section style={footerSection}>
            <Hr style={hr} />
            <Text style={footerText}>
              © {new Date().getFullYear()} Wellness Platform. All rights reserved.
            </Text>
            <Text style={footerText}>
              You received this email because you haven't been active recently.
              <br />
              <Link href={`${appUrl}/preferences`} style={footerLink}>
                Update notification preferences
              </Link>
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
};

/**
 * Generate default body text based on engagement context
 */
function getDefaultBodyText(
  daysSinceActive: number,
  engagementTier: number,
  previousActivities: string[]
): string {
  if (engagementTier <= 2) {
    // High engagement users - casual re-engagement
    return `We've noticed it's been ${daysSinceActive} days since you last checked in. The wellness community (and your goals!) have missed you. We've curated some personalized recommendations based on what you've been working on.`;
  } else if (engagementTier === 3) {
    // Medium engagement - encouraging message
    return `It's been ${daysSinceActive} days, and we wanted to remind you of your progress. Remember that big goal you were working on? We're here to help you get back on track with content tailored to your interests.`;
  } else {
    // Low engagement - urgent, supportive tone
    return `We haven't seen you in ${daysSinceActive} days, and we're here to help you restart your wellness journey. Whether you need motivation, guidance, or just a fresh perspective—we've got resources that can help. Let's pick up where you left off.`;
  }
}

// Styles
const main = {
  backgroundColor: '#f8f9fa',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
};

const container = {
  backgroundColor: '#ffffff',
  margin: '0 auto',
  marginBottom: '64px',
  marginTop: '16px',
  maxWidth: '600px',
  padding: '0',
};

const headerSection = {
  backgroundColor: '#1f2937',
  padding: '32px 20px',
  textAlign: 'center' as const,
};

const logo = {
  color: '#ffffff',
  fontSize: '28px',
  fontWeight: 'bold',
  margin: '0',
};

const contentSection = {
  padding: '40px 32px',
};

const greeting = {
  color: '#1f2937',
  fontSize: '18px',
  fontWeight: '600',
  margin: '0 0 16px 0',
};

const bodyTextStyle = {
  color: '#4b5563',
  fontSize: '15px',
  lineHeight: '24px',
  margin: '0 0 24px 0',
};

const sectionHeading = {
  color: '#1f2937',
  fontSize: '18px',
  fontWeight: '600',
  margin: '0 0 20px 0',
};

const hr = {
  borderColor: '#e5e7eb',
  margin: '24px 0',
};

const calloutSection = {
  backgroundColor: '#f0f4ff',
  borderLeft: '4px solid #2563eb',
  padding: '16px',
};

const calloutLabel = {
  color: '#2563eb',
  fontSize: '12px',
  fontWeight: '600',
  margin: '0 0 8px 0',
  textTransform: 'uppercase' as const,
};

const calloutItem = {
  color: '#374151',
  fontSize: '14px',
  margin: '4px 0',
};

const recommendationsSection = {
  marginBottom: '0',
};

const recommendationCard = {
  backgroundColor: '#f9fafb',
  borderRadius: '8px',
  border: '1px solid #e5e7eb',
  marginBottom: '16px',
  padding: '16px',
};

const recommendationTitle = {
  color: '#1f2937',
  fontSize: '16px',
  fontWeight: '600',
  margin: '0 0 8px 0',
};

const recommendationDesc = {
  color: '#4b5563',
  fontSize: '14px',
  lineHeight: '20px',
  margin: '0 0 8px 0',
};

const recommendationMeta = {
  color: '#6b7280',
  fontSize: '12px',
  margin: '0 0 8px 0',
};

const inlineLink = {
  color: '#2563eb',
  textDecoration: 'none',
  fontSize: '14px',
  fontWeight: '600',
};

const incentiveSection = {
  backgroundColor: '#fef3c7',
  border: '1px solid #fcd34d',
  borderRadius: '6px',
  padding: '16px',
};

const incentiveLabel = {
  color: '#92400e',
  fontSize: '12px',
  fontWeight: '600',
  margin: '0 0 8px 0',
  textTransform: 'uppercase' as const,
};

const incentiveText = {
  color: '#78350f',
  fontSize: '14px',
  lineHeight: '20px',
  margin: '0',
};

const ctaSection = {
  padding: '24px 32px',
  textAlign: 'center' as const,
};

const button = {
  backgroundColor: '#2563eb',
  borderRadius: '6px',
  color: '#ffffff',
  fontSize: '16px',
  fontWeight: 'bold',
  padding: '14px 40px',
  textDecoration: 'none',
  display: 'inline-block',
};

const ctaSubtext = {
  color: '#6b7280',
  fontSize: '13px',
  margin: '16px 0 0 0',
};

const lightLink = {
  color: '#2563eb',
  textDecoration: 'underline',
};

const supportSection = {
  padding: '0 32px 24px 32px',
  textAlign: 'center' as const,
};

const supportText = {
  color: '#4b5563',
  fontSize: '13px',
  lineHeight: '20px',
  margin: '0',
};

const footerSection = {
  backgroundColor: '#f9fafb',
  padding: '24px 32px',
  textAlign: 'center' as const,
};

const footerText = {
  color: '#6b7280',
  fontSize: '12px',
  lineHeight: '18px',
  margin: '8px 0',
};

const footerLink = {
  color: '#2563eb',
  textDecoration: 'underline',
};

export default ReengagementEmail;
