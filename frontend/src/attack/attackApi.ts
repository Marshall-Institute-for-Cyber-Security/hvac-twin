const STORAGE_KEY = "hvac-twin.console-base";
const DEFAULT_CONSOLE_BASE = "http://127.0.0.1:8000";

/** Same runtime-configurable-target pattern as the operator console's
 * config.ts, for the same reason: this page runs on the attacking
 * student group's own laptop, pointed at whichever machine is running
 * hvac_twin.console that session. */
function readStoredConsoleBase(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getConsoleBase(): string {
  return readStoredConsoleBase() ?? DEFAULT_CONSOLE_BASE;
}

export function setConsoleBase(url: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, url);
  } catch {
    // storage unavailable -- the connection bar just won't persist across reloads
  }
}

export type ScenarioState = "idle" | "running" | "done" | "error";

export interface ScenarioStatus {
  name: string;
  state: ScenarioState;
  detail: string | null;
}

async function asScenarioStatus(response: Response): Promise<ScenarioStatus> {
  const body = (await response.json()) as ScenarioStatus | { detail: string };
  if (!response.ok) {
    throw new Error("detail" in body && typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
  }
  return body as ScenarioStatus;
}

export async function listAttacks(): Promise<ScenarioStatus[]> {
  const response = await fetch(`${getConsoleBase()}/attacks`);
  if (!response.ok) throw new Error(`/attacks -> ${response.status}`);
  return (await response.json()) as ScenarioStatus[];
}

export async function startAttack(
  name: string,
  body: Record<string, unknown>,
): Promise<ScenarioStatus> {
  const response = await fetch(`${getConsoleBase()}/attacks/${name}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return asScenarioStatus(response);
}

export async function stopAttack(name: string): Promise<ScenarioStatus> {
  const response = await fetch(`${getConsoleBase()}/attacks/${name}/stop`, { method: "POST" });
  return asScenarioStatus(response);
}

export interface ModbusExecResult {
  ok: boolean;
  values: unknown[] | null;
}

export interface ModbusExecRequest {
  host: string;
  port: number;
  unit_id: number;
  operation: string;
  address: number;
  quantity: number;
  values: number[] | null;
}

export async function execModbus(body: ModbusExecRequest): Promise<ModbusExecResult> {
  const response = await fetch(`${getConsoleBase()}/modbus/exec`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as ModbusExecResult | { detail: string };
  if (!response.ok) {
    throw new Error(
      "detail" in data && typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`,
    );
  }
  return data as ModbusExecResult;
}
