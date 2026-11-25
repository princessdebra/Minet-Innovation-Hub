import { PageHeader } from '../components/PageHeader';

const FAQ: [string, string][] = [
  ['What is the Innovation Hub?', 'A place to find business challenges, share ideas, track your experiments, build capability and see what has been validated.'],
  ['Do I need a business case to submit an idea?', 'No. A short, specific description of the user, the friction and the outcome you want is enough. The Innovation team helps develop it.'],
  ['What are the three horizons?', 'Core protects and optimises today\'s business. Adjacent expands into new growth spaces. Transformational creates future growth engines. They guide the portfolio and are not individual targets.'],
  ['What are the ten types of innovation?', 'The Doblin model: Profit Model, Network, Structure, Process, Product Performance, Product System, Service, Channel, Brand and Customer Engagement. One idea can combine several.'],
  ['Does every idea become an experiment?', 'No. Ideas pass through stage-gate decisions: Source, Assess, Test, then Scale, Adapt or Stop.'],
  ['When is a benefit called validated?', 'Only with supporting evidence, a named benefits owner and a measurement period. Until then it is reported as not validated.'],
  ['Is the data real?', 'This is a proof of concept. Challenges, rankings, counts and content are illustrative and are labelled that way.'],
];

export function Help() {
  return (
    <>
      <PageHeader title="Help" subtitle="Short answers about how the Innovation Hub works." />
      <div className="stack">
        {FAQ.map(([q, a]) => (
          <article key={q} className="card"><h3 className="card-title">{q}</h3><p className="muted">{a}</p></article>
        ))}
      </div>
    </>
  );
}
