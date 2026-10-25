import { Card } from "../components/Kpi";
import { useMeta } from "../api";

export default function Method() {
  const { data } = useMeta();
  const q = data?.data_quality;
  return (
    <>
      <h1>How the numbers are made</h1>
      <Card title="Which forecast counts as the latest">
        <p>
          For each half-hour of the delivery day D, we take the forecast with the most recent publish time that is at or before the cutoff on
          D-1 (default 09:00 UK time, adjustable at the top). Forecasts published later are never used. If none exists, the half-hour stays
          empty instead of being filled in.
        </p>
      </Card>
      <Card title="How accuracy is measured">
        <ul>
          <li>Error = forecast minus actual, in MW. Positive means less wind than forecast, so a buyer could be short.</li>
          <li>Average miss (MAE) is the mean size of the error. Bias is the mean signed error. RMSE weights big misses more.</li>
          <li>Error as share of output (nMAE) is MAE divided by mean actual output. We avoid percentage error per half-hour because it breaks when output is low.</li>
          <li>Shortfall buffer is the 90th percentile of the error, never below zero. It is the extra volume to cover in 9 of 10 half-hours when wind under-delivers.</li>
          <li>The 80% range around a forecast is forecast minus the 90th and 10th error percentiles. It is measured on the same window, so it is a description of the past, not a promise.</li>
          <li>The horizon chart uses every published forecast, to show how accuracy improves nearer the target time.</li>
        </ul>
      </Card>
      <Card title="Data and limits">
        <ul>
          <li>Source: Elexon BMRS only. FUELHH (wind) for actuals, WINDFOR for forecasts. National level, Great Britain.</li>
          <li>
            Forecasts are published hourly in the source{q ? ` (${q.forecasts.resolution_minutes}-minute steps)` : ""}, actuals every half-hour. Each hourly
            forecast is applied to both half-hours inside that hour.
          </li>
          {q && (
            <li>
              {q.forecasts.publish_count} forecast publishes loaded, median gap {q.forecasts.publish_gap_hours.median ?? "n/a"} h.{" "}
              {q.actuals.missing_count} of {q.actuals.expected_half_hours} half-hours have no actual.
            </li>
          )}
          <li>Times shown in UK local time. Clock-change days have 46 or 50 half-hours.</li>
          <li>Wind output only. No prices, demand or outages are used.</li>
        </ul>
      </Card>
    </>
  );
}
