import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check } from 'lucide-react';
import { useApi } from '../api/client';
import type { IdeaDetail, RecordCard, RecordDetail } from '../api/types';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
// import { StageGate } from '../components/StageGate';
import { ErrorMsg, Loading, StatusPill, Tabs } from '../components/Bits';

const NOTE_ORDER = ['Strategic alignment', 'Customer value', 'Feasibility', 'Risk and compliance', 'Potential impact'];
const noteRank = (k: string) => (NOTE_ORDER.includes(k) ? NOTE_ORDER.indexOf(k) : NOTE_ORDER.length);

function RecordTile({ r, selected, onOpen }: { r: RecordCard; selected: boolean; onOpen: () => void }) {
  const meta = [r.horizon, r.types.join(' / '), r.reference_id].filter(Boolean).join(' • ');
  return (
    <article className={`card record ${selected ? 'is-selected' : ''}`}>
      <div className="record__top">
        <span className={`kind-tag kind-tag--${r.kind}`}>{r.kind} • {r.is_draft ? 'Draft' : r.stage}</span>
        <StatusPill status={r.status} />
      </div>
      <h3>{r.title}</h3>
      <p className="record__meta">Owner: <strong>{r.owner}</strong>{meta ? ` • ${meta}` : ''}</p>
      <div className="record__foot">
        <p className="record__next"><span className="muted">{r.next_label}:</span> {r.next_text}</p>
        {r.is_draft
          ? <Link to={`/ideas/new?draft=${r.id}`} className="cta">Continue draft <ArrowRight size={14} /></Link>
          : <button className="cta" onClick={onOpen} aria-pressed={selected}>Open record <ArrowRight size={14} /></button>}
      </div>
    </article>
  );
}

function RecordModal({ record, onClose }: { record: RecordCard; onClose: () => void }) {
  const { user, reference } = useApp();
  const detail = useApi<RecordDetail | IdeaDetail>(`/${record.kind === 'idea' ? 'ideas' : 'experiments'}/${record.id}`);
  const d = detail.data;
  const first = user.name.split(' ')[0];
  const stageIdx = d ? reference.stages.findIndex((s) => s.name === d.stage) : -1;

  return (
    <Modal title={record.title} onClose={onClose} wide>
      {detail.error && <ErrorMsg text={detail.error} />}
      {!d && !detail.error && <Loading />}
      {d && (
        <div className="rd">
          <div className="rd__meta">
            <span className="tagline">{d.tag}</span>
            <StatusPill status={d.status} />
          </div>

          <ol className="stagetrack" aria-label={`Current stage: ${d.stage}`}>
            {reference.stages.map((s, i) => (
              <li key={s.id} className={i < stageIdx ? 'is-done' : i === stageIdx ? 'is-current' : ''}
                  aria-current={i === stageIdx ? 'step' : undefined}>
                <span>{i < stageIdx ? <Check size={11} strokeWidth={3} /> : i + 1}</span>{s.name}
              </li>
            ))}
          </ol>

          <div className="rd__cols">
            <section>
              <h4>Details</h4>
              <dl className="kv">
                <div><dt>Owner</dt><dd>{d.owner}</dd></div>
                <div><dt>Primary horizon</dt><dd>{d.horizon ?? 'Not set'}</dd></div>
                <div><dt>Innovation types</dt><dd>{d.types.length ? d.types.join(' / ') : 'Not set'}</dd></div>
                <div><dt>Sponsor / decision owner</dt><dd>{d.sponsor ?? 'Not yet assigned'}</dd></div>
              </dl>
            </section>
            <section>
              <h4>Evidence &amp; learning</h4>
              <ul className="evidence-list muted">
                {d.evidence_lines.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </section>
          </div>

          <div className="rd__next">
            <div><span className="rd__label">{d.next_label}</span><strong>{d.next_text}</strong></div>
            {d.resource_decision && <div><span className="rd__label">Resource decision</span><span>{d.resource_decision}</span></div>}
          </div>

          <section>
            <h4>Before the next decision</h4>
            <div className="rd__notes">
              {Object.entries(d.review_notes).sort(([a], [b]) => noteRank(a) - noteRank(b)).map(([k, v]) => (
                <div key={k}><strong>{k}</strong><span>{v}</span></div>
              ))}
            </div>
            <p className="small muted rd__foot">
              Portfolio funding and resource decisions are reviewed by sponsors. {first}'s workspace tracks personal actions, not portfolio quotas.
            </p>
          </section>

          <div className="rd__actions">
            <button type="button" className="btn btn--outline" onClick={onClose}>Close</button>
            {d.can_edit && (
              <Link to={`/ideas/new?draft=${d.id}`} className="btn btn--primary">Edit and resubmit <ArrowRight size={14} /></Link>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export function Workspace() {
  const [params, setParams] = useSearchParams();
  const ws = useApi<{ ideas: RecordCard[]; experiments: RecordCard[] }>('/workspace');
  const [filter, setFilter] = useState<'all' | 'idea' | 'experiment'>('all');

  const all = useMemo(() => [...(ws.data?.ideas ?? []), ...(ws.data?.experiments ?? [])], [ws.data]);
  const shown = filter === 'all' ? all : all.filter((r) => r.kind === filter);
  const wanted = params.get('record');
  const opened = all.find((r) => r.key === wanted && !r.is_draft) ?? null;

  return (
    <>
      <PageHeader title="My innovation workspace"
                  subtitle="Track your ideas and experiments from first review to validated learning and implementation." />
      <div className="records__head">
        <h2 className="h2 h2--tight">My records</h2>
        {ws.data && all.length > 0 && (
          <Tabs tabs={[
            { id: 'all', label: `All records (${all.length})` },
            { id: 'idea', label: `Ideas (${ws.data.ideas.length})` },
            { id: 'experiment', label: `Experiments (${ws.data.experiments.length})` },
          ]} value={filter} onChange={setFilter} />
        )}
      </div>
      {ws.error && <ErrorMsg text={ws.error} />}
      {ws.loading && !ws.data && <Loading />}
      {ws.data && all.length === 0 && (
        <div className="card empty"><strong>You have no records yet.</strong>
          <p className="muted">Submit an idea to start. <Link to="/ideas/new">Submit an idea</Link></p></div>
      )}
      <div className="grid-2">
        {shown.map((r) => (
          <RecordTile key={r.key} r={r} selected={opened?.key === r.key}
                      onOpen={() => setParams({ record: r.key })} />
        ))}
      </div>

      {/* <StageGate /> */}

      {opened && <RecordModal key={opened.key} record={opened} onClose={() => setParams({})} />}
    </>
  );
}
