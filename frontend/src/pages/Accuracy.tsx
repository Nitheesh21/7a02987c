import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useByDay, useByHorizon, useByHour, useDistribution, useSummary } from "../api";
import { Card, Kpi, Status } from "../components/Kpi";
import { biasMeaning, mw, pct, shortDate, signedMw } from "../format";
import { useCutoff } from "../useCutoff";

const tick = { fill: "var(--muted)", fontSize: 12 };
const tip = { background: "var(--panel)", border: "1px solid var(--line)" };
const round = (v: unknown) => `${Math.round(Number(v)).toLocaleString("en-GB")} MW`;

export default function Accuracy() {
  const { cutoff, ready } = useCutoff();
  const sum = useSummary(cutoff, ready);
  const byDay = useByDay(cutoff, ready);
  const byHour = useByHour(cutoff, ready);
  const byHorizon = useByHorizon();
  const dist = useDistribution(cutoff, ready);
  const m = sum.data?.metrics;

  const hist = dist.data
    ? dist.data.histogram.counts.map((c, i) => {
        const lo = dist.data!.histogram.edges[i];
        const hi = dist.data!.histogram.edges[i + 1];
        return { label: Math.round((lo + hi) / 2), count: c, mid: (lo + hi) / 2 };
      })
    : [];

  return (
    <>
      <h1>How accurate has the forecast been?</h1>
      <p className="lead">
        Each half-hour is judged using the forecast that was available at the cutoff on the day before. Error is forecast minus actual, so a
        positive error means less wind arrived than predicted.
      </p>
      <Status loading={sum.isLoading} error={sum.error} />
      {m && (
        <div className="kpis">
          <Kpi label="Average miss (MAE)" value={mw(m.mae)} note="Typical size of the error" />
          <Kpi label="Bias" value={signedMw(m.bias)} note={biasMeaning(m.bias)} />
          <Kpi label="RMSE" value={mw(m.rmse)} note="Punishes large misses more" />
          <Kpi label="Error as share of output" value={pct(m.nmae)} note="MAE divided by mean actual (nMAE)" />
          <Kpi label="9 in 10 within" value={mw(m.p90_abs_error)} note="90th percentile of absolute error" />
          <Kpi label="Shortfall buffer" value={mw(m.p90_shortfall_buffer_mw)} note="Cover for 9 in 10 under-deliveries" />
          <Kpi label="Half-hours compared" value={m.count.toLocaleString("en-GB")} note={`${pct(sum.data!.coverage, 1)} of the window`} />
          <Kpi label="80% band check" value={pct(sum.data!.band_coverage, 0)} note="Share of actuals inside the 80% range (in-sample)" />
        </div>
      )}

      <div className="grid2">
        <Card title="Error by delivery day" caption="Bars: average miss. Line: bias (above zero means forecast ran high).">
          <Status loading={byDay.isLoading} error={byDay.error} />
          <div className="chart" role="img" aria-label="Error by delivery day">
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={byDay.data ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" tick={tick} tickFormatter={(d: string) => d.slice(8)} />
                <YAxis tick={tick} width={52} />
                <Tooltip formatter={round} labelFormatter={(d: string) => shortDate(d)} contentStyle={tip} />
                <Legend />
                <ReferenceLine y={0} stroke="var(--line)" />
                <Bar dataKey="mae" name="Average miss" fill="var(--c-forecast)" isAnimationActive={false} />
                <Line dataKey="bias" name="Bias" stroke="var(--c-actual)" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Error by time of day" caption="UK local hour of the delivery half-hour.">
          <Status loading={byHour.isLoading} error={byHour.error} />
          <div className="chart" role="img" aria-label="Error by hour of day">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={byHour.data ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="hour" tick={tick} />
                <YAxis tick={tick} width={52} />
                <Tooltip formatter={round} labelFormatter={(h) => `${h}:00`} contentStyle={tip} />
                <Bar dataKey="mae" name="Average miss" fill="var(--c-forecast)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Does a fresher forecast help?"
          caption="Average miss by how long before the half-hour the forecast was published. Uses every published forecast, not only the one at the cutoff."
        >
          <Status loading={byHorizon.isLoading} error={byHorizon.error} />
          <div className="chart" role="img" aria-label="Error by forecast horizon">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={byHorizon.data ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="bucket" tick={tick} />
                <YAxis tick={tick} width={52} />
                <Tooltip formatter={round} contentStyle={tip} />
                <Bar dataKey="mae" name="Average miss" fill="var(--c-forecast)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="How big are the misses?" caption="Count of half-hours by error size. Right of zero: forecast too high.">
          <Status loading={dist.isLoading} error={dist.error} />
          <div className="chart" role="img" aria-label="Histogram of forecast errors">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={hist} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={1}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="label" tick={tick} />
                <YAxis tick={tick} width={44} />
                <Tooltip formatter={(v: unknown) => `${v} half-hours`} labelFormatter={(l) => `Error near ${l} MW`} contentStyle={tip} />
                <Bar dataKey="count" name="Half-hours" isAnimationActive={false}>
                  {hist.map((h, i) => (
                    <Cell key={i} fill={h.mid > 0 ? "var(--c-actual)" : "var(--c-forecast)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="Accuracy by forecast level" caption="Half-hours split into four equal groups by forecast size. Does the forecast miss more when it predicts a lot of wind?">
        {dist.data && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Group</th><th>Forecast range</th><th className="num">Average miss</th><th className="num">Bias</th><th className="num">Half-hours</th></tr>
              </thead>
              <tbody>
                {dist.data.by_level.map((r) => (
                  <tr key={r.quartile}>
                    <td>{["Lowest", "Lower-mid", "Upper-mid", "Highest"][r.quartile - 1]}</td>
                    <td>{mw(r.forecast_min_mw)} to {mw(r.forecast_max_mw)}</td>
                    <td className="num">{mw(r.mae)}</td>
                    <td className="num">{signedMw(r.bias)}</td>
                    <td className="num">{r.count}</td>
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
