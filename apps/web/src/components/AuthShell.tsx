import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "./Nav";
import { link } from "./ui";

/** The signed-out pages besides sign in: one narrow column with the wordmark and a way back. */
export function AuthShell({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <main className="mx-auto grid min-h-dvh max-w-[24rem] content-center px-[var(--gutter)] py-16">
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <p className="text-lg font-medium tracking-[var(--tracking-display)]">ResolveAI</p>
          <ThemeToggle />
        </div>
        <div className="space-y-3">
          <h1>{title}</h1>
          {description && <p className="text-sm text-muted">{description}</p>}
        </div>
        {children}
        <p className="text-sm">
          <Link href="/login" className={link}>
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
