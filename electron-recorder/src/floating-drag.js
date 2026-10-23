export function createFloatingDragController({
  onStart,
  onMove,
  onEnd,
  onClick,
  movementThreshold = 4,
}) {
  let drag = {
    active: false,
    moved: false,
    startX: 0,
    startY: 0,
    lastX: 0,
    lastY: 0,
  };

  return {
    start({ x, y }) {
      drag = {
        active: true,
        moved: false,
        startX: x,
        startY: y,
        lastX: x,
        lastY: y,
      };
      onStart?.({ x, y });
    },
    move({ x, y }) {
      if (!drag.active) return;
      if (x === drag.lastX && y === drag.lastY) return;
      drag.lastX = x;
      drag.lastY = y;
      drag.moved ||=
        Math.hypot(x - drag.startX, y - drag.startY) > movementThreshold;
      onMove?.({ x, y });
    },
    end() {
      if (!drag.active) return;
      const moved = drag.moved;
      drag.active = false;
      onEnd?.();
      if (!moved) onClick?.();
    },
    cancel() {
      if (!drag.active) return;
      drag.active = false;
      onEnd?.();
    },
  };
}

export function clampFloatingPosition({ point, offset, bounds, workArea }) {
  const maximumX = workArea.x + Math.max(0, workArea.width - bounds.width);
  const maximumY = workArea.y + Math.max(0, workArea.height - bounds.height);
  return {
    x: Math.min(maximumX, Math.max(workArea.x, Math.round(point.x - offset.x))),
    y: Math.min(maximumY, Math.max(workArea.y, Math.round(point.y - offset.y))),
  };
}

// Windows clips the opaque native window to this one capsule outline.
// The web view fills it; there is no larger transparent circle underneath.
export function createFloatingCapsuleShape(width, height) {
  const radius = height / 2;
  return Array.from({ length: height }, (_, y) => {
    const dy = y + 0.5 - radius;
    const x = Math.round(radius - Math.sqrt(radius * radius - dy * dy));
    return { x, y, width: width - 2 * x, height: 1 };
  });
}

export function restoreFloatingPosition({ position, bounds, workAreas }) {
  const primary = workAreas[0];
  const point = position || {
    x: primary.x + primary.width - bounds.width - 22,
    y: primary.y + 128,
  };
  const distance = (area) => {
    const dx = Math.max(area.x - point.x, 0, point.x - area.x - area.width);
    const dy = Math.max(area.y - point.y, 0, point.y - area.y - area.height);
    return dx * dx + dy * dy;
  };
  const workArea = workAreas.reduce(
    (best, area) => (distance(area) < distance(best) ? area : best),
    primary
  );
  return clampFloatingPosition({
    point,
    offset: { x: 0, y: 0 },
    bounds,
    workArea,
  });
}
