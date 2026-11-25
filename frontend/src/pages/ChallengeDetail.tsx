import { Link, useParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useApi } from '../api/client';
import type { ChallengeDetailData } from '../api/types';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading, StatusPill } from '../components/Bits';

export function ChallengeDetail() {
  const { id } = useParams();
  const { data: c, error, loading } = useApi<ChallengeDetailData>(`/challenges/${id}`);
  const back = { to: '/explore', label: 'All challenges' };

  if (error) return <><PageHeader title="Challenge" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !c) return <><PageHeader title="Challenge" back={back} /><Loading /></>;

  return (
    <>
      <PageHeader title={c.title} back={back} subtitle={c.how_might_we} />
      <div className="detail-grid">
        <div className="detail-main">
          <section className="card">
            <h3 className="card-title">Background</h3>
            <p className="muted">{c.background}</p>
            <h3 className="card-title spaced">What success could look like</h3>
            <p className="muted">{c.success_looks_like}</p>
            <p className="small muted spaced">
              {c.is_illustrative ? 'Illustrative challenge • not actual organisational initiative' : ''}
            </p>
          </section>
          <section className="card">
            <h3 className="card-title">Your ideas for this challenge</h3>
            {c.my_ideas.length === 0 ? <p className="muted">You have not linked an idea to this challenge yet.</p> : (
              <ul className="plain-list">
                {c.my_ideas.map((i) => (
                  <li key={i.key}>
                    <Link to={i.is_draft ? `/ideas/new?draft=${i.id}` : `/workspace?record=${i.key}`}>{i.title}</Link>
                    <StatusPill status={i.status} />
                  </li>
                ))}
              </ul>
            )}
            <p className="small muted spaced">
              {c.colleague_idea_count === 0 ? 'No colleague ideas are linked to this challenge yet.'
                : `${c.colleague_idea_count} colleague ${c.colleague_idea_count === 1 ? 'idea is' : 'ideas are'} linked to this challenge.`}
            </p>
          </section>
        </div>
        <aside className="card card--accent detail-side">
          <dl className="kv kv--stack">
            <div><dt>PRIMARY HORIZON</dt><dd className="red upper">{c.horizon}</dd></div>
            <div><dt>INNOVATION TYPE</dt><dd className="red">{c.types.join(' / ')}</dd></div>
            <div><dt>SOURCE</dt><dd>{c.source}</dd></div>
            <div><dt>BUSINESS SPONSOR</dt><dd>{c.sponsor}</dd></div>
            <div><dt>STATUS</dt><dd className="red">{c.status}</dd></div>
          </dl>
          <Link to={`/ideas/new?challenge=${c.id}`} className="btn btn--primary btn--block">
            Submit an idea for this challenge <ArrowRight size={14} />
          </Link>
        </aside>
      </div>
    </>
  );
}
