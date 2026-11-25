import { Link, useParams } from 'react-router-dom';
import { Check } from 'lucide-react';
import { api, useApi } from '../api/client';
import type { PathDetailData } from '../api/types';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading, ProgressBar } from '../components/Bits';

export function PathDetail() {
  const { id } = useParams();
  const { data: p, error, loading, setData } = useApi<PathDetailData>(`/learning/paths/${id}`);
  const back = { to: '/learn', label: 'Learn & connect' };
  if (error) return <><PageHeader title="Learning path" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !p) return <><PageHeader title="Learning path" back={back} /><Loading /></>;

  const act = async (action: 'complete-next' | 'reset') =>
    setData(await api.post<PathDetailData>(`/learning/paths/${p.id}/${action}`));
  const finished = p.status === 'completed';

  return (
    <>
      <PageHeader title={p.title} subtitle={p.description} back={back} />
      <div className="detail-grid">
        <section className="card">
          <div className="path-progress">
            <span className="small">{p.modules_done} of {p.modules_total} modules complete</span>
            <strong>{p.percent}%</strong>
          </div>
          <ProgressBar percent={p.percent} />
          <ol className="modules">
            {p.modules.map((m, i) => (
              <li key={m.id} className={m.done ? 'is-done' : ''}>
                <span className="modules__mark">{m.done ? <Check size={14} strokeWidth={2.5} /> : i + 1}</span>
                <span className="modules__text"><strong>{m.title}</strong><em>{m.summary}</em></span>
                <span className="small muted">{m.minutes} min</span>
              </li>
            ))}
          </ol>
          <div className="path-actions">
            {finished
              ? <span className="pill">Completed. This counts towards your learning rank.</span>
              : <button className="btn btn--primary" onClick={() => void act('complete-next')}>
                  {p.modules_done === 0 ? 'Start path' : 'Mark next module complete'}
                </button>}
            {p.modules_done > 0 && <button className="btn btn--outline" onClick={() => void act('reset')}>Reset progress</button>}
          </div>
          <p className="small muted spaced">Illustrative content. Progress is saved to the dummy database.</p>
        </section>
        <aside className="card card--accent detail-side">
          <h3 className="card-title">About this path</h3>
          <p className="muted">{p.footer}</p>
          {p.linked_experiment && (
            <p className="muted">Linked to your experiment: <Link to={`/workspace?record=experiment-${p.linked_experiment.id}`}>{p.linked_experiment.title}</Link></p>
          )}
          {p.recommended_for && <p className="muted">Recommended for {p.recommended_for}</p>}
        </aside>
      </div>
    </>
  );
}
