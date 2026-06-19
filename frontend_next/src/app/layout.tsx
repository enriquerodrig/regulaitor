import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import "./globals.css";

// Self-hosted Geist (the `geist` package) — NOT next/font/google: the fonts are
// bundled, so the build needs no Google Fonts fetch (works offline / in
// restricted networks, and keeps the deploy free of external font CDNs).

// The per-request CSP nonce (src/proxy.ts) requires dynamic rendering so the
// nonce in the response header matches the inline scripts Next emits.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "RegulAItor — cumplimiento normativo con citas verificadas",
  description:
    "Servicio multi-agente de cumplimiento normativo europeo con verificación estricta de citas. No responde sin cita verificable.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
