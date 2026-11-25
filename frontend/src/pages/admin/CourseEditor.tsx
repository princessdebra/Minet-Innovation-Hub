import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useApi } from '../../api/client';
import { COURSE_STATUS_LABEL, type AdminCourse, type StudioSettings } from '../../api/lms';
import { PageHeader } from '../../components/PageHeader';
import { ErrorMsg, Loading, Tabs } from '../../components/Bits';
import { DetailsTab } from './tabs/DetailsTab';
import { GenerateTab } from './tabs/GenerateTab';
import { ContentTab } from './tabs/ContentTab';
import { AssessmentTab } from './tabs/AssessmentTab';
import { PublishTab } from './tabs/PublishTab';

const STATUS_COLOR: Record<string, string> = {
  draft: 'slate', generating: 'sky', awaiting_review: 'amber',
  published: 'emerald', archived: 'slate',
};

type TabId = 'details' | 'generate' | 'content' | 'assessment' | 'publish';
const TAB_IDS: TabId[] = ['details', 'generate', 'content', 'assessment', 'publish'];

export function CourseEditor() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const course = useApi<AdminCourse>(`/lms/admin/courses/${id}`);
  const settings = useApi<StudioSettings>('/lms/admin/settings');
  const [saved, setSaved] = useState<string | null>(null);

  const requested = params.get('tab') as TabId | null;
  const tab: TabId = requested && TAB_IDS.includes(requested) ? requested : 'details';
  const setTab = (next: TabId) => setParams(next === 'details' ? {} : { tab: next });

  const back = { to: '/admin/course-studio', label: 'AI Course Studio' };
  if (course.error) return <><PageHeader title="Course" back={back} /><ErrorMsg text={course.error} /></>;
  if (!course.data) return <><PageHeader title="Course" back={back} /><Loading /></>;

  const data = course.data;
  const review = (data.review?.lessons_needing_review ?? 0) + (data.review?.blocks_needing_review ?? 0);
  const lessons = (data.modules ?? []).reduce((total, m) => total + m.lessons.length, 0);

  function refresh(message?: string) {
    course.reload();
    if (message) {
      setSaved(message);
      setTimeout(() => setSaved(null), 4000);
    }
  }

  return (
    <>
      <PageHeader title={data.title} subtitle={data.summary ?? undefined} back={back} />

      <div className="studiobar card">
        <span className={`status-pill status-pill--${STATUS_COLOR[data.status] ?? 'slate'}`}>
          {COURSE_STATUS_LABEL[data.status]}
        </span>
        <span className="small muted">
          {lessons} lesson{lessons === 1 ? '' : 's'}
          {data.version > 1 && ` • version ${data.version}`}
          {data.origin === 'ai_generated' && ' • AI-assisted'}
        </span>
        {review > 0 && (
          <span className="status-pill status-pill--amber">{review} item{review === 1 ? '' : 's'} need review</span>
        )}
        {saved && <span className="studiobar__saved">{saved}</span>}
      </div>

      <Tabs
        tabs={[
          { id: 'details' as TabId, label: 'Details' },
          { id: 'generate' as TabId, label: 'Material & AI' },
          { id: 'content' as TabId, label: `Content${lessons ? ` (${lessons})` : ''}` },
          { id: 'assessment' as TabId, label: `Assessment${data.assessments?.length ? ` (${data.assessments.length})` : ''}` },
          { id: 'publish' as TabId, label: 'Preview & publish' },
        ]}
        value={tab} onChange={setTab} />

      <div className="studiotab">
        {tab === 'details' && <DetailsTab course={data} settings={settings.data} onSaved={refresh} />}
        {tab === 'generate' && <GenerateTab course={data} settings={settings.data} onChanged={refresh} />}
        {tab === 'content' && <ContentTab course={data} onChanged={refresh} />}
        {tab === 'assessment' && <AssessmentTab course={data} onChanged={refresh} />}
        {tab === 'publish' && <PublishTab course={data} onChanged={refresh} />}
      </div>
    </>
  );
}
