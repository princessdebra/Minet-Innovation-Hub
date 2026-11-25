import { Link } from 'react-router-dom';
import { BookOpen, Clock, Sparkles } from 'lucide-react';
import { ProgressBar } from '../Bits';
import { formatMinutes, PROGRESS_LABEL, type CourseCardData } from '../../api/lms';

export function CourseCard({ course }: { course: CourseCardData }) {
  const duration = formatMinutes(course.estimated_minutes);
  return (
    <Link to={`/learn/courses/${course.id}`} className="card coursecard">
      <div className="coursecard__media">
        {course.thumbnail
          ? <img src={course.thumbnail.url} alt="" loading="lazy" />
          : <span className="coursecard__placeholder"><BookOpen size={22} strokeWidth={1.5} /></span>}
        {course.origin === 'ai_generated' && (
          <span className="coursecard__ai" title="Parts of this course were generated with AI and reviewed before publication">
            <Sparkles size={11} /> AI-assisted
          </span>
        )}
      </div>
      <div className="coursecard__body">
        <span className="small muted coursecard__eyebrow">
          {course.category || 'Course'} &bull; {course.difficulty}
        </span>
        <h3>{course.title}</h3>
        {course.summary && <p className="muted">{course.summary}</p>}
      </div>
      <div className="coursecard__foot">
        <span className="small muted">
          {course.lesson_count > 0 && <>{course.lesson_count} lesson{course.lesson_count === 1 ? '' : 's'}</>}
          {course.lesson_count > 0 && duration && ' • '}
          {duration && <><Clock size={11} /> {duration}</>}
        </span>
        <span className={`small coursecard__status is-${course.status}`}>
          {PROGRESS_LABEL[course.status]}
        </span>
      </div>
      {course.status === 'in_progress' && (
        <div className="coursecard__bar"><ProgressBar percent={course.progress_percent} /></div>
      )}
    </Link>
  );
}

export function CourseGrid({ courses, empty }: { courses: CourseCardData[]; empty: string }) {
  if (!courses.length) return <p className="muted state-msg">{empty}</p>;
  return (
    <div className="grid-3 coursegrid">
      {courses.map((c) => <CourseCard key={c.id} course={c} />)}
    </div>
  );
}
