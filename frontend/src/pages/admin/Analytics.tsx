import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { useApi } from '../../api/client';
import type { Analytics as AnalyticsData, CourseAnalyticsRow } from '../../api/lms';
import { PageHeader } from '../../components/PageHeader';
import { ErrorMsg, Loading } from '../../components/Bits';

/** Null means "no data yet", which must not be shown as a confident zero. */
function Metric({ label, value, suffix = '' }:
  { label: string; value: number | null; suffix?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__num">
        {value === null ? <span className="stat__none">No data</span> : <>{value}<small>{suffix}</small></>}
      </span>
    </div>
  );
}

function CourseTable({ rows, empty }: { rows: CourseAnalyticsRow[]; empty: string }) {
  if (!rows.length) return <p className="muted small state-msg">{empty}</p>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Course</th>
          <th className="table__num">Enrolled</th>
          <th className="table__num">Completed</th>
          <th className="table__num">Rate</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.course_id}>
            <td>
              <Link to={`/admin/course-studio/${row.course_id}`} className="table__title">
                {row.title}
              </Link>
            </td>
            <td className="table__num">{row.enrolments}</td>
            <td className="table__num">{row.completions}</td>
            <td className="table__num">
              {row.completion_rate === null ? '—' : `${row.completion_rate}%`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Analytics() {
  const { data, error, loading } = useApi<AnalyticsData>('/lms/admin/analytics');
  const back = { to: '/admin/course-studio', label: 'AI Course Studio' };

  return (
    <>
      <PageHeader title="Learning analytics"
                  subtitle="Calculated from real enrolment, lesson and assessment records."
                  back={back} />
      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading />}

      {data && (
        <>
          <div className="card stats stats--4">
            <Metric label="Published courses" value={data.totals.published_courses} />
            <Metric label="Enrolments" value={data.totals.enrolments} />
            <Metric label="Completion rate" value={data.totals.completion_rate} suffix="%" />
            <Metric label="Certificates issued" value={data.totals.certificates_issued} />
          </div>
          <div className="card stats stats--4">
            <Metric label="Active learners" value={data.totals.active_learners} />
            <Metric label="Awaiting review" value={data.totals.awaiting_review} />
            <Metric label="Average assessment score"
                    value={data.totals.average_assessment_score} suffix="%" />
            <Metric label="Learning time" value={data.totals.learning_minutes} suffix=" min" />
          </div>

          <div className="home-split">
            <section className="card table-wrap">
              <div className="records__head records__head--pad">
                <h2 className="card-title">Most popular</h2>
              </div>
              <CourseTable rows={data.most_popular}
                           empty="No one has enrolled on a course yet." />
            </section>
            <section className="card table-wrap">
              <div className="records__head records__head--pad">
                <h2 className="card-title">Low completion</h2>
              </div>
              <CourseTable rows={data.low_completion}
                           empty="No course has enough enrolments to judge yet." />
            </section>
          </div>

          {Object.keys(data.generation_jobs).length > 0 && (
            <section className="card">
              <h2 className="card-title">AI generation jobs</h2>
              <ul className="joblegend">
                {Object.entries(data.generation_jobs).map(([status, count]) => (
                  <li key={status}><strong>{count}</strong> {status.replace(/_/g, ' ')}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="card notice notice--inline">
            <Info size={16} />
            <ul className="small muted analytics__notes">
              {data.notes.map((note, i) => <li key={i}>{note}</li>)}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
