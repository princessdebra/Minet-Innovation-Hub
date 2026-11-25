import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, BarChart3, Plus, Search, Sparkles } from 'lucide-react';
import { ApiError, api, useApi } from '../../api/client';
import { COURSE_STATUS_LABEL, formatDate, formatMinutes,
         type AdminCourse, type AdminCourseList, type StudioSettings } from '../../api/lms';
import { PageHeader } from '../../components/PageHeader';
import { Modal } from '../../components/Modal';
import { ErrorMsg, Loading, Tabs } from '../../components/Bits';

const STATUS_COLOR: Record<string, string> = {
  draft: 'slate', generating: 'sky', awaiting_review: 'amber',
  published: 'emerald', archived: 'slate',
};

type StatusFilter = 'all' | 'draft' | 'generating' | 'awaiting_review' | 'published' | 'archived';

const TABS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'draft', label: 'Drafts' },
  { id: 'generating', label: 'Generating' },
  { id: 'awaiting_review', label: 'Awaiting review' },
  { id: 'published', label: 'Published' },
  { id: 'archived', label: 'Archived' },
];

function NewCourseModal({ settings, onClose }:
  { settings: StudioSettings | null; onClose: () => void }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState('Foundation');
  const [audience, setAudience] = useState('');
  const [objectives, setObjectives] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setErrors({}); setMessage(null);
    try {
      const created = await api.post<AdminCourse>('/lms/admin/courses', {
        title: title.trim(),
        summary: summary.trim() || null,
        category: category.trim() || null,
        difficulty,
        target_audience: audience.trim() || null,
        objectives: objectives.split('\n').map((o) => o.trim()).filter(Boolean),
      });
      navigate(`/admin/course-studio/${created.id}?tab=generate`);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.errors);
        setMessage(Object.keys(err.errors).length ? null : err.message);
      } else {
        setMessage('Could not create the course.');
      }
      setBusy(false);
    }
  }

  return (
    <Modal title="Create a course" onClose={onClose} wide>
      <form onSubmit={submit} className="studioform">
        <div className="field">
          <label htmlFor="title">Course title</label>
          <input id="title" value={title} onChange={(e) => setTitle(e.target.value)}
                 placeholder="e.g. Claims handling fundamentals" required minLength={3} />
          {errors.title && <p className="field__error">{errors.title}</p>}
        </div>
        <div className="field">
          <label htmlFor="summary">Short summary</label>
          <input id="summary" value={summary} maxLength={400}
                 onChange={(e) => setSummary(e.target.value)}
                 placeholder="One line employees will see in the catalogue" />
          <p className="field__hint">Needed before the course can be published.</p>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="category">Category</label>
            <input id="category" value={category} onChange={(e) => setCategory(e.target.value)}
                   placeholder="e.g. Claims" />
          </div>
          <div className="field">
            <label htmlFor="difficulty">Difficulty</label>
            <select id="difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              {(settings?.difficulties ?? ['Foundation', 'Intermediate', 'Advanced']).map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="audience">Target audience</label>
          <input id="audience" value={audience} onChange={(e) => setAudience(e.target.value)}
                 placeholder="e.g. New colleagues in the claims team" />
        </div>
        <div className="field">
          <label htmlFor="objectives">Learning objectives</label>
          <textarea id="objectives" rows={4} value={objectives}
                    onChange={(e) => setObjectives(e.target.value)}
                    placeholder={'One per line\nExplain the claims journey\nApply the triage rules'} />
        </div>
        {message && <p className="field__error">{message}</p>}
        <div className="studioform__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? 'Creating...' : 'Create and add material'}
          </button>
          <button type="button" className="btn btn--outline" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

export function CourseStudio() {
  const [status, setStatus] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [creating, setCreating] = useState(false);

  const params = new URLSearchParams({ per_page: '50' });
  if (status !== 'all') params.set('status', status);
  if (query.trim()) params.set('search', query.trim());

  const { data, error, loading, reload } = useApi<AdminCourseList>(`/lms/admin/courses?${params}`);
  const settings = useApi<StudioSettings>('/lms/admin/settings');

  const openmaic = settings.data?.openmaic;

  return (
    <>
      <PageHeader title="AI Course Studio"
                  subtitle="Create courses, generate content with AI, review it and publish to the Innovation Academy." />

      {settings.data && !settings.data.openmaic_configured && (
        <div className="card notice notice--amber">
          <AlertTriangle size={18} />
          <div>
            <strong>AI generation is not configured.</strong>
            <p className="small">
              Set <code>OPENMAIC_BASE_URL</code> in <code>backend/.env</code> to enable it.
              You can still build courses by hand and import an export archive.
            </p>
          </div>
        </div>
      )}
      {settings.data?.openmaic_configured && openmaic && !openmaic.reachable && (
        <div className="card notice notice--orange">
          <AlertTriangle size={18} />
          <div>
            <strong>OpenMAIC is configured but not reachable.</strong>
            <p className="small">{openmaic.detail}</p>
          </div>
        </div>
      )}

      <section className="card finder">
        <form className="finder__search" onSubmit={(e) => { e.preventDefault(); setQuery(search); }}>
          <Search size={16} strokeWidth={1.75} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
                 placeholder="Search courses" aria-label="Search courses" />
          <button type="submit" className="btn btn--outline btn--compact">Search</button>
        </form>
        <div className="finder__row">
          <Tabs tabs={TABS} value={status} onChange={setStatus} />
          <div className="finder__actions">
            <Link to="/admin/analytics" className="btn btn--outline btn--compact">
              <BarChart3 size={14} /> Analytics
            </Link>
            <button className="btn btn--primary btn--compact" onClick={() => setCreating(true)}>
              <Plus size={15} /> New course
            </button>
          </div>
        </div>
      </section>

      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading text="Loading courses..." />}

      {data && data.courses.length === 0 && (
        <div className="card empty">
          <strong>No courses here yet.</strong>
          <p className="muted">
            {status === 'all' && !query
              ? 'Create your first course to get started.'
              : 'No courses match these filters.'}
          </p>
        </div>
      )}

      {data && data.courses.length > 0 && (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Course</th><th>Status</th><th>Category</th>
                <th className="table__num">Lessons</th><th>Updated</th><th />
              </tr>
            </thead>
            <tbody>
              {data.courses.map((course) => (
                <tr key={course.id}>
                  <td>
                    <Link to={`/admin/course-studio/${course.id}`} className="table__title">
                      {course.title}
                    </Link>
                    <span className="table__sub">
                      {course.origin === 'ai_generated' && (
                        <><Sparkles size={10} /> AI-assisted &bull; </>
                      )}
                      {formatMinutes(course.estimated_minutes) || 'Duration not set'}
                      {course.version > 1 && ` • v${course.version}`}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill status-pill--${STATUS_COLOR[course.status] ?? 'slate'}`}>
                      {COURSE_STATUS_LABEL[course.status]}
                    </span>
                    {course.has_active_job && (
                      <span className="small muted table__sub">Generation running</span>
                    )}
                  </td>
                  <td className="muted">{course.category || '—'}</td>
                  <td className="table__num">{course.lesson_count ?? 0}</td>
                  <td className="muted">{formatDate(course.updated_at)}</td>
                  <td className="table__action">
                    <Link to={`/admin/course-studio/${course.id}`} className="cta">Open</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <NewCourseModal settings={settings.data} onClose={() => { setCreating(false); reload(); }} />
      )}
    </>
  );
}
