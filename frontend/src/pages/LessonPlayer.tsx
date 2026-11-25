import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Award, Check, ChevronLeft, ChevronRight, ClipboardCheck, Sparkles } from 'lucide-react';
import { ApiError, api, useApi } from '../api/client';
import type { CompleteLessonResponse, LessonResponse } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { BlockRenderer } from '../components/lms/BlockRenderer';
import { ErrorMsg, Loading, ProgressBar } from '../components/Bits';

const HEARTBEAT_SECONDS = 60;

export function LessonPlayer() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, setData } = useApi<LessonResponse>(`/lms/lessons/${id}`);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [unmet, setUnmet] = useState<string[]>([]);
  const [earned, setEarned] = useState<CompleteLessonResponse['certificate']>(null);
  const spent = useRef(0);

  // Record time on the lesson. Never completes anything on its own.
  useEffect(() => {
    if (!id) return;
    spent.current = 0;
    const timer = setInterval(() => {
      spent.current += HEARTBEAT_SECONDS;
      api.post(`/lms/lessons/${id}/heartbeat`, { seconds_spent: HEARTBEAT_SECONDS })
        .catch(() => { /* time tracking is best effort; never block the learner */ });
    }, HEARTBEAT_SECONDS * 1000);
    return () => clearInterval(timer);
  }, [id]);

  useEffect(() => { setUnmet([]); setEarned(null); setActionError(null); }, [id]);

  const back = { to: '/learn/courses', label: 'Innovation Academy' };
  if (error) return <><PageHeader title="Lesson" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !data) return <><PageHeader title="Lesson" back={back} /><Loading /></>;

  const { lesson, course, module, navigation, assessments, enrollment } = data;
  const isComplete = lesson.status === 'completed';

  async function markComplete() {
    setBusy(true); setActionError(null);
    try {
      const result = await api.post<CompleteLessonResponse>(
        `/lms/lessons/${lesson.id}/complete`, { seconds_spent: spent.current });
      spent.current = 0;
      setUnmet(result.unmet_requirements);
      setEarned(result.certificate);
      setData({ ...data!, lesson: { ...lesson, status: result.status }, enrollment: result.enrollment });
      if (result.status === 'completed' && navigation.next_id) {
        navigate(`/learn/lessons/${navigation.next_id}`);
      }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not save your progress.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={lesson.title}
                  subtitle={`${course.title} — ${module.title}`}
                  back={{ to: `/learn/courses/${course.id}`, label: course.title }} />

      <div className="player">
        <div className="player__main">
          <div className="player__meta">
            <span className="small muted">
              Lesson {navigation.position} of {navigation.total}
            </span>
            {isComplete && <span className="status-pill status-pill--emerald">Completed</span>}
          </div>
          <ProgressBar percent={enrollment.progress_percent} />

          {lesson.objectives.length > 0 && (
            <section className="card player__objectives">
              <h2 className="card-title">In this lesson</h2>
              <ul className="objectives">
                {lesson.objectives.map((o, i) => <li key={i}><Check size={14} strokeWidth={2.5} /> {o}</li>)}
              </ul>
            </section>
          )}

          <article className="card player__content">
            {lesson.blocks.length === 0
              ? <p className="muted">This lesson has no content yet.</p>
              : lesson.blocks.map((block) => <BlockRenderer key={block.id} block={block} />)}
          </article>

          {assessments.length > 0 && (
            <section className="card player__assessment">
              <ClipboardCheck size={18} />
              <div>
                <h3>{assessments[0].title}</h3>
                <p className="muted small">
                  {assessments[0].required
                    ? 'You need to pass this assessment to complete the course.'
                    : 'An optional check of your understanding.'}
                </p>
              </div>
              <Link to={`/learn/assessments/${assessments[0].id}`} className="btn btn--outline">
                Open assessment
              </Link>
            </section>
          )}

          {unmet.length > 0 && (
            <div className="card notice notice--amber">
              <strong>Before this lesson counts as complete</strong>
              <ul>{unmet.map((u, i) => <li key={i}>{u}</li>)}</ul>
            </div>
          )}

          {earned && (
            <div className="card notice notice--emerald">
              <Award size={18} />
              <div>
                <strong>You have completed {course.title}.</strong>
                <p className="small">Certificate {earned.certificate_number} has been issued.</p>
              </div>
              <Link to={`/learn/courses/${course.id}`} className="btn btn--primary">View certificate</Link>
            </div>
          )}

          {actionError && <ErrorMsg text={actionError} />}

          <nav className="player__nav">
            {navigation.previous_id
              ? <Link to={`/learn/lessons/${navigation.previous_id}`} className="btn btn--outline">
                  <ChevronLeft size={15} /> Previous
                </Link>
              : <span />}
            <div className="player__nav-right">
              {!isComplete && (
                <button className="btn btn--primary" onClick={() => void markComplete()} disabled={busy}>
                  {busy ? 'Saving...' : <>Mark complete <Check size={15} /></>}
                </button>
              )}
              {navigation.next_id && (
                <Link to={`/learn/lessons/${navigation.next_id}`}
                      className={`btn ${isComplete ? 'btn--primary' : 'btn--outline'}`}>
                  Next <ChevronRight size={15} />
                </Link>
              )}
              {!navigation.next_id && isComplete && (
                <Link to={`/learn/courses/${course.id}`} className="btn btn--primary">
                  Back to course
                </Link>
              )}
            </div>
          </nav>

          {course.ai_disclosure && (
            <p className="small muted player__disclosure">
              <Sparkles size={12} /> {course.ai_disclosure}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
