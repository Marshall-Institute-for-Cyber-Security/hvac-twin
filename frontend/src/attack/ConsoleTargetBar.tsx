import { useState, type FormEvent } from "react";
import { getConsoleBase, setConsoleBase } from "./attackApi";

export function ConsoleTargetBar() {
  const [value, setValue] = useState(getConsoleBase());

  const connect = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length === 0) return;
    setConsoleBase(trimmed);
    window.location.reload();
  };

  return (
    <form className="connection-bar" onSubmit={connect}>
      <span className="connection-bar__label">Console</span>
      <input
        className="connection-bar__input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="http://192.168.1.42:8000"
        spellCheck={false}
      />
      <button type="submit" className="connection-bar__btn">
        Connect
      </button>
    </form>
  );
}
