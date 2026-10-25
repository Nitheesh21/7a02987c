export const mw = (v: number | null | undefined, digits = 0): string =>
  v == null ? "n/a" : `${v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;

export const mwh = (v: number | null | undefined): string =>
  v == null ? "n/a" : `${Math.round(v).toLocaleString("en-GB")} MWh`;

export const pct = (v: number | null | undefined, digits = 1): string =>
  v == null ? "n/a" : `${(v * 100).toFixed(digits)}%`;

export const hours = (v: number | null | undefined): string => (v == null ? "n/a" : `${v.toFixed(1)} h`);

/** Signed MW, so the direction of a bias is obvious. */
export const signedMw = (v: number | null | undefined): string => {
  if (v == null) return "n/a";
  const r = Math.round(v);
  return `${r > 0 ? "+" : ""}${r.toLocaleString("en-GB")} MW`;
};

/** Plain-English reading of the bias. Error = forecast minus actual. */
export const biasMeaning = (bias: number | null | undefined): string => {
  if (bias == null) return "No data";
  if (Math.abs(bias) < 1) return "No consistent lean";
  return bias > 0 ? "Forecast ran high (less wind than predicted)" : "Forecast ran low (more wind than predicted)";
};

export const shortDate = (iso: string): string =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", weekday: "short", timeZone: "UTC" });

export const isCutoff = (v: string): boolean => /^([01]\d|2[0-3]):[0-5]\d$/.test(v);
