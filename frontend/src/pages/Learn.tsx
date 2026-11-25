import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, BookOpen, ChevronRight, FlaskConical, GraduationCap, Handshake,
  Layers, type LucideIcon, Megaphone, PenTool, Search, Users } from 'lucide-react';
import { ApiError, api, useApi } from '../api/client';
import type { InnovationType, LearningData, PathCard } from '../api/types';
import { TYPE_DETAILS } from '../data/innovationTypes';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
import { ErrorMsg, Loading, ProgressBar } from '../components/Bits';
import learnPhoto from '../assets/learn-hero.jpg';

const STATUS_LABEL: Record<PathCard['status'], string> = {
  not_started: 'Not started', in_progress: 'In progress', completed: 'Completed',
};
const TOPIC_ICONS: [RegExp, LucideIcon][] = [
  [/customer|client/i, Users], [/types? of innovation|doblin/i, Layers], [/experiment|validat|assumption/i, FlaskConical],
  [/partner|business model/i, Handshake], [/proposition|solution/i, PenTool], [/problem|framing/i, Search],
  [/data|evidence/i, BarChart3], [/story/i, Megaphone],
];
const iconFor = (title: string) => TOPIC_ICONS.find(([re]) => re.test(title))?.[1] ?? BookOpen;

function Recommended({ p }: { p: PathCard }) {
  const modules = p.modules_done > 0 ? `${p.modules_done} of ${p.modules_total} modules` : `${p.modules_total} modules`;
  const Icon = iconFor(p.title);
  return (
    <Link to={`/learn/paths/${p.id}`} className="card path">
      <div className={`path__band path__band--${p.status}`}>
        <span className="path__icon"><Icon size={20} /></span>
        <span className="path__badge">{p.badge}</span>
      </div>
      <div className="path__body">
        <span className="small muted">{STATUS_LABEL[p.status]}</span>
        <h3>{p.title}</h3>
        <p className="muted">{p.description}</p>
        <span className="small muted">{p.footer}</span>
        {p.status === 'in_progress' && <ProgressBar percent={p.percent} />}
      </div>
      <div className="path__footrow">
        <span className="small muted">{modules}</span>
        <span className="cta cta--caps">{p.cta} <ArrowRight size={14} /></span>
      </div>
    </Link>
  );
}

export function Learn() {
  const { user, reference } = useApp();
  const { data, error, loading, reload } = useApi<LearningData>('/learning');
  const [activeType, setActiveType] = useState<InnovationType | null>(null);
  const [mentor, setMentor] = useState(false);
  const [area, setArea] = useState(reference.mentor_areas[0]);
  const [message, setMessage] = useState('');
  const [mentorErr, setMentorErr] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const first = user.name.split(' ')[0];

  async function submitMentor(e: FormEvent) {
    e.preventDefault(); setMentorErr(null);
    try { await api.post('/mentor-requests', { area, message }); setSent(true); }
    catch (err) { setMentorErr(err instanceof ApiError ? err.message : 'Could not send the request.'); }
  }
  async function community(join: boolean) { await api.post(`/community/${join ? 'join' : 'leave'}`); reload(); }

  return (
    <>
      <PageHeader title="Learn & connect"
                  subtitle="The Innovation Academy: practical capabilities for the challenges and initiatives you are working on." />
      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading />}
      {data && (
        <>
          {data.continue && (
            <section className="hero hero--compact">
              <div className="hero__copy">
                <div className="continue__head">
                  <span className="hero__eyebrow">Continue learning</span>
                  <span className="small continue__module">{data.continue.modules_done} of {data.continue.modules_total} modules</span>
                </div>
                <h2>{data.continue.title} • {data.continue.percent}% complete</h2>
                {data.continue.recommended_for && <p>Recommended for {data.continue.recommended_for}</p>}
                <ProgressBar percent={data.continue.percent} dark />
                <div className="hero__actions">
                  <Link to={`/learn/paths/${data.continue.id}`} className="btn btn--primary">Continue learning <ArrowRight size={14} /></Link>
                </div>
              </div>
              <img className="hero__photo" src={learnPhoto} alt="Colleagues learning together at a computer" />
            </section>
          )}

          <Link to="/learn/courses" className="card academybar">
            <span className="academybar__icon"><GraduationCap size={20} /></span>
            <span className="academybar__text">
              <strong>Innovation Academy</strong>
              <em>Full courses with lessons, assessments and a Minet certificate.</em>
            </span>
            <span className="cta cta--caps">Browse courses <ArrowRight size={14} /></span>
          </Link>

          <h2 className="h2">Recommended for {first}</h2>
          <div className="grid-3">{data.recommended.map((p) => <Recommended key={p.id} p={p} />)}</div>

          <h2 className="h2">Build the capability you need next</h2>
          <div className="grid-2">
            {data.next.map((p) => {
              const Icon = iconFor(p.title);
              return (
                <Link key={p.id} to={`/learn/paths/${p.id}`} className="card nextpath">
                  <span className={`path__icon path__icon--${p.status}`}><Icon size={20} /></span>
                  <div className="nextpath__body">
                    <h3>{p.title}</h3><p className="muted">{p.description}</p>
                    <span className="cta cta--caps">{p.cta} <ArrowRight size={14} /></span>
                  </div>
                </Link>
              );
            })}
          </div>

          <section id="types" className="card types-card">
            <h2>Discover the ten types of innovation</h2>
            <p className="muted">One initiative can combine several innovation types and has one primary strategic horizon. Select a type to see what it means.</p>
            <div className="grid-2 types-grid">
              {data.types.map((t) => (
                <button key={t.id} type="button" className="typetile" onClick={() => setActiveType(t)}>
                  <strong>{t.name}</strong><ChevronRight size={16} />
                </button>
              ))}
            </div>
          </section>

          <h2 className="h2">People to learn with</h2>
          <div className="grid-2">
            <section className="card people">
              <div className="people__head">
                <h3>Find a mentor</h3><span className="small muted">Customer research, data, operations, tech</span></div>
              <p className="muted">Connect with colleagues who have experience in customer research, data, operations or technology.</p>
              <button className="cta cta--caps" onClick={() => { setSent(false); setMentor(true); }}>Request a connection</button>
            </section>
            <section className="card people">
              <div className="people__head">
                <h3>Innovation community &amp; collaboration</h3><span className="small muted">Connect across teams</span></div>
              <p className="muted">Discuss challenges, share lessons and find collaborators across teams. Bring your claims or partner-onboarding question.</p>
              <div className="people__foot">
                <button className="cta cta--caps" onClick={() => void community(!data.community.joined)}>
                  {data.community.joined ? 'Leave the community' : 'Join the community'}
                </button>
                <span className="small muted">{data.community.joined ? 'You are a member. ' : ''}{data.community.member_count} members (sample)</span>
              </div>
            </section>
          </div>
        </>
      )}

      {activeType && (
        <Modal title={activeType.name} onClose={() => setActiveType(null)}>
          {(() => {
            const detail = TYPE_DETAILS[activeType.name];
            return (
              <div className="typemodal">
                {detail && <span className="typemodal__group">{detail.group}</span>}
                <p className="typemodal__lead">{activeType.short_description}.</p>
                {detail ? (
                  <>
                    <p>{detail.what}</p>
                    <h4>Questions to ask</h4>
                    <ul>{detail.ask.map((q) => <li key={q}>{q}</li>)}</ul>
                    <h4>Illustrative example</h4>
                    <p className="muted">{detail.example}</p>
                  </>
                ) : null}
                <p className="small muted typemodal__foot">One idea can combine several types. You choose them when you submit an idea.</p>
                <div className="typemodal__actions">
                  <Link to="/ideas/new" className="btn btn--primary" onClick={() => setActiveType(null)}>Submit an idea <ArrowRight size={14} /></Link>
                  <button type="button" className="btn btn--outline" onClick={() => setActiveType(null)}>Close</button>
                </div>
              </div>
            );
          })()}
        </Modal>
      )}

      {mentor && (
        <Modal title="Request a mentor connection" onClose={() => setMentor(false)}>
          {sent ? (
            <>
              <p>Your request has been recorded. The Innovation team will suggest a colleague with experience in {area.toLowerCase()}.</p>
              <button className="btn btn--primary" onClick={() => setMentor(false)}>Close</button>
            </>
          ) : (
            <form onSubmit={submitMentor}>
              <div className="field"><label htmlFor="area">Area of experience</label>
                <select id="area" value={area} onChange={(e) => setArea(e.target.value)}>
                  {reference.mentor_areas.map((a) => <option key={a}>{a}</option>)}
                </select></div>
              <div className="field"><label htmlFor="msg">What would you like help with? (optional)</label>
                <textarea id="msg" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} /></div>
              {mentorErr && <p className="field__error">{mentorErr}</p>}
              <button type="submit" className="btn btn--primary">Send request</button>
            </form>
          )}
        </Modal>
      )}
    </>
  );
}
