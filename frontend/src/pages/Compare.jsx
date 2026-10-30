import { useState } from 'react'
import { useApi } from '../api'
import Plot from '../components/Plot'
import { Badge, Card, CityLink, PageHeader, Status, tierTone } from '../components/ui'
import { COMPONENTS, COMPONENT_COLORS, COMPONENT_LABELS, fmt, pct } from '../utils'

const ROWS = [
  ['Investment score', (r) => fmt(r.score, 1)],
  ['Rank', (r) => (r.rank ? `#${r.rank}` : '—')],
  ['NHB price (₹/sqft)', (r) => fmt(r.metrics.nhb_price)],
  ['Listing median (₹/sqft)', (r) => fmt(r.metrics.median_price_psf)],
  ['NHB momentum (annualised)', (r) => pct(r.metrics.nhb_momentum_pct)],
  ['RBI HPI YoY', (r) => pct(r.metrics.hpi_yoy_pct)],
  ['HPI volatility (QoQ std)', (r) => pct(r.metrics.hpi_volatility)],
  ['Rental yield', (r) => pct(r.metrics.gross_yield_pct)],
  ['Catalyst score', (r) => `${fmt(r.metrics.catalyst_score)}/10`],
]

export default function Compare() {
  const all = useApi('/cities')
  const [picked, setPicked] = useState(['Pune', 'Nagpur', 'Noida'])
  const valid = picked.length >= 2
  const cmp = useApi(valid ? '/compare' : null, { cities: picked.join(',') })

  const toggle = (c) =>
    setPicked((p) => (p.includes(c) ? p.filter((x) => x !== c) : p.length < 6 ? [...p, c] : p))

  return (
    <div className="stack">
      <PageHeader title="Compare cities" subtitle="Side-by-side metrics, score breakdown and price index." />
      <Card title="Choose cities" subtitle="Pick 2 to 6">
        <Status loading={all.loading} error={all.error}>
          <div className="chips">
            {all.data?.cities.map((c) => (
              <button key={c.city} className={picked.includes(c.city) ? 'chip on' : 'chip'} onClick={() => toggle(c.city)}>
                {c.city}
              </button>
            ))}
          </div>
        </Status>
      </Card>

      {!valid && <div className="status">Select at least two cities.</div>}
      {valid && (
        <Status loading={cmp.loading && !cmp.data} error={cmp.error}>
          {cmp.data && (
            <>
              <Card title="Side by side">
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th />
                        {cmp.data.cities.map((r) => (
                          <th key={r.city}><CityLink city={r.city} /> <Badge tone={tierTone(r.tier_type)}>{r.tier_type}</Badge></th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ROWS.map(([label, f]) => (
                        <tr key={label}><td>{label}</td>{cmp.data.cities.map((r) => <td key={r.city}>{f(r)}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card title="Score breakdown" subtitle="0–100 per factor (blank = no data for that city)">
                <Plot
                  data={COMPONENTS.map((c) => ({
                    type: 'bar', name: COMPONENT_LABELS[c], marker: { color: COMPONENT_COLORS[c] },
                    x: cmp.data.cities.map((r) => r.city),
                    y: cmp.data.cities.map((r) => r.component_scores[c]),
                  }))}
                  layout={{ barmode: 'group', yaxis: { title: 'Score (0–100)', range: [0, 105] } }}
                />
              </Card>

              <Card title="Price index since 2022-23" subtitle="RBI HPI rebased to 100 at the first common quarter">
                {Object.keys(cmp.data.hpi_rebased_100).length ? (
                  <Plot
                    data={Object.entries(cmp.data.hpi_rebased_100).map(([city, pts]) => ({
                      type: 'scatter', mode: 'lines+markers', name: city,
                      x: pts.map((p) => p.quarter_end), y: pts.map((p) => p.value),
                    }))}
                    layout={{ yaxis: { title: 'Rebased index' } }}
                  />
                ) : <p className="muted">None of the selected cities are in the RBI HPI.</p>}
                {cmp.data.no_hpi_for.length > 0 && <p className="note">No RBI HPI for: {cmp.data.no_hpi_for.join(', ')}</p>}
              </Card>
            </>
          )}
        </Status>
      )}
    </div>
  )
}
