export function createFloatingDragController({ onStart, onMove, onEnd, onClick, movementThreshold = 4 }) {
  let drag = { active: false, moved: false, startX: 0, startY: 0, lastX: 0, lastY: 0 };

  return {
    start({ x, y }) {
      drag = { active: true, moved: false, startX: x, startY: y, lastX: x, lastY: y };
      onStart?.({ x, y });
    },
    move({ x, y }) {
      if (!drag.active) return;
      if (x === drag.lastX && y === drag.lastY) return;
      drag.lastX = x;
      drag.lastY = y;
      drag.moved ||= Math.hypot(x - drag.startX, y - drag.startY) > movementThreshold;
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
