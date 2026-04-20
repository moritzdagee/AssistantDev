import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';

export default function AdminDocs() {
  return (
    <>
      <PageHeader title="Technische Dokumentation" />
      <MigrationNotice
        legacyRange="Route /admin/docs in src/web_server.py"
        todo="Markdown-Renderer und Navigations-TOC fuer architecture.md / install.md / troubleshooting.md portieren."
      />
    </>
  );
}
