export function money(amount: string, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(amount));
}

const UNITS: [Intl.RelativeTimeFormatUnit, number, string][] = [
  ["day", 86400, "d"],
  ["hour", 3600, "h"],
  ["minute", 60, "min"],
];

/** "2 min ago" / "1 h ago" in lists (the spec's short form); "2 minutes ago" on the Case header. */
export function relativeTime(iso: string, style: "short" | "long" = "short", now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  if (Math.abs(seconds) < 60) return "just now";
  for (const [unit, size, abbr] of UNITS) {
    if (Math.abs(seconds) >= size) {
      const n = Math.round(seconds / size);
      if (style === "short") return n < 0 ? `${-n} ${abbr} ago` : `in ${n} ${abbr}`;
      return new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(n, unit);
    }
  }
  return "just now";
}

export function clock(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone }).format(
    new Date(iso),
  );
}

export function languageName(code: string): string {
  try {
    return new Intl.DisplayNames(["en"], { type: "language" }).of(code.split("-")[0]) ?? code;
  } catch {
    return code;
  }
}

export function lowerFirst(text: string): string {
  return text ? text[0].toLowerCase() + text.slice(1) : text;
}
