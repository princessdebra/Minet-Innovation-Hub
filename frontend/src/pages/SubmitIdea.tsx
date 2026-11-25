import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check, CheckCircle2, Lightbulb, Target } from 'lucide-react';
import { ApiError, api } from '../api/client';
import type { ChallengeDetailData, IdeaDetail } from '../api/types';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';

interface Form {
  title: string; problem: string; solution: string; expected_value: string; evidence: string;
  horizon: string | null; type_ids: number[]; collaborators: string; challenge_id: number | null;
}
const EMPTY: Form = { title: '', problem: '', solution: '', expected_value: '', evidence: '',
  horizon: null, type_ids: [], collaborators: '', challenge_id: null };

const STEPS = ['Acknowledgement and reference ID', 'Initial triage by Innovation team',
  'Clarification or sponsor assigned', 'Review, test or route to owner'];
const NOT_SURE_HINT = 'We can help classify it';

function FormStep({ n, title, hint }: { n: number; title: string; hint: string }) {
  return (
    <div className="form-step">
      <span className="form-step__num">{n}</span>
      <div><h3>{title}</h3><p>{hint}</p></div>
    </div>
  );
}

export function SubmitIdea() {
  const { user, reference, can } = useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [form, setForm] = useState<Form>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [draftId, setDraftId] = useState<number | null>(null);
  const [challengeTitle, setChallengeTitle] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [done, setDone] = useState<{ id: number; reference_id: string } | null>(null);
  const loadedDraft = useRef<number | null>(null);

  const draftParam = params.get('draft');
  const challengeParam = params.get('challenge');

  useEffect(() => {
    if (!draftParam || Number(draftParam) === loadedDraft.current) return;
    api.get<IdeaDetail>(`/ideas/${draftParam}`).then((d) => {
      if (!d.can_edit) { navigate(`/workspace?record=${d.key}`, { replace: true }); return; }
      loadedDraft.current = d.id;
      setDraftId(d.id);
      setForm({
        title: d.title, problem: d.problem ?? '', solution: d.solution ?? '',
        expected_value: d.expected_value ?? '', evidence: d.evidence ?? '',
        horizon: d.horizon_unsure ? 'Not sure' : d.horizon, type_ids: d.type_ids,
        collaborators: d.collaborators ?? '', challenge_id: d.challenge?.id ?? null,
      });
      setChallengeTitle(d.challenge?.title ?? null);
    }).catch(() => setNotice('That draft could not be opened.'));
  }, [draftParam, navigate]);

  useEffect(() => {
    if (!challengeParam || draftParam) return;
    api.get<ChallengeDetailData>(`/challenges/${challengeParam}`).then((c) => {
      setForm((f) => ({ ...f, challenge_id: c.id }));
      setChallengeTitle(c.title);
    }).catch(() => undefined);
  }, [challengeParam, draftParam]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (errors[k]) setErrors((e) => { const { [k]: _drop, ...rest } = e; return rest; });
  };
  const toggleType = (id: number) =>
    set('type_ids', form.type_ids.includes(id) ? form.type_ids.filter((x) => x !== id) : [...form.type_ids, id]);

  async function send(submit: boolean) {
    setBusy(true); setNotice(null); setErrors({});
    const body = { ...form, submit };
    try {
      const res = draftId
        ? await api.put<{ id: number; reference_id: string | null }>(`/ideas/${draftId}`, body)
        : await api.post<{ id: number; reference_id: string | null }>('/ideas', body);
      if (submit) {
        setDone({ id: res.id, reference_id: res.reference_id ?? '' });
      } else {
        loadedDraft.current = res.id;
        setDraftId(res.id);
        setParams({ draft: String(res.id) }, { replace: true });
        setNotice('Draft saved. You can complete it later from My ideas & experiments.');
      }
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.errors).length) {
        setErrors(e.errors);
        setTimeout(() => document.querySelector('[data-invalid="true"]')?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 50);
      } else {
        setNotice((e as Error).message);
      }
    } finally {
      setBusy(false);
    }
  }

  const onSubmit = (e: FormEvent) => { e.preventDefault(); void send(true); };
  const reset = () => { setForm(EMPTY); setDone(null); setDraftId(null); setChallengeTitle(null); loadedDraft.current = null; setParams({}, { replace: true }); };

  const err = (k: string) => errors[k] ? <p className="field__error" role="alert">{errors[k]}</p> : null;
  const inv = (k: string) => (errors[k] ? 'true' : undefined);

  const nextSteps = (
    <ol className="stepper">
      {STEPS.map((s, i) => <li key={s}><span className="stepper__num">{i + 1}</span><span>{s}</span></li>)}
    </ol>
  );

  if (done) {
    return (
      <>
        <PageHeader title="Submit an idea" subtitle="Thank you. Your idea is with the Innovation team." />
        <div className="detail-grid">
          <section className="card done">
            <span className="done__icon"><CheckCircle2 size={22} /></span>
            <h2>Idea submitted</h2>
            <p className="muted">Keep this reference ID if you need to ask about your idea.</p>
            <p className="done__ref">{done.reference_id}</p>
            <div className="done__actions">
              <Link to={`/workspace?record=idea-${done.id}`} className="btn btn--primary">
                View in My ideas &amp; experiments <ArrowRight size={14} />
              </Link>
              <button className="btn btn--outline" onClick={reset}>Submit another idea</button>
            </div>
          </section>
          <aside className="card detail-side">
            <h3 className="card-title">What happens next?</h3>
            {nextSteps}
          </aside>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Submit an idea"
                  subtitle="A short guided submission. You can start with a rough thought; the Innovation team helps develop it." />

      <div className="detail-grid">
        <form className="card form" onSubmit={onSubmit} noValidate>
          <div className="form__head">
            <h2 className="form__title">Tell us what could be better</h2>
            <span className="small muted">Submitting as <strong>{user.name}</strong></span>
          </div>
          {challengeTitle && (
            <p className="linked-challenge"><Target size={15} /> Linked challenge: <strong>{challengeTitle}</strong>
              <button type="button" className="linkbtn" onClick={() => { set('challenge_id', null); setChallengeTitle(null); }}>Remove</button>
            </p>
          )}

          <FormStep n={1} title="The problem" hint="Who is affected, what could change and why it matters." />
          <div className="field" data-invalid={inv('title')}>
            <label htmlFor="title">Idea title</label>
            <input id="title" value={form.title} maxLength={160} placeholder="A clear, short description"
                   onChange={(e) => set('title', e.target.value)} aria-invalid={!!errors.title} />
            {err('title')}
          </div>
          <div className="field-row">
            <div className="field" data-invalid={inv('problem')}>
              <label htmlFor="problem">Problem or opportunity</label>
              <textarea id="problem" rows={4} value={form.problem} placeholder="Who experiences the problem and when?"
                        onChange={(e) => set('problem', e.target.value)} aria-invalid={!!errors.problem} />
              {err('problem')}
            </div>
            <div className="field" data-invalid={inv('solution')}>
              <label htmlFor="solution">Proposed solution</label>
              <textarea id="solution" rows={4} value={form.solution} placeholder="What could be done differently?"
                        onChange={(e) => set('solution', e.target.value)} aria-invalid={!!errors.solution} />
              {err('solution')}
            </div>
          </div>
          <div className="field" data-invalid={inv('expected_value')}>
            <label htmlFor="value">Expected value or benefit</label>
            <input id="value" value={form.expected_value} placeholder="Customer, colleague, cost, revenue, risk or speed"
                   onChange={(e) => set('expected_value', e.target.value)} aria-invalid={!!errors.expected_value} />
            {err('expected_value')}
          </div>
          <div className="field">
            <label htmlFor="evidence">Supporting evidence or insight</label>
            <textarea id="evidence" rows={3} value={form.evidence}
                      placeholder="Optional: customer feedback, pain points, benchmarks or early observations"
                      onChange={(e) => set('evidence', e.target.value)} />
          </div>

          <FormStep n={2} title="Classify the idea" hint="Your best guess is fine. The Innovation team will help refine it." />
          <div className="field" data-invalid={inv('horizon')}>
            <span className="field__label">Potential innovation horizon</span>
            <div className="choice-row" role="radiogroup" aria-label="Potential innovation horizon">
              {[...reference.horizons.map((h) => ({ name: h.name, hint: h.short_description })),
                { name: 'Not sure', hint: NOT_SURE_HINT }].map((h) => (
                <button type="button" key={h.name} role="radio" aria-checked={form.horizon === h.name}
                        className={`choice ${form.horizon === h.name ? 'is-active' : ''}`}
                        onClick={() => set('horizon', h.name)}>
                  <strong>{h.name}</strong> <span>{h.hint}</span>
                  {form.horizon === h.name && <Check size={14} className="choice__tick" />}
                </button>
              ))}
            </div>
            <p className="small muted">Select one primary horizon. This helps the Innovation team route and frame the idea.</p>
            {err('horizon')}
          </div>

          <div className="field" data-invalid={inv('type_ids')}>
            <span className="field__label">Relevant innovation type(s)</span>
            <fieldset className="types">
              <legend className="small">Doblin model: select all that apply</legend>
              <div className="types__grid">
                {reference.innovation_types.map((t) => (
                  <label key={t.id} className={`check type-tile ${form.type_ids.includes(t.id) ? 'is-active' : ''}`}>
                    <input type="checkbox" checked={form.type_ids.includes(t.id)} onChange={() => toggleType(t.id)} />
                    <span className="check__box" aria-hidden="true" />
                    <span><strong>{t.name}</strong><em>{t.short_description}</em></span>
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="small muted">Select the types that best describe the idea. This helps the Innovation team frame the opportunity.</p>
            {err('type_ids')}
          </div>

          <FormStep n={3} title="Collaboration" hint="Optional. Who could help develop or test this?" />
          <div className="field">
            <label htmlFor="collab">Potential collaborators</label>
            <input id="collab" value={form.collaborators} placeholder="Optional: teams, colleagues or partners"
                   onChange={(e) => set('collaborators', e.target.value)} />
          </div>

          <div className="infobox-row">
            <div className="infobox"><strong>How the Innovation team can help</strong>
              <p>We can help classify the idea, develop the opportunity and assign the right owner or sponsor. No full business case is required on entry.</p></div>
            <div className="infobox"><strong>Later review considers</strong>
              <p>Strategic alignment, customer value, feasibility, risk/compliance and potential impact. Not every idea becomes an experiment or pilot.</p></div>
          </div>

          <div className="form__foot">
            <button type="submit" className="btn btn--primary btn--lg" disabled={busy || !can('idea:create')}>
              Submit idea <ArrowRight size={16} />
            </button>
            <button type="button" className="btn btn--outline btn--lg" disabled={busy || !can('idea:create')}
                    onClick={() => void send(false)}>Save draft</button>
            <span className="muted form__hint" aria-live="polite">{notice ?? 'Drafts can be saved and completed later.'}</span>
          </div>
        </form>

        <div className="detail-side stack">
          <aside className="card">
            <h3 className="card-title">What happens next?</h3>
            {nextSteps}
          </aside>
          <aside className="card tipcard">
            <span className="tipcard__icon"><Lightbulb size={16} /></span>
            <h3 className="card-title">Good ideas are specific</h3>
            <p className="muted">Describe the user, the friction and the outcome you want to improve.</p>
            <span className="tipcard__tag">No full business case required</span>
          </aside>
        </div>
      </div>
    </>
  );
}
