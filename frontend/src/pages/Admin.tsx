import { Link } from 'react-router-dom';
import { FileText, ScrollText, ShieldCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

const SECTIONS = [
  {
    to: '/admin/docs',
    title: 'Technische Dokumentation',
    description: 'Architektur, Services, LaunchAgents, Pfade',
    icon: FileText,
  },
  {
    to: '/admin/changelog',
    title: 'Changelog',
    description: 'Alle Aenderungen chronologisch',
    icon: ScrollText,
  },
  {
    to: '/admin/permissions',
    title: 'Berechtigungen',
    description: 'OAuth-Tokens, API-Keys, Zugriffe',
    icon: ShieldCheck,
  },
] as const;

export default function Admin() {
  return (
    <>
      <PageHeader
        title="Admin Panel"
        description="System-Uebersicht und Konfiguration"
      />
      <div className="grid gap-4 md:grid-cols-3">
        {SECTIONS.map(({ to, title, description, icon: Icon }) => (
          <Link key={to} to={to} className="transition hover:opacity-90">
            <Card className="h-full">
              <CardHeader>
                <Icon className="mb-2 h-6 w-6 text-muted-foreground" />
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Oeffnen →
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
