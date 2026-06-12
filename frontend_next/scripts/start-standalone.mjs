// Run the Next.js standalone server (output: "standalone") with the static
// assets copied alongside it — mirrors the Docker runtime (`node server.js`),
// so local `npm start` matches production and avoids the `next start` +
// standalone warning. Cross-platform (Node fs, no shell cp).
import { spawnSync } from "node:child_process";
import { cpSync, existsSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const standalone = join(root, ".next", "standalone");

if (!existsSync(join(standalone, "server.js"))) {
  console.error('No standalone build found. Run "npm run build" first.');
  process.exit(1);
}

// The standalone server resolves these relative to itself.
cpSync(join(root, ".next", "static"), join(standalone, ".next", "static"), {
  recursive: true,
});
if (existsSync(join(root, "public"))) {
  cpSync(join(root, "public"), join(standalone, "public"), { recursive: true });
}

const res = spawnSync(process.execPath, [join(standalone, "server.js")], {
  stdio: "inherit",
  env: process.env,
});
process.exit(res.status ?? 0);
