import { randomUUID } from "node:crypto";

export const MOCK_BINDING_TTL_MS = 5 * 60 * 1000;

const MOCK_SCHOOLS = Object.freeze([
  {
    id: 1001,
    name: "星河实验学校",
    locations: [
      { id: "room-101", name: "一年级一班教室", type: "classroom", classId: "class-101", className: "一年级一班" },
      { id: "room-202", name: "二年级二班教室", type: "classroom", classId: "class-202", className: "二年级二班" },
      { id: "studio-main", name: "公共录播教室", type: "studio", classId: "", className: "" },
    ],
  },
  {
    id: 1002,
    name: "云帆外国语学校",
    locations: [
      { id: "room-301", name: "三年级一班教室", type: "classroom", classId: "class-301", className: "三年级一班" },
      { id: "studio-west", name: "西区录播室", type: "studio", classId: "", className: "" },
    ],
  },
]);

function bindingError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function copy(value) {
  return structuredClone(value);
}

function requireNonEmptyString(value, field) {
  if (typeof value !== "string" || !value.trim()) {
    throw bindingError("BINDING_REQUEST_INVALID", `${field} is required`);
  }
  return value.trim();
}

export class MockBindingService {
  constructor({ now = Date.now, createId = randomUUID, ttlMs = MOCK_BINDING_TTL_MS } = {}) {
    this.mode = "mock";
    this.now = now;
    this.createId = createId;
    this.ttlMs = ttlMs;
    this.sessions = new Map();
  }

  async createSession({ deviceNo } = {}) {
    const normalizedDeviceNo = requireNonEmptyString(deviceNo, "deviceNo");
    const id = String(this.createId());
    const createdAt = this.now();
    const session = {
      id,
      deviceNo: normalizedDeviceNo,
      status: "waiting",
      qrPayload: `xxt-recorder://binding?session=${encodeURIComponent(id)}`,
      createdAt: new Date(createdAt).toISOString(),
      expiresAt: new Date(createdAt + this.ttlMs).toISOString(),
      binding: null,
    };
    this.sessions.set(id, session);
    return copy(session);
  }

  async getSession(sessionId) {
    return copy(this.#getSession(sessionId));
  }

  async simulateScan(sessionId) {
    const session = this.#getSession(sessionId);
    this.#requireStatus(session, "waiting");
    session.status = "scanned";
    session.scannedAt = new Date(this.now()).toISOString();
    return copy(session);
  }

  async listSchools(sessionId) {
    const session = this.#getSession(sessionId);
    this.#requireScanned(session);
    return MOCK_SCHOOLS.map(({ id, name }) => ({ id, name }));
  }

  async listLocations(sessionId, { schoolId, locationType } = {}) {
    const session = this.#getSession(sessionId);
    this.#requireScanned(session);
    const school = MOCK_SCHOOLS.find(({ id }) => id === schoolId);
    if (!school || !["classroom", "studio"].includes(locationType)) {
      throw bindingError("BINDING_SELECTION_INVALID", "school or location type is invalid");
    }
    return school.locations
      .filter(({ type }) => type === locationType)
      .map(({ id, name, type, classId, className }) => ({ id, name, type, classId, className }));
  }

  async confirmBinding(sessionId, { schoolId, locationType, locationId } = {}) {
    const session = this.#getSession(sessionId);
    this.#requireStatus(session, "scanned");
    const school = MOCK_SCHOOLS.find(({ id }) => id === schoolId);
    const location = school?.locations.find(({ id, type }) => id === locationId && type === locationType);
    if (!school || !location) {
      throw bindingError("BINDING_SELECTION_INVALID", "binding selection is not in the catalog");
    }

    const binding = {
      deviceNo: session.deviceNo,
      schoolId: school.id,
      schoolName: school.name,
      locationType: location.type,
      locationId: location.id,
      locationName: location.name,
      classId: location.type === "classroom" ? location.classId : "",
      className: location.type === "classroom" ? location.className : "",
      bindingSource: "mock",
      boundAt: new Date(this.now()).toISOString(),
    };
    session.status = "confirmed";
    session.binding = binding;
    return copy(binding);
  }

  #getSession(sessionId) {
    const session = this.sessions.get(String(sessionId));
    if (!session) {
      throw bindingError("BINDING_SESSION_NOT_FOUND", "binding session was not found");
    }
    if (!["confirmed", "expired"].includes(session.status) && this.now() > Date.parse(session.expiresAt)) {
      session.status = "expired";
    }
    return session;
  }

  #requireStatus(session, expected) {
    if (session.status === "expired") {
      throw bindingError("BINDING_SESSION_EXPIRED", "binding session has expired");
    }
    if (session.status !== expected) {
      throw bindingError("BINDING_SESSION_INVALID_STATE", `binding session must be ${expected}`);
    }
  }

  #requireScanned(session) {
    if (session.status === "expired") {
      throw bindingError("BINDING_SESSION_EXPIRED", "binding session has expired");
    }
    if (session.status !== "scanned") {
      throw bindingError("BINDING_SESSION_NOT_SCANNED", "binding session has not been scanned");
    }
  }
}

export class UnavailableRemoteBindingService {
  constructor() {
    this.mode = "remote";
  }

  async createSession() { throw this.#unavailable(); }
  async getSession() { throw this.#unavailable(); }
  async simulateScan() { throw this.#unavailable(); }
  async listSchools() { throw this.#unavailable(); }
  async listLocations() { throw this.#unavailable(); }
  async confirmBinding() { throw this.#unavailable(); }

  #unavailable() {
    return bindingError("BINDING_SERVICE_UNAVAILABLE", "binding service is not configured");
  }
}

export function createBindingService(options = {}) {
  if (options.mode === "mock") return new MockBindingService(options);
  return new UnavailableRemoteBindingService();
}
