export interface ApiTarget {
  getApiBase: () => string;
  setApiBase: (url: string) => void;
  getWsBase: () => string;
}

/** A backend's address is a runtime choice, not a build-time one -- a
 * classroom deployment has one frontend build pointed at whichever plant
 * laptop's IP a given pair of students is assigned that session, so
 * baking it into the bundle would mean rebuilding per pairing. Each twin
 * this frontend talks to (the closet, the office wing, ...) gets its own
 * storage key and default via this factory, since each is its own
 * backend process on its own port -- not a shared setting. Falls back to
 * `defaultApiBase` if storage is unavailable (private browsing, etc). */
export function createApiTarget(storageKey: string, defaultApiBase: string): ApiTarget {
  function readStored(): string | null {
    try {
      return window.localStorage.getItem(storageKey);
    } catch {
      return null;
    }
  }

  function getApiBase(): string {
    return readStored() ?? defaultApiBase;
  }

  function setApiBase(url: string): void {
    try {
      window.localStorage.setItem(storageKey, url);
    } catch {
      // storage unavailable -- the connection bar just won't persist across reloads
    }
  }

  function getWsBase(): string {
    return getApiBase().replace(/^http/, "ws");
  }

  return { getApiBase, setApiBase, getWsBase };
}

const DEFAULT_API_BASE =
  (import.meta.env.VITE_HMI_API_BASE as string | undefined) ?? "http://127.0.0.1:8100";

export const { getApiBase, setApiBase, getWsBase } = createApiTarget(
  "hvac-twin.api-base",
  DEFAULT_API_BASE,
);
