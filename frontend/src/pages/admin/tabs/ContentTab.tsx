import { FormEvent, useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from 'lucide-react';
import { ApiError, api, useApi } from '../../../api/client';
import { formatMinutes, type AdminCourse, type ContentBlock,
         type LessonSummary, type ModuleSummary } from '../../../api/lms';
import { Modal } from '../../../components/Modal';
import { ErrorMsg, Loading } from '../../../components/Bits';
import { ReviewableBlock } from '../../../components/lms/BlockRenderer';

const EDITABLE_TEXT: ContentBlock['block_type'][] = ['rich_text', 'slide', 'notes', 'html_fallback'];

/* ------------------------------------------------------------- block editor -- */

function BlockEditor({ block, onClose, onSaved }: {
  block: ContentBlock; onClose: () => void; onSaved: () => void;
}) {
  const data = block.data || {};
  const [title, setTitle] = useState(block.title ?? '');
  const [html, setHtml] = useState(typeof data.html === 'string' ? data.html : '');
  const [text, setText] = useState(typeof data.text === 'string' ? data.text : '');
  const [items, setItems] = useState(
    Array.isArray(data.items) ? (data.items as string[]).join('\n') : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isList = block.block_type === 'key_takeaways';
  const isText = EDITABLE_TEXT.includes(block.block_type);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      await api.patch(`/lms/admin/blocks/${block.id}`, {
        block_type: block.block_type,
        title: title.trim() || null,
        data: {
          ...data,
          ...(isText ? { html, text } : {}),
          ...(isList ? { items: items.split('\n').map((i) => i.trim()).filter(Boolean) } : {}),
        },
        asset_id: typeof data.asset_id === 'number' ? data.asset_id : null,
        needs_review: false,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save this block.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Edit ${block.block_type.replace(/_/g, ' ')}`} onClose={onClose} wide>
      <form onSubmit={save} className="studioform">
        {block.import_note && (
          <div className="notice notice--amber notice--inline">
            <AlertTriangle size={16} />
            <p className="small">{block.import_note}</p>
          </div>
        )}
        <div className="field">
          <label htmlFor="b-title">Block title</label>
          <input id="b-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        {isText && (
          <>
            <div className="field">
              <label htmlFor="b-html">Content (HTML)</label>
              <textarea id="b-html" rows={10} value={html} onChange={(e) => setHtml(e.target.value)} />
              <p className="field__hint">
                Sanitised on save. Scripts, iframes and event handlers are removed.
              </p>
            </div>
            <div className="field">
              <label htmlFor="b-text">Plain-text version</label>
              <textarea id="b-text" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
              <p className="field__hint">Used for search and duration estimates.</p>
            </div>
          </>
        )}
        {isList && (
          <div className="field">
            <label htmlFor="b-items">Items</label>
            <textarea id="b-items" rows={6} value={items} onChange={(e) => setItems(e.target.value)} />
            <p className="field__hint">One per line.</p>
          </div>
        )}
        {!isText && !isList && (
          <p className="muted small">
            This block type has no text to edit here. Delete it if it is not wanted, or replace
            the media from the lesson.
          </p>
        )}
        {error && <ErrorMsg text={error} />}
        <div className="studioform__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? 'Saving...' : 'Save and mark reviewed'}
          </button>
          <button type="button" className="btn btn--outline" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------ lesson editor -- */

function LessonEditor({ lessonId, onClose, onChanged }: {
  lessonId: number; onClose: () => void; onChanged: () => void;
}) {
  // Admin route: serves drafts too, and includes the review flags.
  const { data, error, loading, reload } = useApi<{ lesson: LessonSummary & { blocks: ContentBlock[] } }>(
    `/lms/admin/lessons/${lessonId}`);
  const [editing, setEditing] = useState<ContentBlock | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function removeBlock(blockId: number) {
    setActionError(null);
    try {
      await api.del(`/lms/admin/blocks/${blockId}`);
      reload();
      onChanged();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not delete the block.');
    }
  }

  async function addBlock() {
    setActionError(null);
    try {
      await api.post(`/lms/admin/lessons/${lessonId}/blocks`, {
        block_type: 'rich_text', title: 'New section',
        data: { html: '<p>Write the lesson content here.</p>', text: 'Write the lesson content here.' },
      });
      reload();
      onChanged();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not add a block.');
    }
  }

  const lesson = data?.lesson;
  return (
    <Modal title={lesson?.title ?? 'Lesson'} onClose={onClose} wide>
      {error && <ErrorMsg text={error} />}
      {loading && !lesson && <Loading />}
      {lesson && (
        <div className="lessoneditor">
          <p className="small muted">
            {lesson.blocks.length} block{lesson.blocks.length === 1 ? '' : 's'}
            {' • '}{formatMinutes(lesson.estimated_minutes)}
          </p>
          {actionError && <ErrorMsg text={actionError} />}
          {lesson.blocks.map((block) => (
            <div key={block.id} className="lessoneditor__block">
              <ReviewableBlock block={block} />
              <div className="lessoneditor__tools">
                <button className="icon-btn" aria-label="Edit block" onClick={() => setEditing(block)}>
                  <Pencil size={15} />
                </button>
                <button className="icon-btn" aria-label="Delete block"
                        onClick={() => void removeBlock(block.id)}>
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
          <button className="btn btn--outline" onClick={() => void addBlock()}>
            <Plus size={15} /> Add a text block
          </button>
        </div>
      )}
      {editing && (
        <BlockEditor block={editing} onClose={() => setEditing(null)}
                     onSaved={() => { reload(); onChanged(); }} />
      )}
    </Modal>
  );
}

/* --------------------------------------------------------------- main tab -- */

export function ContentTab({ course, onChanged }: {
  course: AdminCourse; onChanged: (message?: string) => void;
}) {
  const modules = course.modules ?? [];
  const [openLesson, setOpenLesson] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  async function addModule(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/lms/admin/courses/${course.id}/modules`, {
        title: newTitle.trim() || 'New module', description: null,
        estimated_minutes: 0, is_published: true,
      });
      setNewTitle(''); setAdding(false);
      onChanged('Module added.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add the module.');
    }
  }

  async function addLesson(moduleId: number) {
    setError(null);
    try {
      await api.post(`/lms/admin/modules/${moduleId}/lessons`, {
        title: 'New lesson', estimated_minutes: 5, completion_rule: 'view', is_published: true,
      });
      onChanged('Lesson added.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add the lesson.');
    }
  }

  async function removeModule(moduleId: number) {
    setError(null);
    try {
      await api.del(`/lms/admin/modules/${moduleId}`);
      onChanged('Module deleted.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the module.');
    }
  }

  async function removeLesson(lessonId: number) {
    setError(null);
    try {
      await api.del(`/lms/admin/lessons/${lessonId}`);
      onChanged('Lesson deleted.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the lesson.');
    }
  }

  async function move(list: { id: number }[], index: number, delta: number, url: string) {
    const next = [...list];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setError(null);
    try {
      await api.post(url, { ordered_ids: next.map((item) => item.id) });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reorder.');
    }
  }

  return (
    <>
      {error && <ErrorMsg text={error} />}

      {modules.length === 0 && (
        <div className="card empty">
          <strong>This course has no content yet.</strong>
          <p className="muted">
            Generate it with AI, import an export archive, or add a module by hand below.
          </p>
        </div>
      )}

      {modules.map((module: ModuleSummary, moduleIndex) => (
        <section key={module.id} className="card modulecard modulecard--admin">
          <div className="modulecard__head">
            <h3>{module.title}</h3>
            <div className="modulecard__tools">
              <button className="icon-btn" aria-label="Move module up"
                      disabled={moduleIndex === 0}
                      onClick={() => void move(modules, moduleIndex, -1,
                        `/lms/admin/courses/${course.id}/modules/reorder`)}>
                <ChevronUp size={15} />
              </button>
              <button className="icon-btn" aria-label="Move module down"
                      disabled={moduleIndex === modules.length - 1}
                      onClick={() => void move(modules, moduleIndex, 1,
                        `/lms/admin/courses/${course.id}/modules/reorder`)}>
                <ChevronDown size={15} />
              </button>
              <button className="icon-btn" aria-label="Delete module"
                      onClick={() => void removeModule(module.id)}>
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          <ol className="lessonlist lessonlist--admin">
            {module.lessons.map((lesson, lessonIndex) => (
              <li key={lesson.id}>
                <button className="lessonlist__item" onClick={() => setOpenLesson(lesson.id)}>
                  <span className="lessonlist__text">
                    <strong>{lesson.title}</strong>
                    <em>
                      {formatMinutes(lesson.estimated_minutes)}
                      {lesson.completion_rule === 'assessment' && ' • assessment required'}
                      {!lesson.is_published && ' • hidden'}
                    </em>
                  </span>
                  {lesson.needs_review && (
                    <span className="status-pill status-pill--amber">Needs review</span>
                  )}
                  <Pencil size={14} />
                </button>
                <div className="lessonlist__tools">
                  <button className="icon-btn" aria-label="Move lesson up"
                          disabled={lessonIndex === 0}
                          onClick={() => void move(module.lessons, lessonIndex, -1,
                            `/lms/admin/modules/${module.id}/lessons/reorder`)}>
                    <ChevronUp size={14} />
                  </button>
                  <button className="icon-btn" aria-label="Move lesson down"
                          disabled={lessonIndex === module.lessons.length - 1}
                          onClick={() => void move(module.lessons, lessonIndex, 1,
                            `/lms/admin/modules/${module.id}/lessons/reorder`)}>
                    <ChevronDown size={14} />
                  </button>
                  <button className="icon-btn" aria-label="Delete lesson"
                          onClick={() => void removeLesson(lesson.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            ))}
          </ol>

          <button className="cta" onClick={() => void addLesson(module.id)}>
            <Plus size={14} /> Add a lesson
          </button>
        </section>
      ))}

      {adding ? (
        <form className="card studioform" onSubmit={addModule}>
          <div className="field">
            <label htmlFor="m-title">Module title</label>
            <input id="m-title" value={newTitle} autoFocus
                   onChange={(e) => setNewTitle(e.target.value)} placeholder="e.g. Getting started" />
          </div>
          <div className="studioform__actions">
            <button type="submit" className="btn btn--primary">Add module</button>
            <button type="button" className="btn btn--outline" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button className="btn btn--outline" onClick={() => setAdding(true)}>
          <Plus size={15} /> Add a module
        </button>
      )}

      {openLesson !== null && (
        <LessonEditor lessonId={openLesson} onClose={() => setOpenLesson(null)}
                      onChanged={() => onChanged()} />
      )}
    </>
  );
}
