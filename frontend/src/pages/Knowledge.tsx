import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useApi } from '../api/client';
import type { ImpactData } from '../api/types';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';
import { PortfolioHorizons } from '../components/PortfolioHorizons';
import { ErrorMsg, Loading } from '../components/Bits';

export function Knowledge() {
  const { user } = useApp();
  const { data, error, loading } = useApi<ImpactData>('/impact');
  return (
    <>
      <PageHeader title="Knowledge & impact"
                  subtitle="Make learning reusable and show the business outcomes that validated innovation delivers." />
      <p className="overview-chip"><strong>PORTFOLIO OVERVIEW</strong> Strategic guidance • illustrative example data • not organisational performance</p>
      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading />}
      {data && (
        <>
          <section className="card strip">
            <div className="strip__lead">
              <strong>Illustrative activity</strong><span className="small muted">Illustrative counts • not actual performance</span></div>
            {data.strip.map((s) => (
              <div key={s.key} className="strip__stat">
                <span className="small muted">{s.label.toUpperCase()}</span>
                {s.value === null ? <strong className="strip__text">Not yet validated</strong> : <strong className="strip__num">{s.value}</strong>}
              </div>
            ))}
          </section>

          <section className="card card--accent statement">
            <h2>From activity to evidence of value</h2>
            <p>Report only validated outcomes. Separate ideas, experiments and pilots from benefits that have been measured and confirmed.</p>
          </section>

          <PortfolioHorizons />

          <h2 className="h2 h2--tight">Outcome measurement by horizon</h2>
          <p className="small muted">Measurement and validation status. Pending outcomes are not confirmed business value.</p>
          <section className="card impact">
            <div className="impact__head"><h3>Impact reporting by three horizons</h3>
              <span className="small muted">Only report benefit as realised/validated with supporting evidence</span></div>
            <div className="impact__cols">
              {data.horizons.map((h) => (
                <div key={h.id} className="impact__col">
                  <span className="small muted upper">{h.name}</span>
                  <h4>{h.headline}</h4>
                  {h.metrics.map((m) => (
                    <div key={m.id} className="metric">
                      <span className="small">{m.name}</span>
                      <strong>{m.validated ? 'Validated' : m.status}</strong>
                      <span className="small muted">{m.evidence_status}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>

          <section className="card validation">
            <h3>When can a benefit be called validated?</h3>
            <p className="muted">All three are required: supporting evidence, a named benefits owner and a measurement period.</p>
            <div className="validation__cols">
              <p className="muted small-lines">Evidence: {data.validation.evidence}<br />
                Benefits owner: {data.validation.benefits_owner}<br />Measurement period: {data.validation.measurement_period}</p>
              <p className="small-lines"><strong>Current status: {data.validation.status}</strong><br />
                <strong>{data.validation.statement}</strong></p>
            </div>
          </section>

          <h2 className="h2">Knowledge library</h2>
          <p className="muted small">Templates, learnings and research to support your work.</p>
          <div className="grid-4 library">
            {data.library.map((c) => (
              <Link key={c.slug} to={`/knowledge/library/${c.slug}`} className="card libtile">
                <h3>{c.title}</h3><p className="muted">{c.description}</p>
                <span className="small muted">{c.meta}</span>
                <span className="cta cta--caps">{c.cta} <ArrowRight size={14} /></span>
              </Link>
            ))}
          </div>

          <section className="card card--grey governance">
            <h3>Governance built into the journey</h3>
            <p className="muted small-lines">
              Strategic alignment • Customer value • Feasibility • Risk and compliance • Potential impact<br />
              Initiative owner and sponsor • Stage-gate decisions • Funding or resources where applicable<br />
              Portfolio oversight is separate from {user.name.split(' ')[0]}'s personal workspace. Benefits require evidence, an accountable owner and a measurement period.
            </p>
          </section>
        </>
      )}
    </>
  );
}
