import { type ReactNode } from 'react';
import { Sidebar } from './Sidebar';

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-[1400px] p-6">{children}</div>
      </main>
    </div>
  );
}
