import { useState, type FormEvent } from "react";
import type { ApiTarget } from "../config";
import { getApiBase, setApiBase } from "../config";

interface ConnectionBarProps {
  target?: Pick<ApiTarget, "getApiBase" | "setApiBase">;
  placeholder?: string;
}

/** Lets whoever opens this page on their own laptop point it at whichever
 * plant machine's backend they've been assigned, without a rebuild.
 * Reconnecting reloads the page -- simplest way to cleanly reset the
 * WebSocket and every poll loop against the new target. Defaults to the
 * closet's own target; a second twin's screen passes its own instead. */
export function ConnectionBar({
  target = { getApiBase, setApiBase },
  placeholder = "http://192.168.1.42:8100",
}: ConnectionBarProps) {
  const [value, setValue] = useState(target.getApiBase());

  const connect = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length === 0) return;
    target.setApiBase(trimmed);
    window.location.reload();
  };

  return (
    <form className="connection-bar" onSubmit={connect}>
      <span className="connection-bar__label">Target</span>
      <input
        className="connection-bar__input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
      <button type="submit" className="connection-bar__btn">
        Connect
      </button>
    </form>
  );
}
