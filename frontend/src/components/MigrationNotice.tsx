import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface MigrationNoticeProps {
  /** Zeilen-Range im Altbestand src/web_server.py */
  legacyRange: string;
  /** Kurzbeschreibung, was hier noch zu migrieren ist */
  todo: string;
}

/**
 * Platzhalter fuer noch nicht migrierte Seiten.
 * Verweist auf die Original-Zeilen in src/web_server.py, damit die
 * Portierung Datei-fuer-Datei nachvollziehbar bleibt.
 */
export function MigrationNotice({ legacyRange, todo }: MigrationNoticeProps) {
  return (
    <Card className="border-dashed">
      <CardHeader className="flex flex-row items-center gap-3">
        <AlertTriangle className="h-5 w-5 text-yellow-500" />
        <CardTitle>Migration ausstehend</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>{todo}</p>
        <p className="text-muted-foreground">
          Quelle:{' '}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
            src/web_server.py {legacyRange}
          </code>
        </p>
      </CardContent>
    </Card>
  );
}
