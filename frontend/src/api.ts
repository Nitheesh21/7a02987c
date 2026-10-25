import { useQuery } from "@tanstack/react-query";

export interface Metrics {
  count: number;
  bias: number | null;
  mae: number | null;
  rmse: number | null;
  nmae: number | null;
  p90_abs_error: number | null;
  p95_abs_error: number | null;
  p90_shortfall_buffer_mw: number | null;
}
export interface Meta {
  delivery_start: string;
  delivery_end: string;
  default_cutoff: string;
  timezone: string;
  last_forecast_publish_utc: string | null;
  data_quality: {
    actuals: { missing_count: number; expected_half_hours: number };
    forecasts: {
      publish_count: number;
      resolution_minutes: number;
      max_horizon_h: number | null;
      publish_gap_hours: { min: number | null; median: number | null; max: number | null };
    };
  };
}
export interface Point {
  start_time_utc: string;
  uk_time: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  publish_time_utc: string | null;
  horizon_h: number | null;
  band_low_mw: number | null;
  band_high_mw: number | null;
}
export interface DaySummary {
  energy_mwh: number | null;
  peak_mw: number | null;
  min_mw: number | null;
  avg_mw: number | null;
  avg_horizon_h: number | null;
  p90_shortfall_buffer_mw: number | null;
  coverage: number;
}
export interface ForecastResponse {
  delivery_date: string;
  cutoff_utc: string;
  cutoff_uk: string;
  summary: DaySummary;
  points: Point[];
}
export interface ForecastDay extends DaySummary {
  delivery_date: string;
  day_mae: number | null;
}
export interface Summary {
  cutoff: string;
  start: string;
  end: string;
  metrics: Metrics;
  coverage: number;
  error_band_p10_mw: number | null;
  error_band_p90_mw: number | null;
  band_coverage: number | null;
  definition: string;
}
export interface ErrRow {
  count: number;
  mae: number | null;
  bias: number | null;
}
export interface DayRow extends ErrRow { date: string }
export interface HourRow extends ErrRow { hour: number }
export interface HorizonRow extends ErrRow { bucket: string; bucket_start_h: number }
export interface LevelRow extends ErrRow {
  quartile: number;
  forecast_min_mw: number;
  forecast_max_mw: number;
}
export interface Distribution {
  histogram: { edges: number[]; counts: number[] };
  by_level: LevelRow[];
}

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

const q = <T,>(key: unknown[], path: string, params: Record<string, string> = {}, enabled = true) =>
  useQuery<T>({ queryKey: key, queryFn: () => get<T>(path, params), enabled, staleTime: 5 * 60_000 });

export const useMeta = () => q<Meta>(["meta"], "/meta");
export const useForecast = (date: string, cutoff: string, enabled: boolean) =>
  q<ForecastResponse>(["forecast", date, cutoff], "/forecast", { delivery_date: date, cutoff }, enabled);
export const useDays = (cutoff: string, enabled: boolean) =>
  q<ForecastDay[]>(["days", cutoff], "/forecast/days", { cutoff }, enabled);
export const useSummary = (cutoff: string, enabled: boolean) =>
  q<Summary>(["summary", cutoff], "/accuracy/summary", { cutoff }, enabled);
export const useByDay = (cutoff: string, enabled: boolean) =>
  q<DayRow[]>(["by-day", cutoff], "/accuracy/by-day", { cutoff }, enabled);
export const useByHour = (cutoff: string, enabled: boolean) =>
  q<HourRow[]>(["by-hour", cutoff], "/accuracy/by-hour", { cutoff }, enabled);
export const useByHorizon = () => q<HorizonRow[]>(["by-horizon"], "/accuracy/by-horizon");
export const useDistribution = (cutoff: string, enabled: boolean) =>
  q<Distribution>(["dist", cutoff], "/accuracy/distribution", { cutoff }, enabled);
