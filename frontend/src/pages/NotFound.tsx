import { Link } from 'react-router-dom';
import { PageHeader } from '../components/PageHeader';

export function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <p className="muted">That page does not exist. <Link to="/">Go to Home</Link></p>
    </>
  );
}
