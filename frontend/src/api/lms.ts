/** Types for the LMS API. Mirrors backend/app/lms_serializers.py. */

export type CourseStatus = 'draft' | 'generating' | 'awaiting_review' | 'published' | 'archived';
export type ProgressStatus = 'not_started' | 'in_progress' | 'completed';
export type JobStatus = 'draft' | 'queued' | 'processing' | 'generated' | 'importing'
  | 'imported' | 'failed' | 'cancelled';
export type BlockType = 'rich_text' | 'slide' | 'image' | 'audio' | 'video' | 'document'
  | 'diagram' | 'key_takeaways' | 'notes' | 'knowledge_check' | 'external_reference'
  | 'html_fallback' | 'unsupported';
export type QuestionKind = 'single' | 'multiple' | 'truefalse' | 'short_answer';

export interface AssetBrief {
  id: number; filename: string; mime_type: string; size_bytes: number;
  kind: string; url: string;
}

export interface ContentBlock {
  id: number;
  block_type: BlockType;
  title: string | null;
  position: number;
  data: Record<string, unknown>;
  needs_review?: boolean;
  import_note?: string | null;
  meta?: Record<string, unknown>;
}

export interface LessonSummary {
  id: number; module_id: number; title: string; description: string | null;
  position: number; lesson_type: string; estimated_minutes: number;
  objectives: string[]; completion_rule: 'view' | 'assessment';
  status?: ProgressStatus;
  is_published?: boolean; needs_review?: boolean;
  blocks?: ContentBlock[];
}

export interface ModuleSummary {
  id: number; course_id: number; title: string; description: string | null;
  position: number; estimated_minutes: number; is_published?: boolean;
  lessons: LessonSummary[];
}

export interface CourseCardData {
  id: number; slug: string; title: string; summary: string | null;
  category: string | null; tags: string[]; difficulty: string;
  estimated_minutes: number; origin: 'manual' | 'ai_generated';
  lesson_count: number; thumbnail: AssetBrief | null;
  status: ProgressStatus; progress_percent: number;
  last_accessed_at?: string | null;
}

export interface Enrollment {
  id: number; course_id: number; status: ProgressStatus;
  progress_percent: number; seconds_spent: number;
  enrolled_at: string; started_at: string | null;
  last_accessed_at: string | null; completed_at: string | null;
}

export interface Certificate {
  id: number; course_id: number; certificate_number: string;
  certificate_type: 'completion' | 'assessed_competency';
  verification_code: string; verification_url: string;
  course_title: string; recipient_name: string; course_version: number;
  score_percent: number | null; issued_at: string; revoked_at: string | null;
  is_valid: boolean; download_url: string;
}

export interface CatalogResponse {
  total: number; page: number; per_page: number;
  courses: CourseCardData[]; categories: string[];
}

export interface CourseDetailResponse {
  course: {
    id: number; slug: string; title: string; summary: string | null;
    description: string | null; objectives: string[]; category: string | null;
    tags: string[]; difficulty: string; estimated_minutes: number;
    origin: 'manual' | 'ai_generated'; ai_disclosure: string | null;
    version: number; thumbnail: AssetBrief | null;
  };
  modules: ModuleSummary[];
  enrollment: Enrollment | null;
  lesson_count: number;
  resume_lesson_id: number | null;
  requirements: {
    lessons: number;
    assessments: { id: number; title: string; pass_percent: number; required: boolean }[];
    blockers: string[];
  };
  certificate: Certificate | null;
}

export interface LessonResponse {
  lesson: LessonSummary & { blocks: ContentBlock[] };
  course: { id: number; title: string; slug: string; ai_disclosure: string | null };
  module: { id: number; title: string };
  navigation: {
    position: number; total: number;
    previous_id: number | null; next_id: number | null;
  };
  assessments: { id: number; title: string; required: boolean }[];
  enrollment: Enrollment;
}

export interface CompleteLessonResponse {
  lesson_id: number; status: ProgressStatus; unmet_requirements: string[];
  enrollment: Enrollment; certificate: Certificate | null;
}

export interface QuestionView {
  id: number; prompt: string; kind: QuestionKind;
  options: { id: string; text: string }[]; marks: number; position: number;
  correct?: string[]; explanation?: string | null;
  is_ai_generated?: boolean;
}

export interface AttemptView {
  id: number; assessment_id: number; attempt_number: number;
  score: number | null; max_score: number | null; percent: number | null;
  passed: boolean | null; started_at: string; submitted_at: string | null;
  results?: {
    question_id: number; correct: boolean; marks_awarded: number;
    marks_possible: number; explanation: string | null;
  }[];
}

export interface AssessmentView {
  id: number; course_id: number; module_id: number | null; lesson_id: number | null;
  title: string; instructions: string | null; pass_percent: number;
  max_attempts: number; time_limit_minutes: number | null;
  is_required_for_completion: boolean; question_count: number;
  questions: QuestionView[];
  attempts_used?: number; attempts_left?: number; best?: AttemptView | null;
  is_published?: boolean; needs_review?: boolean;
}

export interface StartAttemptResponse extends AttemptView {
  deadline: string | null;
  assessment: AssessmentView;
}

export interface SubmitAttemptResponse extends AttemptView {
  pass_percent: number; attempts_used: number; attempts_left: number;
  certificate: Certificate | null;
}

export interface MyLearningResponse {
  in_progress: CourseCardData[];
  completed: CourseCardData[];
  not_started: CourseCardData[];
  recommended: CourseCardData[];
  certificates: Certificate[];
  recent_results: {
    assessment_id: number; assessment_title: string;
    percent: number | null; passed: boolean | null; submitted_at: string | null;
  }[];
  totals: {
    enrolled: number; completed: number; certificates: number; minutes_spent: number;
  };
}

export interface VerifyResponse {
  valid: boolean; reason?: string;
  recipient_name?: string; course_title?: string; certificate_number?: string;
  certificate_type?: string; issued_at?: string; course_version?: number;
  organisation?: string; note?: string; revoked_at?: string;
}

/* ---------------------------------------------------------------- admin ---- */

export interface AdminCourse {
  id: number; slug: string; title: string; summary: string | null;
  description: string | null; objectives: string[]; category: string | null;
  tags: string[]; difficulty: string; target_audience: string | null;
  estimated_minutes: number; status: CourseStatus;
  origin: 'manual' | 'ai_generated'; ai_disclosure: string | null;
  pass_requires_assessments: boolean; version: number; owner_id: number;
  thumbnail: AssetBrief | null;
  published_at: string | null; created_at: string | null; updated_at: string | null;
  lesson_count?: number; has_active_job?: boolean;
  modules?: ModuleSummary[];
  materials?: SourceMaterial[];
  jobs?: GenerationJob[];
  assessments?: AssessmentView[];
  review?: { lessons_needing_review: number; blocks_needing_review: number };
}

export interface SourceMaterial {
  id: number; course_id: number; sensitivity: 'public' | 'internal' | 'confidential';
  openmaic_material_id: string | null; extraction_status: string | null;
  created_at: string | null; asset: AssetBrief | null;
}

export interface ImportReport {
  source: string; modules: number; lessons: number; blocks: number;
  media_files: number; media_bytes: number; questions: number;
  unsupported: { kind: string; detail: string; where: string }[];
  warnings: string[];
  skipped_files: { name: string; reason: string }[];
  already_imported?: boolean; assets_reused?: number; decorative_skipped?: number;
  needs_review: boolean;
}

export interface GenerationJob {
  id: number; course_id: number; status: JobStatus; progress: number;
  step: string | null; message: string | null; instructions: string;
  material_ids: number[]; attempt_count: number; max_attempts: number;
  last_error: string | null; import_report: ImportReport | null;
  openmaic_job_id: string | null; openmaic_classroom_id: string | null;
  requested_by_id: number;
  created_at: string | null; started_at: string | null; finished_at: string | null;
}

export interface StudioSettings {
  openmaic_configured: boolean;
  openmaic_base_url_set: boolean;
  openmaic_credentials_set: boolean;
  max_upload_bytes: number;
  max_archive_bytes: number;
  storage_backend: string;
  certificate_organisation: string;
  openmaic: { reachable: boolean; detail: string };
  html_sanitizer: string;
  difficulties: string[];
  sensitivities: string[];
  capabilities: {
    material_upload: boolean;
    classroom_generation: boolean;
    job_polling: boolean;
    automatic_export_download: boolean;
    structured_content_api: string;
    notes: string[];
  };
}

export interface AdminCourseList {
  total: number; page: number; per_page: number;
  courses: AdminCourse[]; categories: (string | null)[];
}

export interface Analytics {
  totals: {
    courses: number; published_courses: number; awaiting_review: number;
    enrolments: number; completions: number; certificates_issued: number;
    active_learners: number; completion_rate: number | null;
    average_assessment_score: number | null; learning_minutes: number;
  };
  most_popular: CourseAnalyticsRow[];
  low_completion: CourseAnalyticsRow[];
  generation_jobs: Record<string, number>;
  notes: string[];
}

export interface CourseAnalyticsRow {
  course_id: number; title: string; enrolments: number;
  completions: number; completion_rate: number | null;
}

/* --------------------------------------------------------------- helpers ---- */

export const COURSE_STATUS_LABEL: Record<CourseStatus, string> = {
  draft: 'Draft',
  generating: 'Generating',
  awaiting_review: 'Awaiting review',
  published: 'Published',
  archived: 'Archived',
};

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  draft: 'Draft', queued: 'Queued', processing: 'Processing',
  generated: 'Generated', importing: 'Importing', imported: 'Imported',
  failed: 'Failed', cancelled: 'Cancelled',
};

export const PROGRESS_LABEL: Record<ProgressStatus, string> = {
  not_started: 'Not started', in_progress: 'In progress', completed: 'Completed',
};

/** "1h 20m", "45 min", or "" when the duration is unknown. */
export function formatMinutes(total: number): string {
  if (!total || total < 1) return '';
  if (total < 60) return `${total} min`;
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Human label for a generation step, without leaking OpenMAIC internals. */
export const STEP_LABEL: Record<string, string> = {
  queued: 'Waiting in the queue',
  uploading: 'Uploading source material',
  submitting: 'Submitting to the generator',
  initializing: 'Starting up',
  researching: 'Researching the topic',
  generating_outlines: 'Drafting the outline',
  generating_scenes: 'Writing the lessons',
  generating_media: 'Producing media',
  importing: 'Importing into Minet',
  awaiting_export: 'Waiting for an export upload',
  completed: 'Finished',
  failed: 'Failed',
};
