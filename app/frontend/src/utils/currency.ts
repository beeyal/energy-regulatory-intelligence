/**
 * Market-aware currency formatting utilities.
 * All monetary values in the UI should route through these helpers
 * so switching market automatically updates currency display.
 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  AUD: "A$",
  SGD: "S$",
  NZD: "NZ$",
  JPY: "¥",
  INR: "₹",
  KRW: "₩",
  THB: "฿",
  PHP: "₱",
};

/** Currencies that display without decimal fractions */
const NO_DECIMAL_CURRENCIES = new Set(["JPY", "KRW"]);

/**
 * Format a monetary value with abbreviated suffix (K / M / B).
 * Falls back to the raw number with currency symbol if below 1K.
 */
export function formatCurrency(val: string | number | null | undefined, currencyCode = "AUD"): string {
  if (val === null || val === undefined || val === "" || val === "None") return "—";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n) || n === 0) return "—";

  const sym = CURRENCY_SYMBOLS[currencyCode] ?? `${currencyCode} `;
  const noDecimal = NO_DECIMAL_CURRENCIES.has(currencyCode);

  if (n >= 1e9) return `${sym}${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${sym}${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${sym}${(n / 1e3).toFixed(0)}K`;
  return `${sym}${noDecimal ? Math.round(n).toLocaleString() : n.toFixed(0)}`;
}

/**
 * Format a full (non-abbreviated) monetary value using the market locale.
 */
export function formatCurrencyFull(val: string | number | null | undefined, currencyCode = "AUD"): string {
  if (val === null || val === undefined || val === "" || val === "None") return "—";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n) || n === 0) return "—";

  const sym = CURRENCY_SYMBOLS[currencyCode] ?? `${currencyCode} `;
  const LOCALE: Record<string, string> = {
    AUD: "en-AU", SGD: "en-SG", NZD: "en-NZ",
    JPY: "ja-JP", INR: "en-IN", KRW: "ko-KR",
    THB: "th-TH", PHP: "en-PH",
  };
  const locale = LOCALE[currencyCode] ?? "en-AU";
  return `${sym}${n.toLocaleString(locale, { maximumFractionDigits: 0 })}`;
}
