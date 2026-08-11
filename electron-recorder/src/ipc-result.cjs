const MARKER = "classroom-recorder-ipc-result";

function successResult(value) {
  return { marker: MARKER, ok: true, value };
}

function failureResult(error) {
  return {
    marker: MARKER,
    ok: false,
    error: {
      code: stringValue(error?.code),
      message: stringValue(error?.message) || "操作没有完成",
      businessCode: integerValue(error?.businessCode),
      operation: stringValue(error?.operation),
      unbound: Boolean(error?.unbound),
    },
  };
}

function unwrapResult(result) {
  if (result?.marker !== MARKER) return result;
  if (result.ok) return result.value;
  const error = new Error(result.error?.message || "操作没有完成");
  Object.assign(error, result.error || {});
  throw error;
}

async function captureResult(operation) {
  try {
    return successResult(await operation());
  } catch (error) {
    return failureResult(error);
  }
}

function stringValue(value) {
  return typeof value === "string" ? value : "";
}

function integerValue(value) {
  const number = Number(value);
  return Number.isInteger(number) ? number : null;
}

module.exports = {
  captureResult,
  failureResult,
  successResult,
  unwrapResult,
};
