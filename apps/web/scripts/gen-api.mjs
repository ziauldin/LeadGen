// Regenerate src/lib/api/schema.d.ts from the API's OpenAPI schema.
// Uses the API's virtualenv when present, otherwise `python` on PATH.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = resolve(web, "../../services/api");
const candidates = [
  join(apiDir, ".venv", "Scripts", "python.exe"),
  join(apiDir, ".venv", "bin", "python"),
];
const python = candidates.find((path) => existsSync(path)) ?? process.env.PYTHON ?? "python";

execFileSync(python, [join(apiDir, "scripts", "export_openapi.py"), join(web, "openapi.json")], {
  stdio: "inherit",
});
execFileSync(
  process.execPath,
  [
    join(web, "node_modules", "openapi-typescript", "bin", "cli.js"),
    join(web, "openapi.json"),
    "-o",
    join(web, "src", "lib", "api", "schema.d.ts"),
    "--default-non-nullable",
    "false",
  ],
  { stdio: "inherit" },
);
