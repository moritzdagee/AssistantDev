import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Inbox,
  Brain,
  Settings,
  FileText,
  ScrollText,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/messages', label: 'Posteingang', icon: Inbox },
  { to: '/memory', label: 'Memory', icon: Brain },
  { to: '/admin', label: 'Admin', icon: Settings, end: true },
  { to: '/admin/docs', label: 'Dokumentation', icon: FileText },
  { to: '/admin/changelog', label: 'Changelog', icon: ScrollText },
  { to: '/admin/permissions', label: 'Berechtigungen', icon: ShieldCheck },
] as const;

export function Sidebar() {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="px-5 py-5">
        <div className="text-base font-semibold tracking-tight">
          AssistantDev
        </div>
        <div className="text-xs text-muted-foreground">
          Persoenliches AI-System
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 pb-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border px-5 py-3 text-[11px] text-muted-foreground">
        Frontend-Shell · Migration in Arbeit
      </div>
    </aside>
  );
}
