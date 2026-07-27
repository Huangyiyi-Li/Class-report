import { randomUUID } from "node:crypto";

const MOCK_USER = Object.freeze({
  schoolId: 1001,
  schoolName: "星河实验学校",
  userName: "测试教师",
  userType: 0,
});
const MOCK_GRADES = Object.freeze([
  { gradeCode: 1, gradeName: "一年级" },
  { gradeCode: 2, gradeName: "二年级" },
]);
const MOCK_CLASSES = Object.freeze({
  1: [
    { classId: 101, className: "1.1班" },
    { classId: 102, className: "1.2班" },
  ],
  2: [
    { classId: 201, className: "2.1班" },
    { classId: 202, className: "2.2班" },
  ],
});

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
  constructor({ now = Date.now, createId = randomUUID } = {}) {
    this.mode = "mock";
    this.now = now;
    this.createId = createId;
    this.sessions = new Map();
  }

  async createSession({ deviceNo } = {}) {
    const normalizedDeviceNo = requireNonEmptyString(deviceNo, "deviceNo");
    const id = String(this.createId());
    const session = {
      id,
      deviceNo: normalizedDeviceNo,
      status: "authenticated",
      user: copy(MOCK_USER),
      binding: null,
    };
    this.sessions.set(id, session);
    return publicSession(session);
  }

  async getSession(sessionId) {
    return publicSession(this.#getSession(sessionId));
  }

  async listGrades(sessionId) {
    this.#getSession(sessionId);
    return copy(MOCK_GRADES);
  }

  async listClasses(sessionId, { gradeCode } = {}) {
    this.#getSession(sessionId);
    const normalizedGradeCode = requirePositiveInteger(gradeCode, "gradeCode");
    return copy(MOCK_CLASSES[normalizedGradeCode] || []);
  }

  async confirmBinding(sessionId, selection = {}) {
    const session = this.#getSession(sessionId);
    if (session.status !== "authenticated") {
      throw bindingError(
        "BINDING_SESSION_INVALID_STATE",
        "binding session is already confirmed"
      );
    }
    const request = bindingRequest(session, selection);
    const classroomBinding = request.bindType === 1;
    const binding = {
      deviceNo: session.deviceNo,
      schoolId: session.user.schoolId,
      schoolName: session.user.schoolName,
      bindType: request.bindType,
      classroom: request.classroom,
      classId: classroomBinding ? String(request.classId) : "",
      className: classroomBinding
        ? requireNonEmptyString(selection.className, "className")
        : "",
      bindingSource: "mock",
      boundAt: new Date(this.now()).toISOString(),
    };
    session.status = "confirmed";
    session.binding = binding;
    this.sessions.delete(String(sessionId));
    return copy(binding);
  }

  async unbindDevice(sessionId) {
    const session = this.#getSession(sessionId);
    if (session.status !== "authenticated") {
      throw bindingError(
        "BINDING_SESSION_INVALID_STATE",
        "binding session is already confirmed"
      );
    }
    session.status = "confirmed";
    return { success: true };
  }

  #getSession(sessionId) {
    const session = this.sessions.get(String(sessionId));
    if (!session) {
      throw bindingError(
        "BINDING_SESSION_NOT_FOUND",
        "binding session was not found"
      );
    }
    return session;
  }
}

export class UnavailableRemoteBindingService {
  constructor() {
    this.mode = "remote";
  }

  async createSession() {
    throw this.#unavailable();
  }
  async getSession() {
    throw this.#unavailable();
  }
  async listGrades() {
    throw this.#unavailable();
  }
  async listClasses() {
    throw this.#unavailable();
  }
  async confirmBinding() {
    throw this.#unavailable();
  }

  #unavailable() {
    return bindingError(
      "BINDING_SERVICE_UNAVAILABLE",
      "binding service is not configured"
    );
  }
}

export class RemoteBindingService {
  constructor({
    authenticate,
    createId = randomUUID,
    now = Date.now,
    restBaseUrl = "https://rest.xxt.cn",
  } = {}) {
    if (typeof authenticate !== "function") {
      throw bindingError(
        "BINDING_SERVICE_UNAVAILABLE",
        "binding service is not configured"
      );
    }
    this.mode = "remote";
    this.authenticate = authenticate;
    this.createId = createId;
    this.now = now;
    this.restBaseUrl = String(restBaseUrl).replace(/\/+$/, "");
    this.sessions = new Map();
  }

  async createSession({ deviceNo } = {}) {
    const normalizedDeviceNo = requireNonEmptyString(deviceNo, "deviceNo");
    const authenticated = await this.authenticate();
    const user = normalizeAuthenticatedUser(authenticated?.user);
    if (typeof authenticated?.post !== "function") {
      throw bindingError(
        "PASSPORT_SESSION_INVALID",
        "登录会话不能调用绑定接口"
      );
    }
    const id = String(this.createId());
    const session = {
      id,
      deviceNo: normalizedDeviceNo,
      status: "authenticated",
      user,
      post: authenticated.post,
      binding: null,
    };
    this.sessions.set(id, session);
    return publicSession(session);
  }

  async getSession(sessionId) {
    return publicSession(this.#getSession(sessionId));
  }

  async listGrades(sessionId) {
    const session = this.#getSession(sessionId);
    const response = await session.post(
      `${this.restBaseUrl}/ai-lesson-eval/basic-data/get-grade-list`,
      {}
    );
    return normalizeListResponse(response, "grade list").map((grade) => ({
      gradeCode: requirePositiveInteger(grade?.gradeCode, "gradeCode"),
      gradeName: requireNonEmptyString(grade?.gradeName, "gradeName"),
    }));
  }

  async listClasses(sessionId, { gradeCode } = {}) {
    const session = this.#getSession(sessionId);
    const normalizedGradeCode = requirePositiveInteger(gradeCode, "gradeCode");
    const response = await session.post(
      `${this.restBaseUrl}/ai-lesson-eval/basic-data/get-class-list`,
      { gradeCode: normalizedGradeCode }
    );
    return normalizeListResponse(response, "class list").map((classroom) => ({
      classId: requirePositiveInteger(classroom?.classId, "classId"),
      className: requireNonEmptyString(classroom?.className, "className"),
    }));
  }

  async confirmBinding(sessionId, selection = {}) {
    const session = this.#getSession(sessionId);
    if (session.status !== "authenticated") {
      throw bindingError(
        "BINDING_SESSION_INVALID_STATE",
        "绑定会话已经使用，请重新登录"
      );
    }
    const request = bindingRequest(session, selection);
    const response = await session.post(
      `${this.restBaseUrl}/ai-lesson-eval/recording-device/bind-device`,
      request
    );
    requireSuccessfulMutation(response, "绑定失败");
    const classroomBinding = request.bindType === 1;
    const binding = {
      deviceNo: session.deviceNo,
      schoolId: session.user.schoolId,
      schoolName: session.user.schoolName,
      bindType: request.bindType,
      classId: classroomBinding ? String(request.classId) : "",
      className: classroomBinding
        ? requireNonEmptyString(selection.className, "className")
        : "",
      classroom: request.classroom,
      bindingSource: "remote",
      boundAt: new Date(this.now()).toISOString(),
    };
    session.status = "confirmed";
    session.binding = binding;
    this.sessions.delete(String(sessionId));
    return copy(binding);
  }

  async unbindDevice(sessionId) {
    const session = this.#getSession(sessionId);
    if (session.status !== "authenticated") {
      throw bindingError(
        "BINDING_SESSION_INVALID_STATE",
        "绑定会话已经使用，请重新登录"
      );
    }
    const response = await session.post(
      `${this.restBaseUrl}/ai-lesson-eval/recording-device/unbind-device`,
      { deviceNo: session.deviceNo }
    );
    requireSuccessfulMutation(response, "解绑失败");
    session.status = "confirmed";
    this.sessions.delete(String(sessionId));
    return { success: true };
  }

  #getSession(sessionId) {
    const session = this.sessions.get(String(sessionId));
    if (!session) {
      throw bindingError(
        "BINDING_SESSION_NOT_FOUND",
        "binding session was not found"
      );
    }
    return session;
  }
}

export function createBindingService(options = {}) {
  if (options.mode === "mock") return new MockBindingService(options);
  if (typeof options.authenticate === "function")
    return new RemoteBindingService(options);
  return new UnavailableRemoteBindingService();
}

function normalizeAuthenticatedUser(value) {
  if (!value || typeof value !== "object") {
    throw bindingError(
      "PASSPORT_IDENTITY_INVALID",
      "未读取到 Passport 登录身份"
    );
  }
  const user = {
    schoolId: requirePositiveInteger(value.schoolId, "schoolId"),
    schoolName: requireNonEmptyString(value.schoolName, "schoolName"),
    userName: requireNonEmptyString(value.userName, "userName"),
    userType: requireNonNegativeInteger(value.userType, "userType"),
  };
  if (user.userType !== 0) {
    throw bindingError(
      "PASSPORT_ROLE_NOT_ALLOWED",
      "当前身份不是教师侧身份，不能绑定录音设备"
    );
  }
  return user;
}

function publicSession(session) {
  return copy({
    id: session.id,
    deviceNo: session.deviceNo,
    status: session.status,
    user: session.user,
    binding: session.binding,
  });
}

function normalizeListResponse(value, field) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.data)) return value.data;
  throw bindingError(
    "BINDING_RESPONSE_INVALID",
    `${field} response is invalid`
  );
}

function requireSuccessfulMutation(value, fallback) {
  const success =
    value === true || value?.success === true || value?.data?.success === true;
  if (!success) {
    throw bindingError(
      "BINDING_REJECTED",
      requireOptionalMessage(value?.message || value?.data?.message) || fallback
    );
  }
}

function requireOptionalMessage(value) {
  return typeof value === "string" ? value.trim() : "";
}

function requirePositiveInteger(value, field) {
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    value = Number(value);
  }
  if (!Number.isInteger(value) || value <= 0) {
    throw bindingError(
      "BINDING_REQUEST_INVALID",
      `${field} must be a positive integer`
    );
  }
  return value;
}

function requireNonNegativeInteger(value, field) {
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    value = Number(value);
  }
  if (!Number.isInteger(value) || value < 0) {
    throw bindingError(
      "BINDING_REQUEST_INVALID",
      `${field} must be a non-negative integer`
    );
  }
  return value;
}

function bindingRequest(session, selection) {
  const bindType = Number(selection.bindType);
  if (bindType === 1) {
    const classId = requirePositiveInteger(selection.classId, "classId");
    const className = requireNonEmptyString(selection.className, "className");
    return {
      schoolId: session.user.schoolId,
      deviceNo: session.deviceNo,
      bindType,
      classId,
      classroom: `${className}录音设备`,
    };
  }
  if (bindType === 2) {
    return {
      schoolId: session.user.schoolId,
      deviceNo: session.deviceNo,
      bindType,
      classroom: requireNonEmptyString(selection.classroom, "classroom"),
    };
  }
  throw bindingError("BINDING_REQUEST_INVALID", "bindType must be 1 or 2");
}
