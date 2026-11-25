import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { Explore } from './pages/Explore';
import { ChallengeDetail } from './pages/ChallengeDetail';
import { SubmitIdea } from './pages/SubmitIdea';
import { Workspace } from './pages/Workspace';
import { Learn } from './pages/Learn';
import { PathDetail } from './pages/PathDetail';
import { Courses } from './pages/Courses';
import { CourseDetail } from './pages/CourseDetail';
import { LessonPlayer } from './pages/LessonPlayer';
import { AssessmentRunner } from './pages/AssessmentRunner';
import { MyLearning } from './pages/MyLearning';
import { VerifyCertificate } from './pages/VerifyCertificate';
import { Knowledge } from './pages/Knowledge';
import { LibraryCategory } from './pages/LibraryCategory';
import { Leaderboard } from './pages/Leaderboard';
import { Help } from './pages/Help';
import { NotFound } from './pages/NotFound';
import { CourseStudio } from './pages/admin/CourseStudio';
import { CourseEditor } from './pages/admin/CourseEditor';
import { Analytics } from './pages/admin/Analytics';

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="explore" element={<Explore />} />
        <Route path="explore/:id" element={<ChallengeDetail />} />
        <Route path="ideas/new" element={<SubmitIdea />} />
        <Route path="workspace" element={<Workspace />} />
        <Route path="learn" element={<Learn />} />
        <Route path="learn/paths/:id" element={<PathDetail />} />
        <Route path="learn/courses" element={<Courses />} />
        <Route path="learn/courses/:id" element={<CourseDetail />} />
        <Route path="learn/lessons/:id" element={<LessonPlayer />} />
        <Route path="learn/assessments/:id" element={<AssessmentRunner />} />
        <Route path="learn/my-learning" element={<MyLearning />} />
        <Route path="verify" element={<VerifyCertificate />} />
        <Route path="verify/:code" element={<VerifyCertificate />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/library/:slug" element={<LibraryCategory />} />
        <Route path="leaderboard" element={<Leaderboard />} />
        <Route path="admin/course-studio" element={<CourseStudio />} />
        <Route path="admin/course-studio/:id" element={<CourseEditor />} />
        <Route path="admin/analytics" element={<Analytics />} />
        <Route path="help" element={<Help />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
