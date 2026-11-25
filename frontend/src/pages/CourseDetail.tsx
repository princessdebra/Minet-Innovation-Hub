import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Award, Check, ChevronRight, Circle, Clock, Download, PlayCircle, Sparkles } from 'lucide-react';
import { ApiError, api, useApi } from '../api/client';
import { formatMinutes, type CourseDetailResponse, type Enrollment } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading, ProgressBar } from '../components/Bits';

export function CourseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi<CourseDetailResponse>(`/lms/courses/${id}`);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const back = { to: '/learn/courses', label: 'Innovation Academy' };
  if (error) return <><PageHeader title="Course" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !data) return <><PageHeader title="Course" back={back} /><Loading /></>;

  const { course, modules, enrollment, requirements, certificate, resume_lesson_id } = data;
  const lessons = modules.flatMap((m) => m.lessons);
  const done = lessons.filter((l) => l.status === 'completed').length;

  async function start() {
    setBusy(true); setActionError(null);
    try {
      if (!enrollment) await api.post<Enrollment>(`/lms/courses/${course.id}/enrol`);
      if (resume_lesson_id) navigate(`/learn/lessons/${resume_lesson_id}`);
      else reload();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not start this course.');
    } finally {
      setBusy(false);
    }
  }

  const label = !enrollment || enrollment.status === 'not_started' ? 'Start course'
    : enrollment.status === 'completed' ? 'Review course' : 'Resume course';

  return (
    <>
      <PageHeader title={course.title} subtitle={course.summary ?? undefined} back={back} />

      <div className="detail-grid">
        <div>
          <section className="card coursehead">
            <span className="small muted">
              {course.category || 'Course'} &bull; {course.difficulty}
              {course.estimated_minutes > 0 && <> &bull; <Clock size={11} /> {formatMinutes(course.estimated_minutes)}</>}
              {' '}&bull; {data.lesson_count} lesson{data.lesson_count === 1 ? '' : 's'}
            </span>
            {course.description && <p className="coursehead__desc">{course.description}</p>}

            {enrollment && enrollment.status !== 'not_started' && (
              <div className="coursehead__progress">
                <div className="path-progress">
                  <span className="small">{done} of {lessons.length} lessons complete</span>
                  <strong>{enrollment.progress_percent}%</strong>
                </div>
                <ProgressBar percent={enrollment.progress_percent} />
              </div>
            )}

            {actionError && <ErrorMsg text={actionError} />}
            <div className="coursehead__actions">
              <button className="btn btn--primary" onClick={() => void start()} disabled={busy || !resume_lesson_id && !lessons.length}>
                <PlayCircle size={15} /> {busy ? 'Opening...' : label}
              </button>
              {requirements.assessments.length > 0 && (
                <Link to={`/learn/assessments/${requirements.assessments[0].id}`} className="btn btn--outline">
                  Go to assessment
                </Link>
              )}
            </div>
          </section>

          {course.objectives.length > 0 && (
            <section className="card">
              <h2 className="card-title">What you will learn</h2>
              <ul className="objectives">
                {course.objectives.map((o, i) => (
                  <li key={i}><Check size={14} strokeWidth={2.5} /> {o}</li>
                ))}
              </ul>
            </section>
          )}

          <h2 className="h2">Course content</h2>
          {modules.map((module) => (
            <section key={module.id} className="card modulecard">
              <div className="modulecard__head">
                <h3>{module.title}</h3>
                <span className="small muted">
                  {module.lessons.length} lesson{module.lessons.length === 1 ? '' : 's'}
                  {module.estimated_minutes > 0 && ` • ${formatMinutes(module.estimated_minutes)}`}
                </span>
              </div>
              {module.description && <p className="muted small">{module.description}</p>}
              <ol className="lessonlist">
                {module.lessons.map((lesson) => (
                  <li key={lesson.id}>
                    <Link to={`/learn/lessons/${lesson.id}`} className="lessonlist__item">
                      <span className={`lessonlist__mark is-${lesson.status ?? 'not_started'}`}>
                        {lesson.status === 'completed'
                          ? <Check size={13} strokeWidth={3} />
                          : <Circle size={9} strokeWidth={3} />}
                      </span>
                      <span className="lessonlist__text">
                        <strong>{lesson.title}</strong>
                        {lesson.description && <em>{lesson.description}</em>}
                      </span>
                      <span className="small muted">{formatMinutes(lesson.estimated_minutes)}</span>
                      <ChevronRight size={15} />
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>

        <aside className="detail-side-col">
          <section className="card">
            <h3 className="card-title">Completion requirements</h3>
            <ul className="reqlist">
              <li><Check size={13} /> Complete all {requirements.lessons} lessons</li>
              {requirements.assessments.map((a) => (
                <li key={a.id}>
                  <Check size={13} /> {a.required ? 'Pass' : 'Optional'}: {a.title} ({a.pass_percent}% to pass)
                </li>
              ))}
            </ul>
            {requirements.blockers.length > 0 && (
              <div className="reqlist__blockers">
                <span className="small muted">Still outstanding</span>
                <ul>{requirements.blockers.map((b, i) => <li key={i}>{b}</li>)}</ul>
              </div>
            )}
          </section>

          {certificate && (
            <section className="card certcard">
              <Award size={22} />
              <h3>Certificate earned</h3>
              <p className="muted small">
                {certificate.certificate_number} &bull; issued {new Date(certificate.issued_at).toLocaleDateString()}
              </p>
              <a className="btn btn--primary btn--block" href={certificate.download_url}>
                <Download size={14} /> Download PDF
              </a>
              <Link to={`/verify/${certificate.verification_code}`} className="cta cta--caps">
                Verify this certificate
              </Link>
            </section>
          )}

          {course.ai_disclosure && (
            <section className="card aidisclosure">
              <Sparkles size={15} />
              <p className="small muted">{course.ai_disclosure}</p>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
