import { Link } from 'react-router-dom';
import { Award, Download, ShieldCheck } from 'lucide-react';
import { useApi } from '../api/client';
import { formatDate, type MyLearningResponse } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { CourseGrid } from '../components/lms/CourseCard';
import { ErrorMsg, Loading } from '../components/Bits';

export function MyLearning() {
  const { data, error, loading } = useApi<MyLearningResponse>('/lms/me/learning');
  const back = { to: '/learn/courses', label: 'Innovation Academy' };

  return (
    <>
      <PageHeader title="My learning"
                  subtitle="Your courses, assessment results and certificates."
                  back={back} />
      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading />}

      {data && (
        <>
          <div className="card stats stats--4">
            <div className="stat">
              <span className="stat__label">Courses enrolled</span>
              <span className="stat__num">{data.totals.enrolled}</span>
            </div>
            <div className="stat">
              <span className="stat__label">Completed</span>
              <span className="stat__num">{data.totals.completed}</span>
            </div>
            <div className="stat">
              <span className="stat__label">Certificates</span>
              <span className="stat__num">{data.totals.certificates}</span>
            </div>
            <div className="stat">
              <span className="stat__label">Learning time</span>
              <span className="stat__num">{data.totals.minutes_spent}<small> min</small></span>
            </div>
          </div>

          {data.in_progress.length > 0 && (
            <>
              <h2 className="h2">Continue learning</h2>
              <CourseGrid courses={data.in_progress} empty="" />
            </>
          )}

          {data.not_started.length > 0 && (
            <>
              <h2 className="h2">Enrolled, not started</h2>
              <CourseGrid courses={data.not_started} empty="" />
            </>
          )}

          {data.completed.length > 0 && (
            <>
              <h2 className="h2">Completed</h2>
              <CourseGrid courses={data.completed} empty="" />
            </>
          )}

          {data.in_progress.length === 0 && data.completed.length === 0
            && data.not_started.length === 0 && (
            <div className="card empty">
              <strong>You have not started a course yet.</strong>
              <p className="muted">
                Browse the <Link to="/learn/courses">Innovation Academy</Link> to find one.
              </p>
            </div>
          )}

          <div className="home-split">
            <section className="card">
              <h2 className="card-title">My certificates</h2>
              {data.certificates.length === 0
                ? <p className="muted small">Complete a course to earn your first certificate.</p>
                : (
                  <ul className="certlist">
                    {data.certificates.map((cert) => (
                      <li key={cert.id} className={cert.is_valid ? '' : 'is-revoked'}>
                        <Award size={18} />
                        <div>
                          <strong>{cert.course_title}</strong>
                          <span className="small muted">
                            {cert.certificate_number} &bull; {formatDate(cert.issued_at)}
                            {cert.score_percent !== null && ` • ${cert.score_percent}%`}
                            {!cert.is_valid && ' • revoked'}
                          </span>
                        </div>
                        {cert.is_valid && (
                          <div className="certlist__actions">
                            <a className="icon-btn" href={cert.download_url}
                               aria-label={`Download certificate for ${cert.course_title}`}>
                              <Download size={16} />
                            </a>
                            <Link className="icon-btn" to={`/verify/${cert.verification_code}`}
                                  aria-label="Verify this certificate">
                              <ShieldCheck size={16} />
                            </Link>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
            </section>

            <section className="card">
              <h2 className="card-title">Recent assessment results</h2>
              {data.recent_results.length === 0
                ? <p className="muted small">You have not taken an assessment yet.</p>
                : (
                  <table className="table">
                    <thead>
                      <tr><th>Assessment</th><th className="table__num">Score</th><th>Result</th></tr>
                    </thead>
                    <tbody>
                      {data.recent_results.map((row, i) => (
                        <tr key={i}>
                          <td>
                            <span className="table__title">{row.assessment_title}</span>
                            <span className="table__sub">{formatDate(row.submitted_at)}</span>
                          </td>
                          <td className="table__num">{row.percent ?? '—'}%</td>
                          <td>
                            <span className={`status-pill status-pill--${row.passed ? 'emerald' : 'orange'}`}>
                              {row.passed ? 'Passed' : 'Not passed'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </section>
          </div>

          {data.recommended.length > 0 && (
            <>
              <h2 className="h2">Recommended next</h2>
              <CourseGrid courses={data.recommended} empty="" />
            </>
          )}
        </>
      )}
    </>
  );
}
