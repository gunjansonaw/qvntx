import { fmtCalendarDay, fmtDateTime, fmtInt } from '../lib/format.js'

/** How the numbers are produced - written for traders, precise enough for analysts. */
export default function MethodologyView({ meta }) {
  const d = meta?.dataset
  return (
    <div className="view prose">
      <section className="card">
        <h2>The decision we model</h2>
        <p>
          The desk buys power in the GB day-ahead auctions on the day before delivery (D-1). Purchase decisions made in{' '}
          <strong>January 2026</strong> cover delivery days{' '}
          <strong>
            {meta ? `${fmtCalendarDay(meta.deliveryDays.firstDay)} – ${fmtCalendarDay(meta.deliveryDays.lastDay)} 2026` : '2 Jan – 1 Feb 2026'}
          </strong>
          . For every half-hourly settlement period we compare the wind forecast the desk could actually see at its decision
          time with the wind that was then generated.
        </p>
        <ul>
          <li>
            <strong>Auction gates.</strong> EPEX SPOT's GB day-ahead auction closes at 09:20 UK time and Nord Pool's N2EX
            GB day-ahead auction at 09:50. NESO publishes a forecast run at 09:30, so the choice of exchange changes which
            forecast you trade on.
          </li>
          <li>
            <strong>Custom gate / fixed lead.</strong> Any decision time on D-1, or "the latest forecast at least N hours
            before each period", can be evaluated the same way.
          </li>
        </ul>
      </section>

      <section className="card">
        <h2>Data</h2>
        <ul>
          <li>
            <strong>Actual generation — Elexon BMRS FUELHH</strong>, fuel type WIND: half-hourly metered output of
            transmission-connected wind farms (MW, averaged over the settlement period).
          </li>
          <li>
            <strong>Forecast — Elexon BMRS WINDFOR</strong>: NESO's national wind generation forecast, hourly resolution,
            published eight times a day (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UK in winter). Each run looks
            roughly 2–3 days ahead.
          </li>
          {d && (
            <li>
              Loaded <strong>{fmtInt(d.actualPeriods)}</strong> settlement periods and <strong>{fmtInt(d.forecastRuns)}</strong>{' '}
              forecast runs ({fmtInt(d.forecastPoints)} hourly values) · source: <strong>{d.source}</strong> · retrieved{' '}
              {fmtDateTime(d.retrievedAt)} UK.
            </li>
          )}
        </ul>
      </section>

      <section className="card">
        <h2>Which forecast counts</h2>
        <ol>
          <li>For each settlement period, find the decision cut-off (for example 09:20 UK on D-1).</li>
          <li>
            Take the <strong>latest forecast run published at or before the cut-off</strong>. Later runs are invisible — no
            look-ahead bias.
          </li>
          <li>Rows a run publishes for times before its own publish time are hindcasts, not forecasts, and are dropped.</li>
          <li>
            WINDFOR is hourly while settlement is half-hourly: HH:30 values are linearly interpolated between the two
            surrounding hours <em>of the same run</em>.
          </li>
          <li>All delivery days are UK settlement days, so clock-change days correctly have 46 or 50 periods.</li>
        </ol>
      </section>

      <section className="card">
        <h2>Metrics</h2>
        <p>
          Error is <strong>forecast − actual</strong>. Positive means the forecast over-stated wind, so the desk is short and
          must procure the gap.
        </p>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Definition</th>
              <th scope="col">Why it matters</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>MAE</td><td>mean |error|</td><td>Typical size of a miss, in MW</td></tr>
            <tr><td>RMSE</td><td>√ mean error²</td><td>Weights large misses more heavily</td></tr>
            <tr><td>Bias</td><td>mean error</td><td>Systematic over- or under-forecasting</td></tr>
            <tr><td>WAPE</td><td>Σ|error| ÷ Σ actual</td><td>Percentage error that stays stable at low output</td></tr>
            <tr><td>MAPE</td><td>mean(|error| ÷ actual)</td><td>Familiar, but inflated when output is low</td></tr>
            <tr><td>P90 miss</td><td>90th percentile of |error|</td><td>A "bad but normal" miss</td></tr>
            <tr><td>Shortfall energy</td><td>Σ max(error, 0) × 0.5 h</td><td>MWh wind failed to deliver vs plan</td></tr>
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Uncertainty band</h2>
        <p>
          The P10–P90 band applies the empirical error quantiles of the selected window to each forecast. Because errors
          grow with wind level, quantiles are computed separately for each 3 GW band of forecast output and interpolated
          between neighbouring bands, so the range widens smoothly as the forecast rises (bands with fewer than 50
          periods are not used). P50 is a bias-adjusted central estimate.
        </p>
      </section>

      <section className="card">
        <h2>Procurement plan</h2>
        <p>
          The desk's question is how much power to buy beyond what wind will provide. For each half-hour:{' '}
          <strong>power to buy = demand − firm wind</strong>.
        </p>
        <ul>
          <li>
            <strong>Firm wind</strong> at a chosen confidence (80 / 90 / 95%) is the forecast minus the forecast-error
            quantile at that confidence for the same forecast level. Actual wind met or beat it in that share of periods.
          </li>
          <li>
            <strong>Extra cover</strong> = forecast − firm wind: volume to secure from other sources on top of planning
            against the raw forecast. <strong>Peak extra capacity</strong> is the largest half-hourly gap.
          </li>
          <li>
            <strong>Plan held</strong> back-tests the plan: the share of periods in which actual wind was at least the firm
            volume.
          </li>
          <li>
            Demand is not part of this pilot's data (the brief limits it to Elexon wind), so the desk applies its own demand
            forecast to get the total purchase volume.
          </li>
        </ul>
      </section>

      <section className="card">
        <h2>Caveats</h2>
        <ul>
          <li>
            The band and guidance are calibrated on the same month they describe (in-sample). A production version should
            calibrate on a rolling window of past days only.
          </li>
          <li>
            Both datasets cover transmission-connected wind. Embedded (distribution-connected) wind is not metered here and
            shows up as lower demand instead.
          </li>
          <li>
            The persistent over-forecast at high wind is consistent with wind output being curtailed for network constraints,
            which the forecast of available output may not net off. Worth confirming with NESO before acting on it.
          </li>
        </ul>
      </section>
    </div>
  )
}
