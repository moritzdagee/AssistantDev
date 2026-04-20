import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';

export default function AdminPermissions() {
  return (
    <>
      <PageHeader title="Berechtigungen" />
      <MigrationNotice
        legacyRange="Route /admin/permissions in src/web_server.py"
        todo="OAuth-Status (Slack, Canva, Google Calendar), API-Key-Slots und macOS-Automation-Permissions darstellen."
      />
    </>
  );
}
