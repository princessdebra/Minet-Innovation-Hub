import { FormEvent, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Ban, FileText, Info, RotateCcw, Sparkles, Trash2, Upload } from 'lucide-react';
import { ApiError, api } from '../../../api/client';
import { JOB_STATUS_LABEL, STEP_LABEL, formatBytes, formatDate,
         type AdminCourse, type GenerationJob, type ImportReport,
         type SourceMaterial, type StudioSettings } from '../../../api/lms';
import { ErrorMsg } from '../../../components/Bits';

const ACTIVE: GenerationJob['status'][] = ['queued', 'processing', 'generated', 'importing'];
const POLL_MS = 5000;

const JOB_COLOR: Record<string, string> = {
  queued: 'slate', processing: 'sky', generated: 'amber', importing: 'sky',
  imported: 'emerald', failed: 'orange', cancelled: 'slate', draft: 'slate',
};

function ReportSummary({ report }: { report: ImportReport }) {
  return (
    <div className="importreport">
      <p className="small">
        Imported <strong>{report.lessons}</strong> lesson{report.lessons === 1 ? '' : 's'},{' '}
        <strong>{report.blocks}</strong> content block{report.blocks === 1 ? '' : 's'} and{' '}
        <strong>{report.media_files}</strong> media file{report.media_files === 1 ? '' : 's'}
        {report.media_bytes > 0 && ` (${formatBytes(report.media_bytes)})`}.
      </p>
      {report.already_imported && (
        <p className="small jobpanel__error">
          Already imported, so nothing was added. Tick &ldquo;Replace&rdquo; below and upload again
          to overwrite it (your edits to that content would be lost).
        </p>
      )}
      {report.warnings.length > 0 && (
        <ul className="importreport__list">
          {report.warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}
      {report.unsupported.length > 0 && (
        <details className="importreport__details">
          <summary>{report.unsupported.length} item(s) need review</summary>
          <ul className="importreport__list">
            {report.unsupported.slice(0, 25).map((u, i) => (
              <li key={i}><strong>{u.kind.replace(/_/g, ' ')}:</strong> {u.detail}</li>
            ))}
          </ul>
        </details>
      )}
      {report.skipped_files.length > 0 && (
        <details className="importreport__details">
          <summary>{report.skipped_files.length} file(s) skipped</summary>
          <ul className="importreport__list">
            {report.skipped_files.slice(0, 25).map((s, i) => (
              <li key={i}><strong>{s.name}</strong> &mdash; {s.reason}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function GenerateTab({ course, settings, onChanged }: {
  course: AdminCourse; settings: StudioSettings | null; onChanged: (message?: string) => void;
}) {
  const materials = course.materials ?? [];
  const jobs = course.jobs ?? [];
  const activeJob = jobs.find((j) => ACTIVE.includes(j.status)) ?? null;

  const [live, setLive] = useState<GenerationJob | null>(activeJob);
  const [selected, setSelected] = useState<number[]>(materials.map((m) => m.id));
  const [instructions, setInstructions] = useState('');
  const [sensitivity, setSensitivity] = useState('internal');
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [replaceImport, setReplaceImport] = useState(false);
  const materialInput = useRef<HTMLInputElement>(null);
  const exportInput = useRef<HTMLInputElement>(null);

  // Poll while a job is running. The admin can leave the page; the job keeps going.
  useEffect(() => {
    setLive(activeJob);
    if (!activeJob || activeJob.step === 'awaiting_export') return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.get<GenerationJob>(`/lms/admin/generation-jobs/${activeJob.id}`);
        setLive(fresh);
        if (!ACTIVE.includes(fresh.status) || fresh.step === 'awaiting_export') {
          clearInterval(timer);
          onChanged();
        }
      } catch { /* transient: keep the last known state and try again */ }
    }, POLL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJob?.id, activeJob?.step]);

  async function uploadMaterial(file: File) {
    setError(null); setUploadPercent(0);
    const body = new FormData();
    body.append('file', file);
    body.append('sensitivity', sensitivity);
    try {
      const created = await api.upload<SourceMaterial>(
        `/lms/admin/courses/${course.id}/materials`, body, setUploadPercent);
      setSelected((prev) => [...prev, created.id]);
      onChanged('Material uploaded.');
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.errors.file || err.message) : 'Could not upload the file.');
    } finally {
      setUploadPercent(null);
    }
  }

  async function removeMaterial(id: number) {
    setError(null);
    try {
      await api.del(`/lms/admin/materials/${id}`);
      setSelected((prev) => prev.filter((m) => m !== id));
      onChanged('Material removed.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not remove the material.');
    }
  }

  async function generate(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const job = await api.post<GenerationJob>(`/lms/admin/courses/${course.id}/generate`, {
        instructions: instructions.trim(), material_ids: selected,
      });
      setLive(job);
      setInstructions('');
      onChanged('Generation queued.');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.errors.material_ids || err.errors.instructions || err.message);
      } else setError('Could not start generation.');
    } finally {
      setBusy(false);
    }
  }

  async function act(jobId: number, action: 'retry' | 'cancel') {
    setError(null);
    try {
      setLive(await api.post<GenerationJob>(`/lms/admin/generation-jobs/${jobId}/${action}`));
      onChanged(action === 'retry' ? 'Job re-queued.' : 'Job cancelled.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action} the job.`);
    }
  }

  async function importExport(file: File) {
    setError(null); setUploadPercent(0); setImportReport(null);
    const body = new FormData();
    body.append('file', file);
    if (live?.id) body.append('job_id', String(live.id));
    if (replaceImport) body.append('replace', 'true');
    try {
      const result = await api.upload<{ report: ImportReport }>(
        `/lms/admin/courses/${course.id}/import`, body, setUploadPercent);
      setImportReport(result.report);
      onChanged('Export imported.');
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.errors.file || err.message) : 'Could not import the export.');
    } finally {
      setUploadPercent(null);
    }
  }

  const generationReady = settings?.openmaic_configured && settings.openmaic.reachable;
  const awaitingExport = live?.step === 'awaiting_export'
    || (live?.status === 'generated' && live?.step !== 'importing');

  return (
    <>
      {/* ------------------------------------------------ source material -- */}
      <section className="card">
        <div className="records__head">
          <h2 className="card-title">Source material</h2>
          <span className="small muted">
            PDF, PPTX, DOCX, XLSX, images, TXT, MD, CSV, audio and video
          </span>
        </div>

        {materials.length === 0 && (
          <p className="muted small">
            No material uploaded yet. The AI uses these documents as the source for the course.
          </p>
        )}

        {materials.length > 0 && (
          <ul className="materiallist">
            {materials.map((material) => (
              <li key={material.id}>
                <label className="check">
                  <input type="checkbox" checked={selected.includes(material.id)}
                         onChange={(e) => setSelected((prev) => e.target.checked
                           ? [...prev, material.id]
                           : prev.filter((m) => m !== material.id))} />
                  <span className="check__box" aria-hidden="true" />
                  <span className="materiallist__body">
                    <FileText size={15} />
                    <span>
                      <strong>{material.asset?.filename ?? 'File'}</strong>
                      <em>
                        {material.asset && formatBytes(material.asset.size_bytes)}
                        {' • '}{material.sensitivity}
                        {material.openmaic_material_id && ' • sent to OpenMAIC'}
                      </em>
                    </span>
                  </span>
                </label>
                {material.sensitivity === 'confidential' && (
                  <span className="status-pill status-pill--orange">Blocked from AI</span>
                )}
                <button type="button" className="icon-btn" aria-label="Remove material"
                        onClick={() => void removeMaterial(material.id)}>
                  <Trash2 size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="uploadrow">
          <label className="field uploadrow__sensitivity">
            <span className="small muted">Classification</span>
            <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
              {(settings?.sensitivities ?? ['public', 'internal', 'confidential']).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <input ref={materialInput} type="file" hidden
                 onChange={(e) => {
                   const file = e.target.files?.[0];
                   if (file) void uploadMaterial(file);
                   e.target.value = '';
                 }} />
          <button type="button" className="btn btn--outline"
                  onClick={() => materialInput.current?.click()}
                  disabled={uploadPercent !== null}>
            <Upload size={15} /> Upload document
          </button>
          {uploadPercent !== null && (
            <span className="uploadrow__progress">
              <span style={{ width: `${uploadPercent}%` }} />
              <em>{uploadPercent}%</em>
            </span>
          )}
        </div>

        {sensitivity === 'confidential' && (
          <p className="small muted notice-inline">
            <Info size={13} /> Confidential documents are stored in Minet but are never sent to
            the AI provider. Use them for a manually authored course.
          </p>
        )}
      </section>

      {/* ------------------------------------------------------ generation -- */}
      <section className="card">
        <h2 className="card-title"><Sparkles size={16} /> Generate with AI</h2>

        {!settings?.openmaic_configured && (
          <div className="notice notice--amber notice--inline">
            <AlertTriangle size={16} />
            <p className="small">
              AI generation is not configured. Set <code>OPENMAIC_BASE_URL</code> in
              <code> backend/.env</code>. You can still import an export archive below.
            </p>
          </div>
        )}
        {settings?.openmaic_configured && !settings.openmaic.reachable && (
          <div className="notice notice--orange notice--inline">
            <AlertTriangle size={16} />
            <p className="small">OpenMAIC is not reachable: {settings.openmaic.detail}</p>
          </div>
        )}

        {live && ACTIVE.includes(live.status) ? (
          <div className="jobpanel">
            <div className="jobpanel__head">
              <span className={`status-pill status-pill--${JOB_COLOR[live.status]}`}>
                {JOB_STATUS_LABEL[live.status]}
              </span>
              <span className="small muted">
                {STEP_LABEL[live.step ?? ''] ?? live.step ?? ''}
              </span>
              <button type="button" className="btn btn--outline btn--compact"
                      onClick={() => void act(live.id, 'cancel')}>
                <Ban size={13} /> Cancel
              </button>
            </div>
            <div className="jobpanel__bar">
              <span style={{ width: `${live.progress}%` }} />
            </div>
            <p className="small muted">{live.message}</p>
            <p className="small muted">
              Generation usually takes several minutes. You can leave this page &mdash; the job
              keeps running and its state is shown here when you come back.
            </p>
            {live.last_error && (
              <p className="small jobpanel__error">{live.last_error}</p>
            )}
          </div>
        ) : (
          <form onSubmit={generate} className="studioform">
            <div className="field">
              <label htmlFor="g-instructions">What should the AI produce?</label>
              <textarea id="g-instructions" rows={4} value={instructions} minLength={10}
                        onChange={(e) => setInstructions(e.target.value)}
                        placeholder="e.g. Build a six-lesson course covering the claims triage process in the handbook. Use short lessons with practical examples for new colleagues." />
              <p className="field__hint">
                The course title, audience, level and objectives are sent with this brief.
              </p>
            </div>
            {error && <ErrorMsg text={error} />}
            <div className="studioform__actions">
              <button type="submit" className="btn btn--primary"
                      disabled={busy || !generationReady || instructions.trim().length < 10}>
                <Sparkles size={15} /> {busy ? 'Queueing...' : 'Start generation'}
              </button>
              <span className="small muted">
                {selected.length} of {materials.length} document{materials.length === 1 ? '' : 's'} selected
              </span>
            </div>
          </form>
        )}
      </section>

      {/* ---------------------------------------------------- export import -- */}
      <section className={`card ${awaitingExport ? 'card--accent' : ''}`}>
        <h2 className="card-title">Import an export archive</h2>
        {awaitingExport && (
          <div className="notice notice--amber notice--inline">
            <AlertTriangle size={16} />
            <p className="small">{live?.message}</p>
          </div>
        )}
        <p className="muted small">
          OpenMAIC builds its export files in the browser, so Minet cannot download them
          automatically. Open the generated classroom in OpenMAIC, export it, then upload the
          file here. Everything after that is Minet&rsquo;s: content, media, progress and
          certificates.
        </p>
        <label className="check">
          <input type="checkbox" checked={replaceImport}
                 onChange={(e) => setReplaceImport(e.target.checked)} />
          <span className="check__box" aria-hidden="true" />
          <span>Replace content previously imported from this export
            <em className="field__hint">Off by default so re-uploading never duplicates lessons.</em>
          </span>
        </label>
        <div className="uploadrow">
          <input ref={exportInput} type="file" accept=".zip,.maic.zip,application/zip" hidden
                 onChange={(e) => {
                   const file = e.target.files?.[0];
                   if (file) void importExport(file);
                   e.target.value = '';
                 }} />
          <button type="button" className="btn btn--outline"
                  onClick={() => exportInput.current?.click()}
                  disabled={uploadPercent !== null}>
            <Upload size={15} /> Upload export (.zip)
          </button>
          {uploadPercent !== null && (
            <span className="uploadrow__progress">
              <span style={{ width: `${uploadPercent}%` }} />
              <em>{uploadPercent}%</em>
            </span>
          )}
        </div>
        {importReport && <ReportSummary report={importReport} />}
        {error && <ErrorMsg text={error} />}
      </section>

      {/* ------------------------------------------------------- job history -- */}
      {jobs.length > 0 && (
        <section className="card table-wrap">
          <div className="records__head records__head--pad">
            <h2 className="card-title">Generation history</h2>
          </div>
          <table className="table">
            <thead>
              <tr><th>Started</th><th>Status</th><th>Instructions</th><th>Result</th><th /></tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="muted">{formatDate(job.created_at) || '—'}</td>
                  <td>
                    <span className={`status-pill status-pill--${JOB_COLOR[job.status]}`}>
                      {JOB_STATUS_LABEL[job.status]}
                    </span>
                  </td>
                  <td>
                    <span className="table__sub">{job.instructions.slice(0, 120)}
                      {job.instructions.length > 120 && '...'}</span>
                  </td>
                  <td>
                    {job.import_report
                      ? <span className="small">{job.import_report.lessons} lessons, {job.import_report.blocks} blocks</span>
                      : <span className="small muted">{job.last_error ? job.last_error.slice(0, 90) : '—'}</span>}
                  </td>
                  <td className="table__action">
                    {(job.status === 'failed' || job.status === 'cancelled') && (
                      <button className="cta" onClick={() => void act(job.id, 'retry')}>
                        <RotateCcw size={13} /> Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
