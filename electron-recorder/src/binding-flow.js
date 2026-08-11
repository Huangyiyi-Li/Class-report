export const initialBindingFlow = Object.freeze({
  phase: "closed",
  session: null,
  grades: [],
  classes: [],
  selection: {},
  binding: null,
  error: null,
});

export function bindingFlowReducer(state, action) {
  switch (action.type) {
    case "OPEN":
    case "RESTART":
      return { ...initialBindingFlow, phase: "creating" };
    case "SESSION_UPDATED":
      return {
        ...state,
        session: action.session,
        phase:
          action.session?.status === "authenticated"
            ? "bindingType"
            : state.phase,
        error: null,
      };
    case "SELECT_BIND_TYPE":
      if (action.bindType === 1) {
        return {
          ...state,
          phase: "loadingGrades",
          grades: [],
          classes: [],
          selection: { bindType: 1 },
        };
      }
      if (action.bindType === 2) {
        return {
          ...state,
          phase: "publicClassroom",
          grades: [],
          classes: [],
          selection: { bindType: 2 },
        };
      }
      return state;
    case "GRADES_LOADED":
      return {
        ...state,
        grades: action.grades || [],
        phase: "grade",
        error: null,
      };
    case "SELECT_GRADE":
      return {
        ...state,
        phase: "loadingClasses",
        classes: [],
        selection: { bindType: 1, gradeCode: action.gradeCode },
      };
    case "CLASSES_LOADED":
      return {
        ...state,
        classes: action.classes || [],
        phase: "class",
        error: null,
      };
    case "SELECT_CLASS": {
      const selected = state.classes.find(
        ({ classId }) => String(classId) === String(action.classId)
      );
      if (!selected) return state;
      return {
        ...state,
        phase: "review",
        selection: {
          ...state.selection,
          classId: selected.classId,
          className: selected.className,
        },
      };
    }
    case "REVIEW_PUBLIC": {
      const classroom = String(action.classroom || "").trim();
      if (!classroom) return state;
      return {
        ...state,
        phase: "review",
        selection: { bindType: 2, classroom },
      };
    }
    case "CONFIRMING":
      return { ...state, phase: "confirming", error: null };
    case "CONFIRMED":
      return {
        ...state,
        phase: "confirmed",
        binding: action.binding,
        error: null,
      };
    case "ERROR":
      return { ...state, phase: "error", error: action.error };
    case "BACK":
      return back(state);
    case "RETURN_TO_SELECTION":
      return {
        ...state,
        phase: state.selection.bindType === 2 ? "publicClassroom" : "class",
        error: null,
      };
    case "CLOSE":
      return initialBindingFlow;
    default:
      return state;
  }
}

export function canRebind(snapshot = {}) {
  const recording =
    snapshot.recordingState ||
    snapshot.recording ||
    snapshot.runtime?.recording ||
    "idle";
  return recording === "idle";
}

export async function beginFullRebinding({
  confirm,
  unbindDevice,
  openBinding,
}) {
  if (!confirm()) return false;
  await unbindDevice();
  openBinding();
  return true;
}

function back(state) {
  if (state.phase === "grade") {
    return { ...state, phase: "bindingType", grades: [], selection: {} };
  }
  if (["class", "loadingClasses"].includes(state.phase)) {
    return {
      ...state,
      phase: "grade",
      classes: [],
      selection: { bindType: 1 },
    };
  }
  if (state.phase === "publicClassroom") {
    return { ...state, phase: "bindingType", selection: {} };
  }
  if (state.phase === "review") {
    return {
      ...state,
      phase: state.selection.bindType === 2 ? "publicClassroom" : "class",
    };
  }
  return state;
}
