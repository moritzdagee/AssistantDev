import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';

export default function Messages() {
  return (
    <>
      <PageHeader
        title="Posteingang"
        description="E-Mail, WhatsApp, kChat, Slack — unifizierter Stream."
      />
      <MigrationNotice
        legacyRange="Zeilen 13387–14240 (_MSG_DASHBOARD_HTML) und 14241–ff. (_MSG_VIEW_HTML)"
        todo="Per-Message-Tracking, Conversation-Aggregation, Filter/Suche und die Detail-View portieren."
      />
    </>
  );
}
