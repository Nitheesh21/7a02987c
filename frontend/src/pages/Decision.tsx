import { useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useSearchParams } from "react-router-dom";
import { useDays, useForecast } from "../api";
import { Card, Kpi, Status } from "../components/Kpi";
import { hours, mw, mwh, pct, shortDate } from "../format";
import { useCutoff } from "../useCutoff";

export default function Decision() {
  const { cutoff, meta, ready } = useCutoff();
  const [params, setParams] = useSearchParams();
  const start = meta.data?.delivery_start ?? "";
  const end = meta.data?.delivery_end ?? "";
  const date = params.get("date") ?? start;
  const forecast = useForecast(date, cutoff, ready && Boolean(date));
  const days = useDays(cutoff, ready);

  const pick = (d: string) => {
    const next = new URLSearchParams(params);
    next.set("date", d);
    setParams(next, { replace: true });
  };
  const shift = (n: number) => {
    const d = new Date(`${date}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    const iso = d.toISOString().slice(0, 10);
    if (iso >= start && iso <= end) pick(iso);
  };

  const data = useMemo(
    () =>
      (forecast.data?.points ?? []).map((p) => ({
        t: p.uk_time,
        forecast: p.forecast_mw,
        actual: p.actual_mw,
        band: p.band_low_mw != null && p.band_high_mw != null ? [p.band_low_mw, p.band_high_mw] : null,
      })),
    [forecast.data],
  );
  const s = forecast.data?.summary;

  return (
    <>
      <h1>Wind generation forecast for delivery day</h1>
      <div className="picker">
        <button onClick={() => shift(-1)} disabled={!date || date <= start} aria-label="Previous day">Prev</button>
        <input type="date" value={date} min={start} max={end} onChange={(e) => e.target.value && pick(e.target.value)} aria-label="Delivery date" />
        <button onClick={() => shift(1)} disabled={!date || date >= end} aria-label="Next day">Next</button>
        {forecast.data && (
          <span className="muted">
            Using forecasts published up to <strong>{forecast.data.cutoff_uk}</strong>
          </span>
        )}
      </div>
      <Status loading={forecast.isLoading || meta.isLoading} error={forecast.error} />

      {s && (
        <>
          <div className="kpis">
            <Kpi label="Expected wind energy" value={mwh(s.energy_mwh)} note="Sum over the day" />
            <Kpi label="Average output" value={mw(s.avg_mw)} note={`Low ${mw(s.min_mw)}, peak ${mw(s.peak_mw)}`} />
            <Kpi
              label="Suggested shortfall buffer"
              value={mw(s.p90_shortfall_buffer_mw)}
              note="In 9 of 10 half-hours, actual wind was no more than this far below the forecast"
            />
            <Kpi label="Forecast age" value={hours(s.avg_horizon_h)} note="Average time from publish to the half-hour" />
            <Kpi label="Forecast coverage" value={pct(s.coverage, 0)} note="Half-hours that have a forecast by the cutoff" />
          </div>
          <Card
            title="Half-hourly forecast"
            caption="Solid line is the latest forecast available at the cutoff. The shaded band is the range that actual output fell in for 80% of past half-hours. The dashed line is what actually happened, shown only for comparison. It was not known at decision time."
          >
            <div className="chart" role="img" aria-label="Line chart of forecast and actual wind generation by half-hour">
              <ResponsiveContainer width="100%" height={340}>
                <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="t" interval={5} tick={{ fill: "var(--muted)", fontSize: 12 }} />
                  <YAxis tick={{ fill: "var(--muted)", fontSize: 12 }} width={56} tickFormatter={(v: number) => `${v / 1000}k`} unit="" />
                  <Tooltip formatter={(v: unknown) => (Array.isArray(v) ? `${Math.round(v[0])} to ${Math.round(v[1])} MW` : `${Math.round(Number(v))} MW`)} contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)" }} />
                  <Legend />
                  <Area dataKey="band" name="80% range" stroke="none" fill="var(--c-band)" fillOpacity={0.35} connectNulls={false} isAnimationActive={false} />
                  <Line dataKey="forecast" name="Forecast (MW)" stroke="var(--c-forecast)" strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
                  <Line dataKey="actual" name="Actual (MW)" stroke="var(--c-actual)" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}

      <Card title="All delivery days" caption="Select a row to see that day. Day error is the mean absolute error of that day's forecast.">
        <Status loading={days.isLoading} error={days.error} />
        {days.data && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Day</th><th className="num">Energy</th><th className="num">Average</th><th className="num">Peak</th><th className="num">Coverage</th><th className="num">Day error (MAE)</th>
                </tr>
              </thead>
              <tbody>
                {days.data.map((d) => (
                  <tr key={d.delivery_date} className={d.delivery_date === date ? "sel" : ""}>
                    <td><button className="link" onClick={() => pick(d.delivery_date)}>{shortDate(d.delivery_date)}</button></td>
                    <td className="num">{mwh(d.energy_mwh)}</td>
                    <td className="num">{mw(d.avg_mw)}</td>
                    <td className="num">{mw(d.peak_mw)}</td>
                    <td className="num">{pct(d.coverage, 0)}</td>
                    <td className="num">{mw(d.day_mae)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
