import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';

export default function NotFound() {
  return (
    <>
      <PageHeader title="Seite nicht gefunden" description="404" />
      <Button asChild>
        <Link to="/">Zum Dashboard</Link>
      </Button>
    </>
  );
}
