import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Archive, Check, Eye, Send, Undo2 } from 'lucide-react';
import { ApiError, api, useApi } from '../../../api/client';
import { formatMinutes, type AdminCourse, type ModuleSummary } from '../../../api/lms';
import { BlockRenderer } from '../../../components/lms/BlockRenderer';
import { ErrorMsg, Loading } from '../../../components/Bits';

interface PreviewResponse {
  course: AdminCourse;
  modules: ModuleSummary[];
  preview: true;
}

export function PublishTab({ course, onChanged }: {
  course: AdminCourse; onChanged: (message?: string) => void;
}) {
  const preview = useApi<PreviewResponse>(`/lms/admin/courses/${course.id}/preview`);
  const [acknowledged, setAcknowledged] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [previewLesson, setPreviewLesson] = useState<number | null>(null);

  const lessons = (course.modules ?? []).flatMap((m) => m.lessons);
  const needsReview = (course.review?.lessons_needing_review ?? 0)
    + (course.review?.blocks_needing_review ?? 0);
  const isAi = course.origin === 'ai_generated';

  const checks = [
    { ok: lessons.length > 0, label: `At least one lesson (${lessons.length})` },
    { ok: Boolean(course.summary || course.description), label: 'A summary employees can read' },
    { ok: needsReview === 0, label: needsReview === 0
      ? 'No content flagged for review'
      : `${needsReview} item(s) still flagged for review`, soft: true },
    { ok: !course.has_active_job, label: 'No generation job running' },
  ];

  async function run(action: 'publish' | 'unpublish' | 'archive') {
    setBusy(true); setError(null); setErrors({});
    try {
      await api.post(`/lms/admin/courses/${course.id}/${action}`,
        action === 'publish'
          ? { acknowledged_ai_review: acknowledged, approval_note: note.trim() || null }
          : {});
      onChanged(action === 'publish' ? 'Course published.'
        : action === 'unpublish' ? 'Course withdrawn.' : 'Course archived.');
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.errors).length) setErrors(err.errors);
      else setError(err instanceof ApiError ? err.message : `Could not ${action} the course.`);
    } finally {
      setBusy(false);
    }
  }

  const activeLesson = preview.data?.modules
    .flatMap((m) => m.lessons)
    .find((l) => l.id === previewLesson);

  return (
    <>
      <section className="card">
        <h2 className="card-title">Before publishing</h2>
        <ul className="checklist">
          {checks.map((check, i) => (
            <li key={i} className={check.ok ? 'is-ok' : check.soft ? 'is-warn' : 'is-blocked'}>
              {check.ok ? <Check size={14} strokeWidth={3} /> : <AlertTriangle size={14} />}
              {check.label}
            </li>
          ))}
        </ul>
        {needsReview > 0 && (
          <p className="small muted">
            Flagged content does not block publishing, but it is content the importer could not
            map cleanly. Check it in the{' '}
            <Link to={`/admin/course-studio/${course.id}?tab=content`}>Content tab</Link> first.
          </p>
        )}

        {isAi && (
          <div className="field">
            <label className="check" htmlFor="ack">
              <input id="ack" type="checkbox" checked={acknowledged}
                     onChange={(e) => setAcknowledged(e.target.checked)} />
              <span className="check__box" aria-hidden="true" />
              <span>
                I have reviewed the AI-generated content for accuracy and confirmed it contains
                no confidential material.
                <em className="field__hint">
                  Required for AI-assisted courses. Your name and today&rsquo;s date are recorded
                  on the course.
                </em>
              </span>
            </label>
            {errors.acknowledged_ai_review && (
              <p className="field__error">{errors.acknowledged_ai_review}</p>
            )}
          </div>
        )}

        <div className="field">
          <label htmlFor="p-note">Approval note (optional)</label>
          <input id="p-note" value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="e.g. Reviewed with the claims team on 24 November" />
        </div>

        {errors.modules && <p className="field__error">{errors.modules}</p>}
        {errors.summary && <p className="field__error">{errors.summary}</p>}
        {errors.generation && <p className="field__error">{errors.generation}</p>}
        {errors.media && <p className="field__error">{errors.media}</p>}
        {Object.entries(errors)
          .filter(([key]) => !['acknowledged_ai_review', 'modules', 'summary', 'generation', 'media'].includes(key))
          .map(([key, message]) => <p key={key} className="field__error">{message}</p>)}
        {error && <ErrorMsg text={error} />}

        <div className="studioform__actions">
          {course.status !== 'published' ? (
            <button className="btn btn--primary" onClick={() => void run('publish')} disabled={busy}>
              <Send size={15} /> {busy ? 'Publishing...' : 'Publish to the Academy'}
            </button>
          ) : (
            <>
              <Link to={`/learn/courses/${course.id}`} className="btn btn--primary">
                <Eye size={15} /> View as a learner
              </Link>
              <button className="btn btn--outline" onClick={() => void run('unpublish')} disabled={busy}>
                <Undo2 size={15} /> Withdraw
              </button>
            </>
          )}
          {course.status !== 'archived' && (
            <button className="btn btn--outline" onClick={() => void run('archive')} disabled={busy}>
              <Archive size={15} /> Archive
            </button>
          )}
        </div>

        {course.status === 'published' && (
          <p className="small muted">
            Published {course.published_at ? new Date(course.published_at).toLocaleString() : ''}
            {course.version > 1 && ` • version ${course.version}`}.
            Publishing again after edits creates a new version; certificates already issued keep
            the version they were earned against.
          </p>
        )}
      </section>

      <h2 className="h2">Learner preview</h2>
      {preview.error && <ErrorMsg text={preview.error} />}
      {preview.loading && !preview.data && <Loading />}

      {preview.data && (
        <div className="previewgrid">
          <aside className="card previewnav">
            <h3 className="card-title">{preview.data.course.title}</h3>
            <p className="small muted">
              {lessons.length} lesson{lessons.length === 1 ? '' : 's'}
              {course.estimated_minutes > 0 && ` • ${formatMinutes(course.estimated_minutes)}`}
            </p>
            {preview.data.modules.map((module) => (
              <div key={module.id} className="previewnav__module">
                <strong>{module.title}</strong>
                <ul>
                  {module.lessons.map((lesson) => (
                    <li key={lesson.id}>
                      <button className={previewLesson === lesson.id ? 'is-active' : ''}
                              onClick={() => setPreviewLesson(lesson.id)}>
                        {lesson.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {preview.data.modules.length === 0 && (
              <p className="small muted">No published modules to preview yet.</p>
            )}
          </aside>

          <article className="card previewpane">
            {activeLesson ? (
              <>
                <h3>{activeLesson.title}</h3>
                {activeLesson.description && <p className="muted">{activeLesson.description}</p>}
                <PreviewBlocks lessonId={activeLesson.id} />
              </>
            ) : (
              <p className="muted">Select a lesson on the left to preview it exactly as an employee
                would see it.</p>
            )}
          </article>
        </div>
      )}
    </>
  );
}

function PreviewBlocks({ lessonId }: { lessonId: number }) {
  const { data, error, loading } = useApi<{ lesson: { blocks: Parameters<typeof BlockRenderer>[0]['block'][] } }>(
    `/lms/admin/lessons/${lessonId}`);
  if (error) return <ErrorMsg text={error} />;
  if (loading || !data) return <Loading />;
  if (!data.lesson.blocks.length) return <p className="muted small">This lesson has no content yet.</p>;
  return <>{data.lesson.blocks.map((block) => <BlockRenderer key={block.id} block={block} />)}</>;
}
