"use client";

import { Loader2, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, login } from "@/lib/api-client";
import { MIN_TOKEN_LEN } from "@/lib/config";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(token);
      router.push("/ask");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar sesión.");
      setLoading(false);
    }
  }

  const disabled = loading || token.trim().length < MIN_TOKEN_LEN;

  return (
    <div className="flex min-h-full flex-col">
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md">
          <CardHeader>
            <span className="flex items-center gap-2 font-semibold text-primary">
              <Shield className="size-5" aria-hidden />
              RegulAItor
            </span>
            <CardTitle className="mt-2">Acceso</CardTitle>
            <CardDescription>
              Introduce tu token de API para acceder a tu organización.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="token">Token de API</Label>
                <Input
                  id="token"
                  type="password"
                  autoComplete="off"
                  autoFocus
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  placeholder="••••••••••••••••"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? "login-error" : "token-hint"}
                />
                <p id="token-hint" className="text-xs text-muted-foreground">
                  Mínimo {MIN_TOKEN_LEN} caracteres.
                </p>
              </div>
              {error ? (
                <p id="login-error" role="alert" className="text-sm text-red-600">
                  {error}
                </p>
              ) : null}
              <Button type="submit" className="w-full" disabled={disabled}>
                {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Entrar
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
      <LegalDisclaimer />
    </div>
  );
}
