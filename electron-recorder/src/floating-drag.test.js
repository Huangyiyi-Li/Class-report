import test from "node:test";
import assert from "node:assert/strict";
import {
  clampFloatingPosition,
  createFloatingDragController,
} from "./floating-drag.js";

test("window-generated pointer moves cannot keep moving after the cursor stops", () => {
  const moves = [];
  const controller = createFloatingDragController({
    onMove: (point) => moves.push(point),
  });

  controller.start({ x: 100, y: 100 });
  controller.move({ x: 124, y: 116 });
  controller.move({ x: 124, y: 116 });
  controller.move({ x: 124, y: 116 });

  assert.deepEqual(moves, [{ x: 124, y: 116 }]);
});

test("drag cancellation ends capture without opening the main window", () => {
  let ended = 0;
  let clicked = 0;
  const controller = createFloatingDragController({
    onEnd: () => (ended += 1),
    onClick: () => (clicked += 1),
  });

  controller.start({ x: 100, y: 100 });
  controller.cancel();

  assert.equal(ended, 1);
  assert.equal(clicked, 0);
});

test("floating position stays fully inside the active display work area", () => {
  const common = {
    offset: { x: 36, y: 36 },
    bounds: { width: 72, height: 72 },
    workArea: { x: 0, y: 0, width: 1920, height: 1040 },
  };

  assert.deepEqual(
    clampFloatingPosition({ ...common, point: { x: -100, y: -80 } }),
    { x: 0, y: 0 }
  );
  assert.deepEqual(
    clampFloatingPosition({ ...common, point: { x: 2200, y: 1300 } }),
    { x: 1848, y: 968 }
  );
  assert.deepEqual(
    clampFloatingPosition({ ...common, point: { x: 500, y: 400 } }),
    { x: 464, y: 364 }
  );
});

test("capsule clipping uses symmetric integer rows with no outer rim", async () => {
  const { createFloatingCapsuleShape } = await import("./floating-drag.js");
  assert.equal(typeof createFloatingCapsuleShape, "function");
  const rows = createFloatingCapsuleShape(88, 24);
  assert.equal(rows.length, 24);
  for (const row of rows) {
    assert.equal(row.x * 2 + row.width, 88);
    assert.equal(row.height, 1);
    assert.ok(Number.isInteger(row.x));
    assert.ok(row.width > 0);
    assert.deepEqual({ ...rows[23 - row.y], y: row.y }, row);
  }
  assert.ok(rows[0].x > 0);
  assert.equal(rows[11].x, 0);
});
