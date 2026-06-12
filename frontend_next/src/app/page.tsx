import { redirect } from "next/navigation";

// Root: send to the chat surface. Unauthenticated visitors are bounced to
// /login by the Proxy (src/proxy.ts) before this runs.
export default function Home() {
  redirect("/ask");
}
