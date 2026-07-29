import assert from "node:assert/strict";
import test from "node:test";

import {
  API_ROUTE_DEFINITIONS,
  PRODUCTION_API_ROUTES,
  TEST_API_ROUTES,
  detectApiEnvironment,
  validateApiRoutes,
} from "./api-routes.js";

test("test and production presets expose every editable recorder API", () => {
  assert.deepEqual(Object.keys(TEST_API_ROUTES), [
    "deviceAuth",
    "gradeClassList",
    "bindDevice",
    "unbindDevice",
    "ossToken",
    "saveAudioFileInfo",
  ]);
  assert.equal(
    TEST_API_ROUTES.gradeClassList,
    "http://rest-test.xxt.cn/wisdom/group/grade-class-list"
  );
  assert.equal(
    PRODUCTION_API_ROUTES.gradeClassList,
    "http://rest.xxt.cn/wisdom/group/grade-class-list"
  );
  assert.equal(API_ROUTE_DEFINITIONS.length, 6);
});

test("editable API routes accept complete http/https URL maps and detect presets", () => {
  assert.equal(detectApiEnvironment(TEST_API_ROUTES), "test");
  assert.equal(detectApiEnvironment(PRODUCTION_API_ROUTES), "production");
  const custom = {
    ...TEST_API_ROUTES,
    deviceAuth: "https://gateway.example.test/device-auth",
  };
  assert.deepEqual(validateApiRoutes(custom), custom);
  assert.equal(detectApiEnvironment(custom), "custom");
});

test("API route validation fails closed for partial or unsafe values", () => {
  assert.throws(
    () => validateApiRoutes({ ...TEST_API_ROUTES, deviceAuth: "" }),
    /deviceAuth/
  );
  assert.throws(
    () =>
      validateApiRoutes({
        ...TEST_API_ROUTES,
        gradeClassList: "file:///tmp/catalog.json",
      }),
    /http/
  );
  assert.throws(
    () => validateApiRoutes({ ...TEST_API_ROUTES, extra: "https://x.test" }),
    /extra/
  );
});
