import { writeFileSync } from "node:fs";
import { bindingProblemCode } from "./binding-error-view.js";

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

export function createBindingFailureTracker({ now = () => new Date() } = {}) {
  let latest = null;
  return {
    capture(stage, error = {}) {
      const source = error || {};
      latest = {
        occurredAt: new Date(now()).toISOString(),
        stage: safeString(stage),
        problemCode: bindingProblemCode(source),
        code: safeString(source.code),
        businessCode: integerValue(source.businessCode),
        operation: safeString(source.operation),
        message: safeDiagnosticMessage(source.message),
      };
      return { ...latest };
    },
    clear() {
      latest = null;
    },
    latest() {
      return latest ? { ...latest } : null;
    },
  };
}

function safeString(value) {
  return typeof value === "string" ? value : "";
}

function integerValue(value) {
  if (value === null || value === "") return null;
  const number = Number(value);
  return Number.isInteger(number) ? number : null;
}

function safeDiagnosticMessage(value) {
  return safeString(value)
    .replace(
      /(authorization|password|secret|token)\s*[:=]\s*\S+/giu,
      "$1=[REDACTED]"
    )
    .replace(/Bearer\s+\S+/giu, "Bearer [REDACTED]")
    .slice(0, 1000);
}
