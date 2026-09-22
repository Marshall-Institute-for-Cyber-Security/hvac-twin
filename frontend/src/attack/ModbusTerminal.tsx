import { useState, type FormEvent } from "react";
import { Field } from "./Field";
import { execModbus } from "./attackApi";

const OPERATIONS = [
  { value: "read_coils", label: "Read Coils" },
  { value: "read_discrete_inputs", label: "Read Discrete Inputs" },
  { value: "read_holding_registers", label: "Read Holding Registers" },
  { value: "read_input_registers", label: "Read Input Registers" },
  { value: "write_coil", label: "Write Coil" },
  { value: "write_coils", label: "Write Coils" },
  { value: "write_register", label: "Write Register" },
  { value: "write_registers", label: "Write Registers" },
] as const;

type Operation = (typeof OPERATIONS)[number]["value"];

const READ_OPS = new Set<Operation>([
  "read_coils",
  "read_discrete_inputs",
  "read_holding_registers",
  "read_input_registers",
]);

interface LogEntry {
  id: number;
  command: string;
  result: string;
  ok: boolean;
}

let nextLogId = 1;

/** The raw primitive under every canned scenario in this console,
 * exposed directly -- students build one Modbus request by hand instead
 * of only running the five pre-built attacks. */
export function ModbusTerminal() {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("5020");
  const [unitId, setUnitId] = useState("1");
  const [operation, setOperation] = useState<Operation>("read_holding_registers");
  const [address, setAddress] = useState("0");
  const [quantity, setQuantity] = useState("1");
  const [values, setValues] = useState("0");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<LogEntry[]>([]);

  const isRead = READ_OPS.has(operation);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    const parsedValues = values
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v.length > 0)
      .map(Number);
    const command = `${operation} host=${host}:${port} unit=${unitId} addr=${address}${
      isRead ? ` qty=${quantity}` : ` values=[${parsedValues.join(",")}]`
    }`;
    try {
      const result = await execModbus({
        host,
        port: Number(port),
        unit_id: Number(unitId),
        operation,
        address: Number(address),
        quantity: Number(quantity),
        values: isRead ? null : parsedValues,
      });
      setLog((prev) => [
        ...prev,
        {
          id: nextLogId++,
          command,
          result: result.values !== null ? JSON.stringify(result.values) : "OK",
          ok: true,
        },
      ]);
    } catch (error) {
      setLog((prev) => [...prev, { id: nextLogId++, command, result: String(error), ok: false }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="panel scenario-card modbus-terminal" onSubmit={submit}>
      <div className="panel__header">
        <h2 className="panel__title">Modbus Terminal</h2>
      </div>
      <p className="scenario-card__desc">
        Build and send your own Modbus TCP request against any host:port -- the same raw
        primitive every canned attack above uses, with no scenario wrapped around it.
      </p>
      <div className="scenario-card__fields">
        <Field label="Host" value={host} onChange={setHost} />
        <Field label="Port" value={port} onChange={setPort} type="number" />
        <Field label="Unit ID" value={unitId} onChange={setUnitId} type="number" />
        <label className="field">
          <span className="field__label">Operation</span>
          <select
            className="field__input"
            value={operation}
            onChange={(event) => setOperation(event.target.value as Operation)}
          >
            {OPERATIONS.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>
        </label>
        <Field label="Address" value={address} onChange={setAddress} type="number" />
        {isRead ? (
          <Field label="Quantity" value={quantity} onChange={setQuantity} type="number" />
        ) : (
          <Field label="Values (comma-separated)" value={values} onChange={setValues} />
        )}
      </div>
      <div className="scenario-card__actions">
        <button type="submit" className="view-toggle__btn view-toggle__btn--active" disabled={busy}>
          Send
        </button>
      </div>
      <div className="modbus-terminal__log">
        {log.length === 0 ? (
          <p className="event-log__empty">No commands sent yet.</p>
        ) : (
          log
            .slice()
            .reverse()
            .map((entry) => (
              <div key={entry.id} className="modbus-terminal__entry">
                <span className="modbus-terminal__cmd">&gt; {entry.command}</span>
                <span
                  className={
                    entry.ok
                      ? "modbus-terminal__result"
                      : "modbus-terminal__result modbus-terminal__result--error"
                  }
                >
                  {entry.result}
                </span>
              </div>
            ))
        )}
      </div>
    </form>
  );
}
