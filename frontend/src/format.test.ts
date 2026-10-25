import { describe, expect, it } from "vitest";
import { biasMeaning, isCutoff, mw, pct, signedMw } from "./format";

describe("format", () => {
  it("formats missing values as n/a", () => {
    expect(mw(null)).toBe("n/a");
    expect(pct(undefined)).toBe("n/a");
  });
  it("formats MW with thousands separators", () => {
    expect(mw(12345.6)).toBe("12,346 MW");
  });
  it("signs the bias", () => {
    expect(signedMw(250)).toBe("+250 MW");
    expect(signedMw(-250)).toBe("-250 MW");
  });
  it("explains bias direction", () => {
    expect(biasMeaning(300)).toContain("high");
    expect(biasMeaning(-300)).toContain("low");
    expect(biasMeaning(0.2)).toContain("No consistent");
  });
  it("validates cutoffs", () => {
    expect(isCutoff("09:00")).toBe(true);
    expect(isCutoff("9:00")).toBe(false);
    expect(isCutoff("24:00")).toBe(false);
  });
});
