import { useApi } from '../api'
import { Card, PageHeader, Status } from '../components/ui'
import { COMPONENTS, COMPONENT_LABELS, fmt } from '../utils'

export default function Methodology() {
  const m = useApi('/methodology')
  const info = useApi('/model-info')
  return (
    <div className="stack">
      <PageHeader title="Methodology" subtitle="How every number is produced, and what it cannot tell you." />
      <Card title="How the investment score works">
        <Status loading={m.loading} error={m.error}>
          {m.data && (
            <>
              <p>{m.data.scoring}</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Factor</th><th>What it measures</th>{Object.keys(m.data.profiles).map((p) => <th key={p}>{p}</th>)}</tr></thead>
                  <tbody>
                    {COMPONENTS.map((c) => (
                      <tr key={c}>
                        <td>{COMPONENT_LABELS[c]}</td><td>{m.data.components[c]}</td>
                        {Object.values(m.data.profiles).map((p, i) => <td key={i}>{Math.round(p[c] * 100)}%</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Status>
      </Card>

      <Card title="Locality score">
        <p>Listing data is a one-time snapshot, so there is <b>no locality-level price growth</b>. A locality's score is half the score of its city
          (which carries growth, catalysts and stability) and half how attractive it is compared with its own neighbours:
          affordability 40%, rental yield relative to the city 40% (only with 10+ rent listings), and market depth 20% (number of listings).
          Each local part is a percentile rank inside the city. Localities with fewer than 20 listings are hidden by default.</p>
      </Card>

      <Card title="Rent vs buy">
        <p>A month-by-month simulation. The buyer pays the down payment and buying costs, then EMI and upkeep; their net worth is the sale value after
          selling costs minus the loan left. The renter invests the same up-front cash and every month invests the difference between the buyer's
          outflow and their rent. Break-even is the first year after which the buyer stays ahead. Taxes (home-loan deductions, capital gains) are ignored,
          and the result is very sensitive to the price-growth and investment-return assumptions, which is why the page shows a sensitivity table.</p>
      </Card>

      <Card title="Fair-price model">
        <Status loading={info.loading} error={info.error}>
          {info.data && (
            <>
              <p>Gradient boosting on city, locality (target-encoded), area and BHK, trained on {fmt(info.data.listings)} listings. Validation: {info.data.validation}.</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th /><th>Median error</th><th>Mean error</th><th>R² (log price)</th></tr></thead>
                  <tbody>
                    <tr><td>Model</td><td>{info.data.model.median_ape_pct}%</td><td>{info.data.model.mape_pct}%</td><td>{info.data.model.r2_log_price}</td></tr>
                    <tr><td>Baseline: locality average</td><td>{info.data.baseline_locality_mean.median_ape_pct}%</td><td>{info.data.baseline_locality_mean.mape_pct}%</td><td>{info.data.baseline_locality_mean.r2_log_price}</td></tr>
                  </tbody>
                </table>
              </div>
              <ul>{info.data.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
            </>
          )}
        </Status>
      </Card>

      <Card title="Limitations">
        <Status loading={m.loading} error={m.error}>
          {m.data && <ul>{m.data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
        </Status>
      </Card>

      <Card title="Data sources">
        <ul>
          <li>RBI House Price Index (quarterly, 18 cities, base 2022-23) from the RBI DBIE portal.</li>
          <li>NHB Residex carpet-area prices (50 cities, 4 quarters).</li>
          <li>Public Kaggle listing datasets for sale and rent (2022 to 2024), cleaned and deduplicated.</li>
          <li>Infrastructure and industry catalysts compiled from public news, with sources listed on each city page.</li>
        </ul>
      </Card>
    </div>
  )
}
