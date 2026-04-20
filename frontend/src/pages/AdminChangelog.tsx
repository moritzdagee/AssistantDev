import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';

export default function AdminChangelog() {
  return (
    <>
      <PageHeader title="Changelog" />
      <MigrationNotice
        legacyRange="Route /admin/changelog in src/web_server.py"
        todo="changelog.md einlesen, nach Datum gruppieren und mit Suchfilter anzeigen."
      />
    </>
  );
}
