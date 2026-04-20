import { useParams } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';

export default function Memory() {
  const { agent } = useParams<{ agent?: string }>();
  return (
    <>
      <PageHeader
        title="Memory"
        description={
          agent
            ? `Working-Memory fuer Agent: ${agent}`
            : 'Memory-Dateien aller Agenten'
        }
      />
      <MigrationNotice
        legacyRange="_MEMORY_PAGE_HTML ab Zeile 11527"
        todo="File-Browser fuer memory/<agent>/ mit Preview, Prioritaet und Add/Remove-Flow portieren."
      />
    </>
  );
}
