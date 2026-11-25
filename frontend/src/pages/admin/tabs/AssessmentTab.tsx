import { FormEvent, useState } from 'react';
import { AlertTriangle, Check, Plus, Sparkles, Trash2 } from 'lucide-react';
import { ApiError, api } from '../../../api/client';
import type { AdminCourse, QuestionKind, QuestionView } from '../../../api/lms';
import { ErrorMsg } from '../../../components/Bits';

interface DraftOption { id: string; text: string }
interface DraftQuestion {
  key: string; prompt: string; kind: QuestionKind;
  options: DraftOption[]; correct: string[]; marks: number; explanation: string;
  aiGenerated: boolean;
}

const LETTERS = 'abcdefgh';
let counter = 0;
const nextKey = () => `q${++counter}`;

function blankQuestion(): DraftQuestion {
  return {
    key: nextKey(), prompt: '', kind: 'single',
    options: [{ id: 'a', text: '' }, { id: 'b', text: '' }],
    correct: [], marks: 1, explanation: '', aiGenerated: false,
  };
}

function fromApi(question: QuestionView): DraftQuestion {
  return {
    key: nextKey(),
    prompt: question.prompt,
    kind: question.kind,
    options: question.options.length
      ? question.options.map((o) => ({ id: o.id, text: o.text }))
      : [{ id: 'a', text: '' }, { id: 'b', text: '' }],
    correct: question.correct ?? [],
    marks: question.marks,
    explanation: question.explanation ?? '',
    aiGenerated: Boolean(question.is_ai_generated),
  };
}

export function AssessmentTab({ course, onChanged }: {
  course: AdminCourse; onChanged: (message?: string) => void;
}) {
  const existing = course.assessments?.[0];
  const [assessment, setAssessment] = useState({
    title: existing?.title ?? 'End-of-course assessment',
    instructions: existing?.instructions ?? '',
    pass_percent: existing?.pass_percent ?? 70,
    max_attempts: existing?.max_attempts ?? 3,
    time_limit_minutes: existing?.time_limit_minutes ?? null as number | null,
    is_required_for_completion: existing?.is_required_for_completion ?? true,
    is_published: existing?.is_published ?? false,
  });
  const [questions, setQuestions] = useState<DraftQuestion[]>(
    existing?.questions?.length ? existing.questions.map(fromApi) : [blankQuestion()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const aiCount = questions.filter((q) => q.aiGenerated).length;

  function update(key: string, patch: Partial<DraftQuestion>) {
    setQuestions((prev) => prev.map((q) => (q.key === key ? { ...q, ...patch } : q)));
  }

  function setKind(key: string, kind: QuestionKind) {
    setQuestions((prev) => prev.map((q) => {
      if (q.key !== key) return q;
      if (kind === 'truefalse') {
        return { ...q, kind, options: [{ id: 'a', text: 'True' }, { id: 'b', text: 'False' }],
                 correct: q.correct.slice(0, 1) };
      }
      if (kind === 'short_answer') return { ...q, kind, options: [], correct: q.correct };
      const options = q.options.length >= 2 ? q.options
        : [{ id: 'a', text: '' }, { id: 'b', text: '' }];
      return { ...q, kind, options, correct: kind === 'single' ? q.correct.slice(0, 1) : q.correct };
    }));
  }

  function toggleCorrect(question: DraftQuestion, optionId: string) {
    const multiple = question.kind === 'multiple';
    const correct = multiple
      ? (question.correct.includes(optionId)
        ? question.correct.filter((c) => c !== optionId)
        : [...question.correct, optionId])
      : [optionId];
    update(question.key, { correct });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null); setFieldErrors({});
    const payload = {
      ...assessment,
      time_limit_minutes: assessment.time_limit_minutes || null,
      questions: questions
        .filter((q) => q.prompt.trim())
        .map((q) => ({
          prompt: q.prompt.trim(),
          kind: q.kind,
          options: q.kind === 'short_answer' ? []
            : q.options.filter((o) => o.text.trim()).map((o) => ({ id: o.id, text: o.text.trim() })),
          correct: q.kind === 'short_answer'
            ? q.correct.map((c) => c.trim()).filter(Boolean)
            : q.correct,
          marks: Math.max(1, q.marks),
          explanation: q.explanation.trim() || null,
        })),
    };
    try {
      if (existing) await api.put(`/lms/admin/assessments/${existing.id}`, payload);
      else await api.post(`/lms/admin/courses/${course.id}/assessments`, payload);
      onChanged('Assessment saved.');
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.errors).length) setFieldErrors(err.errors);
      else setError(err instanceof ApiError ? err.message : 'Could not save the assessment.');
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!existing) return;
    setError(null);
    try {
      await api.del(`/lms/admin/assessments/${existing.id}`);
      onChanged('Assessment deleted.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the assessment.');
    }
  }

  return (
    <form className="studioform" onSubmit={save}>
      {aiCount > 0 && (
        <div className="card notice notice--amber">
          <Sparkles size={18} />
          <div>
            <strong>{aiCount} question{aiCount === 1 ? '' : 's'} came from AI generation.</strong>
            <p className="small">
              Check the wording and the marked answers before publishing. Saving marks them as
              reviewed by you.
            </p>
          </div>
        </div>
      )}

      <section className="card">
        <h2 className="card-title">Assessment settings</h2>
        <div className="field">
          <label htmlFor="a-title">Title</label>
          <input id="a-title" value={assessment.title} required
                 onChange={(e) => setAssessment({ ...assessment, title: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="a-instructions">Instructions for learners</label>
          <textarea id="a-instructions" rows={3} value={assessment.instructions ?? ''}
                    onChange={(e) => setAssessment({ ...assessment, instructions: e.target.value })} />
        </div>
        <div className="grid-3">
          <div className="field">
            <label htmlFor="a-pass">Pass mark (%)</label>
            <input id="a-pass" type="number" min={1} max={100} value={assessment.pass_percent}
                   onChange={(e) => setAssessment({ ...assessment, pass_percent: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="a-attempts">Attempts allowed</label>
            <input id="a-attempts" type="number" min={1} max={20} value={assessment.max_attempts}
                   onChange={(e) => setAssessment({ ...assessment, max_attempts: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="a-time">Time limit (minutes)</label>
            <input id="a-time" type="number" min={1} max={600}
                   value={assessment.time_limit_minutes ?? ''}
                   placeholder="No limit"
                   onChange={(e) => setAssessment({
                     ...assessment,
                     time_limit_minutes: e.target.value ? Number(e.target.value) : null })} />
          </div>
        </div>
        <div className="field">
          <label className="check" htmlFor="a-required">
            <input id="a-required" type="checkbox" checked={assessment.is_required_for_completion}
                   onChange={(e) => setAssessment({
                     ...assessment, is_required_for_completion: e.target.checked })} />
            <span className="check__box" aria-hidden="true" />
            <span>Must be passed before the course counts as complete</span>
          </label>
          <label className="check" htmlFor="a-published">
            <input id="a-published" type="checkbox" checked={assessment.is_published}
                   onChange={(e) => setAssessment({ ...assessment, is_published: e.target.checked })} />
            <span className="check__box" aria-hidden="true" />
            <span>Visible to learners
              <em className="field__hint">Leave off while you are still writing questions.</em>
            </span>
          </label>
        </div>
      </section>

      {questions.map((question, index) => (
        <section key={question.key} className="card quizedit">
          <div className="quizedit__head">
            <h3>Question {index + 1}</h3>
            {question.aiGenerated && (
              <span className="status-pill status-pill--amber"><Sparkles size={11} /> AI-written</span>
            )}
            <button type="button" className="icon-btn" aria-label="Delete question"
                    onClick={() => setQuestions((prev) => prev.filter((q) => q.key !== question.key))}>
              <Trash2 size={15} />
            </button>
          </div>

          <div className="field">
            <label htmlFor={`${question.key}-prompt`}>Question</label>
            <textarea id={`${question.key}-prompt`} rows={2} value={question.prompt}
                      onChange={(e) => update(question.key, { prompt: e.target.value })} />
            {fieldErrors[`questions.${index}.prompt`] && (
              <p className="field__error">{fieldErrors[`questions.${index}.prompt`]}</p>
            )}
          </div>

          <div className="grid-2">
            <div className="field">
              <label htmlFor={`${question.key}-kind`}>Type</label>
              <select id={`${question.key}-kind`} value={question.kind}
                      onChange={(e) => setKind(question.key, e.target.value as QuestionKind)}>
                <option value="single">Multiple choice (one answer)</option>
                <option value="multiple">Multiple select (several answers)</option>
                <option value="truefalse">True or false</option>
                <option value="short_answer">Short answer</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor={`${question.key}-marks`}>Marks</label>
              <input id={`${question.key}-marks`} type="number" min={1} value={question.marks}
                     onChange={(e) => update(question.key, { marks: Number(e.target.value) })} />
            </div>
          </div>

          {question.kind === 'short_answer' ? (
            <div className="field">
              <label htmlFor={`${question.key}-accepted`}>Accepted answers</label>
              <textarea id={`${question.key}-accepted`} rows={3}
                        value={question.correct.join('\n')}
                        onChange={(e) => update(question.key, {
                          correct: e.target.value.split('\n') })} />
              <p className="field__hint">One per line. Matching ignores case.</p>
            </div>
          ) : (
            <div className="field">
              <span className="field__label">
                Options &mdash; tick the correct {question.kind === 'multiple' ? 'answers' : 'answer'}
              </span>
              <div className="quizedit__options">
                {question.options.map((option, optionIndex) => (
                  <div key={option.id} className="quizedit__option">
                    <button type="button"
                            className={`quizedit__tick ${question.correct.includes(option.id) ? 'is-on' : ''}`}
                            aria-label={`Mark option ${option.id} correct`}
                            onClick={() => toggleCorrect(question, option.id)}>
                      {question.correct.includes(option.id) && <Check size={12} strokeWidth={3} />}
                    </button>
                    <input value={option.text} placeholder={`Option ${option.id.toUpperCase()}`}
                           disabled={question.kind === 'truefalse'}
                           onChange={(e) => update(question.key, {
                             options: question.options.map((o, i) =>
                               i === optionIndex ? { ...o, text: e.target.value } : o) })} />
                    {question.kind !== 'truefalse' && question.options.length > 2 && (
                      <button type="button" className="icon-btn" aria-label="Remove option"
                              onClick={() => update(question.key, {
                                options: question.options.filter((_, i) => i !== optionIndex),
                                correct: question.correct.filter((c) => c !== option.id) })}>
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {question.kind !== 'truefalse' && question.options.length < 8 && (
                <button type="button" className="cta"
                        onClick={() => update(question.key, {
                          options: [...question.options,
                                    { id: LETTERS[question.options.length], text: '' }] })}>
                  <Plus size={13} /> Add option
                </button>
              )}
              {fieldErrors[`questions.${index}.options`] && (
                <p className="field__error">{fieldErrors[`questions.${index}.options`]}</p>
              )}
              {fieldErrors[`questions.${index}.correct`] && (
                <p className="field__error">{fieldErrors[`questions.${index}.correct`]}</p>
              )}
            </div>
          )}

          <div className="field">
            <label htmlFor={`${question.key}-why`}>Feedback shown after submission</label>
            <input id={`${question.key}-why`} value={question.explanation}
                   onChange={(e) => update(question.key, { explanation: e.target.value })} />
          </div>
        </section>
      ))}

      <button type="button" className="btn btn--outline"
              onClick={() => setQuestions((prev) => [...prev, blankQuestion()])}>
        <Plus size={15} /> Add a question
      </button>

      {Object.keys(fieldErrors).length > 0 && (
        <div className="card notice notice--orange">
          <AlertTriangle size={18} />
          <p className="small">Some questions need attention before this can be saved.</p>
        </div>
      )}
      {error && <ErrorMsg text={error} />}

      <div className="studioform__actions">
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Saving...' : existing ? 'Save assessment' : 'Create assessment'}
        </button>
        {existing && (
          <button type="button" className="btn btn--outline" onClick={() => void remove()}>
            Delete assessment
          </button>
        )}
      </div>
    </form>
  );
}
