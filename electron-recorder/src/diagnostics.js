import { writeFileSync } from "node:fs";

const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(password|token|secret|authorization)/i;

export function redactDiagnostics(value, parents = []) {
  if (Array.isArray(value))
    return value.map((child) => redactDiagnostics(child, parents));
  if (!value || typeof value !== "object") return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => {
      const isOssRoute =
        parents.at(-1) === "apiRoutes" &&
        key === "ossToken" &&
        typeof child === "string" &&
        /^https?:\/\//u.test(child);
      return [
        key,
        SENSITIVE_KEY.test(key) && !isOssRoute
          ? REDACTED
          : redactDiagnostics(child, [...parents, key]),
      ];
    })
  );
}

export function writeDiagnosticFile(filePath, diagnostics) {
  writeFileSync(
    filePath,
    `${JSON.stringify(redactDiagnostics(diagnostics), null, 2)}\n`,
    "utf8"
  );
}
