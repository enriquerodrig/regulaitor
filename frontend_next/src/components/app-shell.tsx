"use client";

import { Activity, FileText, LogOut, MessageSquare, ScrollText, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/ask", label: "Pregunta", icon: MessageSquare },
  { href: "/analyze", label: "Analiza documento", icon: FileText },
  { href: "/audit", label: "Auditoría", icon: ScrollText },
  { href: "/health", label: "Estado", icon: Activity },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function onLogout() {
    await logout();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <span className="flex items-center gap-2 font-semibold text-primary">
            <Shield className="size-5" aria-hidden />
            RegulAItor
          </span>
          <nav className="flex items-center gap-1" aria-label="Navegación principal">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-label={label}
                aria-current={pathname === href ? "page" : undefined}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                  pathname === href
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={onLogout}
              aria-label="Salir"
              className="ml-1 text-muted-foreground"
            >
              <LogOut className="size-4" aria-hidden />
              <span className="hidden sm:inline">Salir</span>
            </Button>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>

      <LegalDisclaimer />
    </div>
  );
}
