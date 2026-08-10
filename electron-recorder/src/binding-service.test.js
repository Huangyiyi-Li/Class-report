import assert from "node:assert/strict";
import test from "node:test";

import { createBindingService } from "./binding-service.js";
import { PRODUCTION_API_ROUTES, TEST_API_ROUTES } from "./api-routes.js";

const NOW = Date.parse("2026-07-15T08:00:00.000Z");

test("mock mode follows the same Passport-shaped grade and class contract", async () => {
  const service = createBindingService({
    mode: "mock",
    now: () => NOW,
    createId: () => "session-1",
  });
  const session = await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  assert.equal(session.status, "authenticated");
  assert.equal(session.user.schoolName, "星河实验学校");
  assert.deepEqual(await service.listGrades(session.id), [
    { gradeCode: 1, gradeName: "一年级" },
    { gradeCode: 2, gradeName: "二年级" },
  ]);
  assert.deepEqual(await service.listClasses(session.id, { gradeCode: 1 }), [
    { classId: 101, className: "1.1班" },
    { classId: 102, className: "1.2班" },
  ]);
});

test("mock mode creates canonical class and public classroom bindings", async () => {
  const service = createBindingService({
    mode: "mock",
    now: () => NOW,
    createId: () => "session-1",
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  assert.deepEqual(
    await service.confirmBinding("session-1", {
      bindType: 1,
      classId: 101,
      className: "1.1班",
    }),
    {
      deviceNo: "AABBCCDDEEFF",
      schoolId: 1001,
      schoolName: "星河实验学校",
      bindType: 1,
      classroom: "1.1班录音设备",
      classId: "101",
      className: "1.1班",
      bindingSource: "mock",
      boundAt: "2026-07-15T08:00:00.000Z",
    }
  );

  const second = createBindingService({
    mode: "mock",
    now: () => NOW,
    createId: () => "session-2",
  });
  await second.createSession({ deviceNo: "AABBCCDDEEFF" });
  const publicBinding = await second.confirmBinding("session-2", {
    bindType: 2,
    classroom: "  多媒体教室录音设备  ",
  });
  assert.equal(publicBinding.classId, "");
  assert.equal(publicBinding.className, "");
  assert.equal(publicBinding.classroom, "多媒体教室录音设备");
});

test("default remote mode fails closed and never exposes mock data", async () => {
  const service = createBindingService();
  await assert.rejects(service.createSession({ deviceNo: "AABBCCDDEEFF" }), {
    code: "BINDING_SERVICE_UNAVAILABLE",
  });
  await assert.rejects(service.listGrades("anything"), {
    code: "BINDING_SERVICE_UNAVAILABLE",
  });
  assert.equal(service.mode, "remote");
});

function remoteFixture(requests, mutationResponse = { content: "success" }) {
  return createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    now: () => NOW,
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async (url, payload) => {
        requests.push([url, payload]);
        if (url.endsWith("/grade-class-list"))
          return {
            code: 1,
            data: [
              {
                gradeId: 7,
                gradeName: "七年级",
                classId: 701,
                className: "七年级一班",
                studentCount: 36,
              },
            ],
          };
        return mutationResponse;
      },
    }),
    getApiRoutes: () => TEST_API_ROUTES,
  });
}

test("remote mode loads grades and classes from the shared grade-class-list API", async () => {
  const requests = [];
  const service = remoteFixture(requests);
  const session = await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  assert.equal(session.status, "authenticated");
  assert.equal(session.user.schoolId, 9001);
  assert.equal(session.user.userType, 0);
  assert.deepEqual(await service.listGrades(session.id), [
    { gradeCode: 7, gradeName: "七年级" },
  ]);
  assert.deepEqual(await service.listClasses(session.id, { gradeCode: 7 }), [
    { classId: 701, className: "七年级一班" },
  ]);
  assert.deepEqual(requests, [
    [
      "https://rest-test.xxt.cn/wisdom/group/grade-class-list",
      { schoolId: null },
    ],
  ]);
});

test("remote mode reads a newly saved route map without recreating the service", async () => {
  const requests = [];
  let routes = TEST_API_ROUTES;
  const service = createBindingService({
    mode: "remote",
    createId: () => "session-routes",
    getApiRoutes: () => routes,
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async (url, payload) => {
        requests.push([url, payload]);
        return [
          {
            gradeCode: 7,
            gradeName: "七年级",
            groupId: 701,
            groupName: "一班",
          },
        ];
      },
    }),
  });
  const session = await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  routes = PRODUCTION_API_ROUTES;
  await service.listGrades(session.id);
  assert.equal(requests[0][0], PRODUCTION_API_ROUTES.gradeClassList);
});

test("remote classroom binding sends the confirmed request contract", async () => {
  const requests = [];
  const service = remoteFixture(requests);
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  const binding = await service.confirmBinding("passport-session-1", {
    bindType: 1,
    classId: 701,
    className: "七年级一班",
  });
  assert.deepEqual(requests[0], [
    TEST_API_ROUTES.bindDevice,
    {
      schoolId: 9001,
      deviceNo: "AABBCCDDEEFF",
      bindType: 1,
      classId: 701,
      classroom: "七年级一班录音设备",
    },
  ]);
  assert.equal(binding.classroom, "七年级一班录音设备");
  assert.equal(binding.bindingSource, "remote");
});

test("remote binding rejects business failure and consumes a successful session once", async () => {
  let response = { success: false, message: "设备已被其他学校绑定" };
  const service = createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async () => response,
    }),
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  const selection = { bindType: 1, classId: 701, className: "七年级一班" };
  await assert.rejects(
    service.confirmBinding("passport-session-1", selection),
    {
      code: "BINDING_REJECTED",
    }
  );
  response = { content: "success" };
  await service.confirmBinding("passport-session-1", selection);
  await assert.rejects(
    service.confirmBinding("passport-session-1", selection),
    {
      code: "BINDING_SESSION_NOT_FOUND",
    }
  );
});

test("remote binding accepts the backend SimpleSuccessVO contract", async () => {
  const service = createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async () => ({ content: "success" }),
    }),
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  const binding = await service.confirmBinding("passport-session-1", {
    bindType: 1,
    classId: 701,
    className: "七年级一班",
  });

  assert.equal(binding.classId, "701");
  assert.equal(binding.classroom, "七年级一班录音设备");
});

test("remote mutation accepts only top-level SimpleSuccessVO content", async () => {
  const service = createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async () => ({ success: true }),
    }),
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  await assert.rejects(
    service.confirmBinding("passport-session-1", {
      bindType: 1,
      classId: 701,
      className: "七年级一班",
    }),
    { code: "BINDING_REJECTED" }
  );
});

test("remote binding reports the backend business message when code is not successful", async () => {
  const service = createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async () => ({ code: 5, msg: "设备已绑定其他的班级或者教室" }),
    }),
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  await assert.rejects(
    service.confirmBinding("passport-session-1", {
      bindType: 1,
      classId: 701,
      className: "七年级一班",
    }),
    {
      code: "BINDING_REJECTED",
      message: "设备已绑定其他的班级或者教室",
    }
  );
});

test("remote binding never treats a business error code as SimpleSuccessVO", async () => {
  const service = createBindingService({
    mode: "remote",
    createId: () => "passport-session-1",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试教师",
        userType: 0,
      },
      post: async () => ({ code: 1, msg: "学校不存在" }),
    }),
  });
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });

  await assert.rejects(
    service.confirmBinding("passport-session-1", {
      bindType: 1,
      classId: 701,
      className: "七年级一班",
    }),
    {
      code: "BINDING_REJECTED",
      message: "学校不存在",
    }
  );
});

test("Passport student identity is rejected before catalog access", async () => {
  const service = createBindingService({
    mode: "remote",
    authenticate: async () => ({
      user: {
        schoolId: 9001,
        schoolName: "众享中学",
        userName: "测试学生",
        userType: 2,
      },
      post: async () => ({ success: true }),
    }),
  });
  await assert.rejects(service.createSession({ deviceNo: "AABBCCDDEEFF" }), {
    code: "PASSPORT_ROLE_NOT_ALLOWED",
  });
});

test("remote public classroom omits classId and unbind only sends deviceNo", async () => {
  const requests = [];
  const service = remoteFixture(requests);
  await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  await service.confirmBinding("passport-session-1", {
    bindType: 2,
    classroom: "  多媒体教室录音设备  ",
  });
  assert.deepEqual(requests[0][1], {
    schoolId: 9001,
    deviceNo: "AABBCCDDEEFF",
    bindType: 2,
    classroom: "多媒体教室录音设备",
  });
  const unbindService = remoteFixture(requests);
  await unbindService.createSession({ deviceNo: "AABBCCDDEEFF" });
  await unbindService.unbindDevice("passport-session-1");
  assert.deepEqual(requests[1], [
    TEST_API_ROUTES.unbindDevice,
    { deviceNo: "AABBCCDDEEFF" },
  ]);
});

test("remote unbind accepts only top-level content success", async () => {
  for (const response of [
    { success: true },
    { data: { content: "success" } },
    { content: "failed" },
  ]) {
    const service = remoteFixture([], response);
    await service.createSession({ deviceNo: "AABBCCDDEEFF" });
    await assert.rejects(
      service.unbindDevice("passport-session-1"),
      (error) => error.code === "BINDING_REJECTED"
    );
  }
});
