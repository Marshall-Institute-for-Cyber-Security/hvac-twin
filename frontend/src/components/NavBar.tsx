interface NavLink {
  href: string;
  label: string;
}

const LINKS: NavLink[] = [
  { href: "/index.html", label: "Overview" },
  { href: "/closet.html", label: "Server Closet" },
  { href: "/office.html", label: "Office Wing" },
  { href: "/attack.html", label: "Red Team" },
  { href: "/defenses.html", label: "Defenses" },
];

/** Plain <a> links between the app's separate HTML entries, not client-side
 * routes -- matches vite.config.ts's deliberate one-page-per-entry design,
 * so this needs no router and works identically from any of them. */
export function NavBar() {
  const path = typeof window !== "undefined" ? window.location.pathname : "";
  const isActive = (href: string) =>
    path === href || (href === "/index.html" && (path === "/" || path === ""));

  return (
    <nav className="nav-bar">
      <span className="nav-bar__brand">ICS BMS Sim</span>
      <div className="nav-bar__links">
        {LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className={
              isActive(link.href) ? "nav-bar__link nav-bar__link--active" : "nav-bar__link"
            }
          >
            {link.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
