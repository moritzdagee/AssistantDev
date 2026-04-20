import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/layout/PageHeader';
import { MigrationNotice } from '@/components/MigrationNotice';
import { api } from '@/lib/api';
import { endpoints } from '@/lib/endpoints';

interface AgentsResponse {
  agents?: Array<{ name: string; description?: string }>;
}

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get<AgentsResponse>(endpoints.agents),
  });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Chat mit Agenten, Kontext, Konversationen."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Agenten</CardTitle>
            <CardDescription>Verfuegbare Agenten vom Backend</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {isLoading && <p className="text-muted-foreground">Lade…</p>}
            {isError && (
              <p className="text-destructive">
                Fehler: {(error as Error).message}
              </p>
            )}
            {!isLoading && !isError && (
              <ul className="space-y-1">
                {(data?.agents ?? []).map((a) => (
                  <li key={a.name} className="flex items-center justify-between">
                    <span className="font-medium">{a.name}</span>
                    {a.description && (
                      <span className="text-xs text-muted-foreground">
                        {a.description}
                      </span>
                    )}
                  </li>
                ))}
                {(!data?.agents || data.agents.length === 0) && (
                  <li className="text-muted-foreground">
                    Keine Agenten gemeldet.
                  </li>
                )}
              </ul>
            )}
          </CardContent>
        </Card>
        <MigrationNotice
          legacyRange="Zeilen 3423–11526 (HTML)"
          todo="Chat-Pane, Sidebar mit Konversationen, Kontext-Panel, Agent-Modal, File-Upload und Message-Rendering muessen aus dem inline HTML/JS portiert werden."
        />
      </div>
    </>
  );
}
