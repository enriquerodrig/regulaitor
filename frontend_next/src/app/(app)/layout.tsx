import { AppShell } from "@/components/app-shell";

// Layout for the authenticated surfaces (/ask, /analyze, /health). Route
// protection is enforced by the Proxy (src/proxy.ts, Next 16); this just wraps
// them in the shell.
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
