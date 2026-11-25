export interface TypeDetail {
  group: 'Configuration' | 'Offering' | 'Experience';
  what: string;
  ask: string[];
  example: string;
}

// Explanations of the ten Doblin types of innovation, keyed by the type name stored in the database.
export const TYPE_DETAILS: Record<string, TypeDetail> = {
  'Profit Model': {
    group: 'Configuration',
    what: 'How you make money. It covers what customers pay for, how and when they pay, and how pricing and costs are structured to turn your offering into revenue.',
    ask: ['What do customers actually pay for today?', 'Could we charge differently, for example by subscription, by usage or for advice?', 'Is there someone else who would pay for this value?'],
    example: 'Moving from a one-off fee to a recurring advisory fee for ongoing risk reviews.',
  },
  Network: {
    group: 'Configuration',
    what: 'How you connect with others to create value. It covers partnerships, alliances, joint ventures and shared platforms that let you do more than you could alone.',
    ask: ['What do others do better than we do?', 'Which partners reach clients we cannot?', 'Could we build something together instead of alone?'],
    example: 'Onboarding intermediaries through a shared partner platform to reach underserved segments.',
  },
  Structure: {
    group: 'Configuration',
    what: 'How you organise and align your people and assets. It covers team design, roles, skills, incentives and facilities, and how they are set up to deliver the work.',
    ask: ['Are the right people and incentives lined up behind this work?', 'Would a different team shape or hand-off remove friction?', 'Which skills are missing or underused?'],
    example: 'One service team that owns the client from first notice to settlement instead of several hand-offs.',
  },
  Process: {
    group: 'Configuration',
    what: 'How you do your work. It covers the core and supporting processes that produce your offerings, and the methods that make them faster, cheaper or more reliable.',
    ask: ['Where is there repeated work, waiting or rework?', 'Which step could be removed, automated or done in a different order?', 'Where do things regularly fall through the gaps?'],
    example: 'Collecting missing documents at intake so cases do not stall later.',
  },
  'Product Performance': {
    group: 'Offering',
    what: 'The features, function and quality of your core offering. It is about how well the product itself does the job customers need, compared with what else is available.',
    ask: ['What would make the product itself better, faster or more complete?', 'Which customer need does it meet poorly today?', 'What do customers work around?'],
    example: 'Making a policy easier to understand, or adding cover for a risk that is currently excluded.',
  },
  'Product System': {
    group: 'Offering',
    what: 'How individual offerings connect and complement one another. It covers bundles, platforms, add-ons and links between products that together are worth more than each alone.',
    ask: ['What else do customers need around this product?', 'Could our offerings work better together?', 'Is there a platform other products could plug into?'],
    example: 'Bundling a risk survey, cover and recovery planning into a single resilience package.',
  },
  Service: {
    group: 'Experience',
    what: 'How you support and enhance the value of your offering. It covers help, advice, guarantees and follow-up that make the offering easier to try, use and get value from.',
    ask: ['Where do customers need help or have to chase us?', 'What would make this easier to use or trust?', 'What happens after the sale?'],
    example: 'Proactive status updates at each milestone so clients never have to ask where things stand.',
  },
  Channel: {
    group: 'Experience',
    what: 'How your offerings reach customers. It covers every touchpoint where customers find, buy and use what you offer, from direct teams and intermediaries to digital and physical routes.',
    ask: ['Where do customers want to find and buy from us?', 'Could a different route reach more people at lower cost?', 'Which touchpoints feel disjointed?'],
    example: 'A self-service digital route for simple requests such as certificates.',
  },
  Brand: {
    group: 'Experience',
    what: 'How you express your offering and your business. It covers the identity, promise and reputation that customers recognise and trust, and that set you apart.',
    ask: ['What do we want to be known for?', 'Does every interaction reinforce that promise?', 'How could we show reliability more clearly?'],
    example: 'Plain-language communication that backs up a reputation for clarity when clients are under stress.',
  },
  'Customer Engagement': {
    group: 'Experience',
    what: 'How you build interactions and relationships that go beyond a transaction. It is about understanding what customers aspire to and creating moments that feel meaningful to them.',
    ask: ['How do we stay relevant between renewals or purchases?', 'What do we know about what customers are trying to achieve?', 'What would make the relationship feel personal?'],
    example: 'Regular client health checks and risk-trend briefings between renewals.',
  },
};
