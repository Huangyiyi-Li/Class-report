export const initialBindingFlow = Object.freeze({
  phase: "closed",
  session: null,
  schools: [],
  locations: [],
  selection: {},
  binding: null,
  error: null,
});

export function bindingFlowReducer(state, action) {
  switch (action.type) {
    case "OPEN":
    case "RESTART":
      return { ...initialBindingFlow, phase: "creating" };
    case "SESSION_UPDATED": {
      const status = action.session?.status;
      const phase = status === "waiting" ? "waiting" : status === "scanned" ? "scanned" :
        status === "expired" ? "expired" : status === "confirmed" ? "confirmed" : state.phase;
      return { ...state, session: action.session, phase, error: null };
    }
    case "SCHOOLS_LOADED":
      return { ...state, schools: action.schools || [], phase: "school", error: null };
    case "SELECT_SCHOOL":
      return {
        ...state,
        phase: "locationType",
        locations: [],
        selection: { schoolId: action.schoolId },
      };
    case "SELECT_LOCATION_TYPE":
      return {
        ...state,
        phase: "loadingLocations",
        locations: [],
        selection: normalizeSelection({ ...state.selection, locationType: action.locationType }),
      };
    case "LOCATIONS_LOADED":
      return { ...state, locations: action.locations || [], phase: "location", error: null };
    case "SELECT_LOCATION":
      return {
        ...state,
        phase: "review",
        selection: normalizeSelection({ ...state.selection, locationId: action.locationId }),
      };
    case "CONFIRMING":
      return { ...state, phase: "confirming", error: null };
    case "CONFIRMED":
      return { ...state, phase: "confirmed", binding: action.binding, error: null };
    case "ERROR":
      return { ...state, phase: "error", error: action.error };
    case "BACK":
      return back(state);
    case "CLOSE":
      return initialBindingFlow;
    default:
      return state;
  }
}

export function normalizeSelection(selection = {}) {
  if (selection.locationType !== "studio") return { ...selection };
  return { ...selection, classId: "", className: "" };
}

export function canRebind(snapshot = {}) {
  const recording = snapshot.recordingState || snapshot.recording || snapshot.runtime?.recording || "idle";
  return recording === "idle";
}

export function canSimulateScan(mode) {
  return mode === "mock";
}

function back(state) {
  if (["location", "loadingLocations"].includes(state.phase)) {
    return { ...state, phase: "locationType", locations: [], selection: { schoolId: state.selection.schoolId } };
  }
  if (state.phase === "review") return { ...state, phase: "location" };
  if (state.phase === "locationType") return { ...state, phase: "school", selection: {} };
  return state;
}
