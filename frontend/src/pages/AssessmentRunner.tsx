import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Award, Check, Clock, RotateCcw, X } from 'lucide-react';
import { ApiError, api, useApi } from '../api/client';
import type { AssessmentView, StartAttemptResponse, SubmitAttemptResponse } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading } from '../components/Bits';

type Answers = Record<string, string | string[]>;

function Countdown({ deadline }: { deadline: string }) {
  const [left, setLeft] = useState(() => Math.max(0, new Date(deadline).getTime() - Date.now()));
  useEffect(() => {
    const timer = setInterval(
      () => setLeft(Math.max(0, new Date(deadline).getTime() - Date.now())), 1000);
    return () => clearInterval(timer);
  }, [deadline]);
  const minutes = Math.floor(left / 60000);
  const seconds = Math.floor((left % 60000) / 1000);
  return (
    <span className={`quiz__timer ${left < 60000 ? 'is-low' : ''}`}>
      <Clock size={13} /> {minutes}:{String(seconds).padStart(2, '0')}
    </span>
  );
}

export function AssessmentRunner() {
  const { id } = useParams();
  const { data, error, loading, reload } = useApi<AssessmentView>(`/lms/assessments/${id}`);
  const [attempt, setAttempt] = useState<StartAttemptResponse | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [result, setResult] = useState<SubmitAttemptResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const back = { to: '/learn/courses', label: 'Innovation Academy' };
  if (error) return <><PageHeader title="Assessment" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !data) return <><PageHeader title="Assessment" back={back} /><Loading /></>;

  const courseLink = { to: `/learn/courses/${data.course_id}`, label: 'Back to course' };

  async function start() {
    setBusy(true); setActionError(null); setResult(null); setAnswers({});
    try {
      setAttempt(await api.post<StartAttemptResponse>(`/lms/assessments/${id}/attempts`));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not start this assessment.');
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!attempt) return;
    setBusy(true); setActionError(null);
    try {
      const submitted = await api.post<SubmitAttemptResponse>(
        `/lms/attempts/${attempt.id}/submit`, { answers });
      setResult(submitted);
      setAttempt(null);
      reload();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not submit your answers.');
      setAttempt(null);
      reload();
    } finally {
      setBusy(false);
    }
  }

  function toggle(questionId: number, optionId: string, multiple: boolean) {
    setAnswers((prev) => {
      const key = String(questionId);
      if (!multiple) return { ...prev, [key]: optionId };
      const current = Array.isArray(prev[key]) ? (prev[key] as string[]) : [];
      return {
        ...prev,
        [key]: current.includes(optionId)
          ? current.filter((o) => o !== optionId)
          : [...current, optionId],
      };
    });
  }

  /* ------------------------------------------------------------- results -- */
  if (result) {
    const byQuestion = new Map((result.results ?? []).map((r) => [r.question_id, r]));
    return (
      <>
        <PageHeader title={data.title} back={courseLink} />
        <section className={`card quizresult ${result.passed ? 'is-pass' : 'is-fail'}`}>
          <span className="quizresult__icon">
            {result.passed ? <Award size={26} /> : <RotateCcw size={24} />}
          </span>
          <div>
            <h2>{result.passed ? 'Passed' : 'Not passed this time'}</h2>
            <p className="muted">
              You scored <strong>{result.percent}%</strong> ({result.score} of {result.max_score} marks).
              The pass mark is {result.pass_percent}%.
            </p>
            <p className="small muted">
              {result.attempts_left > 0
                ? `${result.attempts_left} attempt${result.attempts_left === 1 ? '' : 's'} remaining.`
                : 'You have used all your attempts.'}
            </p>
          </div>
          <div className="quizresult__actions">
            {!result.passed && result.attempts_left > 0 && (
              <button className="btn btn--primary" onClick={() => void start()} disabled={busy}>
                Try again
              </button>
            )}
            <Link to={courseLink.to} className="btn btn--outline">Back to course</Link>
          </div>
        </section>

        {result.certificate && (
          <div className="card notice notice--emerald">
            <Award size={18} />
            <div>
              <strong>Course complete.</strong>
              <p className="small">Certificate {result.certificate.certificate_number} has been issued.</p>
            </div>
            <a className="btn btn--primary" href={result.certificate.download_url}>Download PDF</a>
          </div>
        )}

        <h2 className="h2">Your answers</h2>
        {data.questions.map((question, index) => {
          const outcome = byQuestion.get(question.id);
          return (
            <section key={question.id} className={`card quizreview ${outcome?.correct ? 'is-correct' : 'is-wrong'}`}>
              <div className="quizreview__head">
                <span className="quizreview__mark">
                  {outcome?.correct ? <Check size={14} strokeWidth={3} /> : <X size={14} strokeWidth={3} />}
                </span>
                <h3>{index + 1}. {question.prompt}</h3>
                <span className="small muted">
                  {outcome?.marks_awarded ?? 0} / {outcome?.marks_possible ?? question.marks}
                </span>
              </div>
              {outcome?.explanation && <p className="muted small quizreview__why">{outcome.explanation}</p>}
            </section>
          );
        })}
      </>
    );
  }

  /* ------------------------------------------------------------ attempt --- */
  if (attempt) {
    const questions = attempt.assessment.questions;
    const answered = questions.filter((q) => {
      const value = answers[String(q.id)];
      return Array.isArray(value) ? value.length > 0 : Boolean(value);
    }).length;

    return (
      <>
        <PageHeader title={data.title} back={courseLink} />
        <section className="card quizbar">
          <span className="small muted">Attempt {attempt.attempt_number} &bull; {answered} of {questions.length} answered</span>
          {attempt.deadline && <Countdown deadline={attempt.deadline} />}
        </section>

        {questions.map((question, index) => {
          const multiple = question.kind === 'multiple';
          const value = answers[String(question.id)];
          return (
            <section key={question.id} className="card quizq">
              <h3>{index + 1}. {question.prompt}</h3>
              <p className="small muted">
                {multiple ? 'Select all that apply' : 'Select one answer'}
                {question.marks > 1 && ` • ${question.marks} marks`}
              </p>
              {question.kind === 'short_answer' ? (
                <div className="field">
                  <input type="text" value={typeof value === 'string' ? value : ''}
                         placeholder="Type your answer"
                         onChange={(e) => setAnswers((p) => ({ ...p, [String(question.id)]: e.target.value }))} />
                </div>
              ) : (
                <div className="quizq__options">
                  {question.options.map((option) => {
                    const selected = multiple
                      ? Array.isArray(value) && value.includes(option.id)
                      : value === option.id;
                    return (
                      <label key={option.id} className={`quizopt ${selected ? 'is-active' : ''}`}>
                        <input type={multiple ? 'checkbox' : 'radio'}
                               name={`q-${question.id}`} checked={selected}
                               onChange={() => toggle(question.id, option.id, multiple)} />
                        <span className="quizopt__box">{selected && <Check size={12} strokeWidth={3} />}</span>
                        <span>{option.text}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}

        {actionError && <ErrorMsg text={actionError} />}
        <div className="quizsubmit">
          <button className="btn btn--primary" onClick={() => void submit()} disabled={busy}>
            {busy ? 'Submitting...' : 'Submit answers'}
          </button>
          <span className="small muted">
            Your answers are marked by Minet after you submit.
          </span>
        </div>
      </>
    );
  }

  /* --------------------------------------------------------------- intro -- */
  const used = data.attempts_used ?? 0;
  const left = data.attempts_left ?? data.max_attempts;
  return (
    <>
      <PageHeader title={data.title} back={courseLink} />
      <section className="card quizintro">
        {data.instructions && <p>{data.instructions}</p>}
        <dl className="kv">
          <div><dt>Questions</dt><dd>{data.question_count}</dd></div>
          <div><dt>Pass mark</dt><dd>{data.pass_percent}%</dd></div>
          <div><dt>Attempts</dt><dd>{used} used &bull; {left} remaining</dd></div>
          {data.time_limit_minutes && (
            <div><dt>Time limit</dt><dd>{data.time_limit_minutes} minutes</dd></div>
          )}
        </dl>
        {data.best && data.best.percent !== null && (
          <p className="small muted">
            Your best result so far: <strong>{data.best.percent}%</strong>
            {data.best.passed ? ' (passed)' : ''}
          </p>
        )}
        {actionError && <ErrorMsg text={actionError} />}
        <div className="quizintro__actions">
          <button className="btn btn--primary" onClick={() => void start()} disabled={busy || left <= 0}>
            {busy ? 'Starting...' : used > 0 ? 'Start another attempt' : 'Start assessment'}
          </button>
          <Link to={courseLink.to} className="btn btn--outline">Back to course</Link>
        </div>
        {left <= 0 && (
          <p className="small muted">
            You have used all {data.max_attempts} attempts. Speak to the Innovation team if you
            need another.
          </p>
        )}
      </section>
    </>
  );
}
