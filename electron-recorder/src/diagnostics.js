import { writeFileSync } from "node:fs";

const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(password|token|secret|authorization)/i;

export function redactDiagnostics(value) {
  if (Array.isArray(value)) return value.map(redactDiagnostics);
  if (!value || typeof value !== "object") return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => [
      key,
      SENSITIVE_KEY.test(key) ? REDACTED : redactDiagnostics(child),
    ]),
  );
}

export function writeDiagnosticFile(filePath, diagnostics) {
  writeFileSync(filePath, `${JSON.stringify(redactDiagnostics(diagnostics), null, 2)}\n`, "utf8");
}
