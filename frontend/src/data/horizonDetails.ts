export interface HorizonDetail {
  label: string; title: string; question: string; focus: string; purpose: string; impact: string;
  example?: { initiative: string; measure: string };
}

// Ordered Horizon 1, 2, 3 (matches the order of reference.horizons).
export const HORIZON_DETAILS: HorizonDetail[] = [
  {
    label: 'Horizon 1', title: 'Core Innovation',
    question: 'How do we improve what we already do?',
    focus: 'Focuses on operational efficiency, service or product enhancements, and sustaining current performance to protect competitiveness.',
    purpose: 'Protect & optimise today’s business.',
    impact: 'Focuses on incremental improvements to existing products, services, customer experiences, operating models, and business processes to protect competitiveness and elevate operational performance.',
  },
  {
    label: 'Horizon 2', title: 'Adjacent Innovation',
    question: 'How do we expand what we do today into new opportunities?',
    focus: 'Leverages existing enterprise capabilities to reach new markets, customer needs, channels, or strategic partnerships.',
    purpose: 'Expand into new growth spaces.',
    impact: 'Leverages existing organizational capabilities to serve new markets, customer needs, distribution channels, or strategic partnerships, broadening our market presence.',
  },
  {
    label: 'Horizon 3', title: 'Transformational Innovation',
    question: 'How do we reinvent how value is created and captured?',
    focus: 'Seeks to establish new business models, ecosystems, platforms, and future sources of competitive advantage.',
    purpose: 'Create future growth engines.',
    impact: 'Establishes new business models, ecosystems and platforms that become future sources of competitive advantage.',
    example: { initiative: 'Digital Risk Intelligence Platform', measure: 'Revenue from new business models' },
  },
];
