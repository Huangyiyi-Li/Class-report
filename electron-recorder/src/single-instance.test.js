import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { configureSingleInstance } from "./single-instance.js";

test("second Electron instance exits before startup", () => {
  const app = new EventEmitter();
  let quits = 0;
  app.requestSingleInstanceLock = () => false;
  app.quit = () => { quits += 1; };
  assert.equal(configureSingleInstance(app, () => {}), false);
  assert.equal(quits, 1);
});

test("primary Electron instance focuses its existing window", () => {
  const app = new EventEmitter();
  let focused = 0;
  app.requestSingleInstanceLock = () => true;
  app.quit = () => {};
  assert.equal(configureSingleInstance(app, () => { focused += 1; }), true);
  app.emit("second-instance");
  assert.equal(focused, 1);
});
