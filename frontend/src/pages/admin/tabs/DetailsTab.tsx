import { FormEvent, useRef, useState } from 'react';
import { Image as ImageIcon, Upload } from 'lucide-react';
import { ApiError, api } from '../../../api/client';
import type { AdminCourse, StudioSettings } from '../../../api/lms';
import { ErrorMsg } from '../../../components/Bits';

export function DetailsTab({ course, settings, onSaved }: {
  course: AdminCourse; settings: StudioSettings | null; onSaved: (message?: string) => void;
}) {
  const [form, setForm] = useState({
    title: course.title,
    summary: course.summary ?? '',
    description: course.description ?? '',
    category: course.category ?? '',
    difficulty: course.difficulty,
    target_audience: course.target_audience ?? '',
    tags: (course.tags ?? []).join(', '),
    objectives: (course.objectives ?? []).join('\n'),
    estimated_minutes: course.estimated_minutes,
    pass_requires_assessments: course.pass_requires_assessments,
  });
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setErrors({}); setMessage(null);
    try {
      await api.patch(`/lms/admin/courses/${course.id}`, {
        title: form.title.trim(),
        summary: form.summary.trim() || null,
        description: form.description.trim() || null,
        category: form.category.trim() || null,
        difficulty: form.difficulty,
        target_audience: form.target_audience.trim() || null,
        tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
        objectives: form.objectives.split('\n').map((o) => o.trim()).filter(Boolean),
        estimated_minutes: Number(form.estimated_minutes) || 0,
        pass_requires_assessments: form.pass_requires_assessments,
      });
      onSaved('Details saved.');
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.errors);
        if (!Object.keys(err.errors).length) setMessage(err.message);
      } else setMessage('Could not save the course.');
    } finally {
      setBusy(false);
    }
  }

  async function uploadThumbnail(file: File) {
    setMessage(null);
    const body = new FormData();
    body.append('file', file);
    try {
      await api.upload(`/lms/admin/courses/${course.id}/thumbnail`, body);
      onSaved('Thumbnail updated.');
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not upload the image.');
    }
  }

  return (
    <form className="card studioform" onSubmit={save}>
      <div className="field">
        <label htmlFor="d-title">Course title</label>
        <input id="d-title" value={form.title} onChange={(e) => set('title', e.target.value)}
               required minLength={3} />
        {errors.title && <p className="field__error">{errors.title}</p>}
      </div>

      <div className="field">
        <label htmlFor="d-summary">Short summary</label>
        <input id="d-summary" value={form.summary} maxLength={400}
               onChange={(e) => set('summary', e.target.value)} />
        <p className="field__hint">Shown in the catalogue. Required before publishing.</p>
        {errors.summary && <p className="field__error">{errors.summary}</p>}
      </div>

      <div className="field">
        <label htmlFor="d-description">Full description</label>
        <textarea id="d-description" rows={4} value={form.description}
                  onChange={(e) => set('description', e.target.value)} />
      </div>

      <div className="grid-3">
        <div className="field">
          <label htmlFor="d-category">Category</label>
          <input id="d-category" value={form.category}
                 onChange={(e) => set('category', e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="d-difficulty">Difficulty</label>
          <select id="d-difficulty" value={form.difficulty}
                  onChange={(e) => set('difficulty', e.target.value)}>
            {(settings?.difficulties ?? ['Foundation', 'Intermediate', 'Advanced']).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          {errors.difficulty && <p className="field__error">{errors.difficulty}</p>}
        </div>
        <div className="field">
          <label htmlFor="d-minutes">Estimated minutes</label>
          <input id="d-minutes" type="number" min={0} value={form.estimated_minutes}
                 onChange={(e) => set('estimated_minutes', Number(e.target.value))} />
          <p className="field__hint">Recalculated from lessons when you publish.</p>
        </div>
      </div>

      <div className="field">
        <label htmlFor="d-audience">Target audience</label>
        <input id="d-audience" value={form.target_audience}
               onChange={(e) => set('target_audience', e.target.value)} />
      </div>

      <div className="field">
        <label htmlFor="d-tags">Tags</label>
        <input id="d-tags" value={form.tags} onChange={(e) => set('tags', e.target.value)}
               placeholder="claims, triage, process" />
        <p className="field__hint">Comma separated.</p>
      </div>

      <div className="field">
        <label htmlFor="d-objectives">Learning objectives</label>
        <textarea id="d-objectives" rows={5} value={form.objectives}
                  onChange={(e) => set('objectives', e.target.value)} />
        <p className="field__hint">One per line. Used in the AI brief and shown to learners.</p>
      </div>

      <div className="field">
        <label className="check" htmlFor="d-gate">
          <input id="d-gate" type="checkbox" checked={form.pass_requires_assessments}
                 onChange={(e) => set('pass_requires_assessments', e.target.checked)} />
          <span className="check__box" aria-hidden="true" />
          <span>
            Require every assessment to be passed before the course counts as complete
            <em className="field__hint">Turn off for an informational course with no graded check.</em>
          </span>
        </label>
      </div>

      <div className="field">
        <span className="field__label">Course thumbnail</span>
        <div className="thumbrow">
          {course.thumbnail
            ? <img className="thumbrow__preview" src={course.thumbnail.url} alt="" />
            : <span className="thumbrow__placeholder"><ImageIcon size={20} /></span>}
          <input ref={fileInput} type="file" accept="image/*" hidden
                 onChange={(e) => {
                   const file = e.target.files?.[0];
                   if (file) void uploadThumbnail(file);
                   e.target.value = '';
                 }} />
          <button type="button" className="btn btn--outline btn--compact"
                  onClick={() => fileInput.current?.click()}>
            <Upload size={14} /> {course.thumbnail ? 'Replace image' : 'Upload image'}
          </button>
        </div>
      </div>

      {message && <ErrorMsg text={message} />}
      <div className="studioform__actions">
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? 'Saving...' : 'Save details'}
        </button>
      </div>
    </form>
  );
}
