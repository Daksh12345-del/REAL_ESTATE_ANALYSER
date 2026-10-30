import { useMemo, useState } from 'react'
import { useApi, useDebounced } from '../api'
import Plot from '../components/Plot'
import { Badge, Card, CityLink, PageHeader, Status, tierTone } from '../components/ui'
import { COMPONENTS, COMPONENT_COLORS, COMPONENT_LABELS, PROFILES, fmt, pct } from '../utils'

export default function Rankings() {
  const [mode, setMode] = useState('balanced') // a profile name or 'custom'
  const [weights, setWeights] = useState(PROFILES.balanced)
  const [tier, setTier] = useState('')

  const params = useMemo(() => {
    const p = { top: 20, tier }
    if (mode === 'custom') COMPONENTS.forEach((c) => (p[`w_${c}`] = weights[c]))
    else p.profile = mode
    return p
  }, [mode, weights, tier])
  const debounced = useDebounced(params)
  const { data, error, loading } = useApi('/opportunities', debounced)

  const pickProfile = (name) => {
    setMode(name)
    setWeights(PROFILES[name])
  }
  const setWeight = (c, v) => {
    setMode('custom')
    setWeights((w) => ({ ...w, [c]: Number(v) }))
  }

  const results = data?.results ?? []
  const sumW = COMPONENTS.reduce((s, c) => s + weights[c], 0)

  return (
    <div className="stack-lg">
      <PageHeader title="City rankings" subtitle="Investment score for every city. Change the investor profile or drag the weights and the ranking updates live." />
    <div className="grid two-col">
      <aside>
        <Card title="Investor profile" subtitle="Pick a preset or drag the sliders">
          <div className="btn-row">
            {Object.keys(PROFILES).map((p) => (
              <button key={p} className={mode === p ? 'btn active' : 'btn'} onClick={() => pickProfile(p)}>
                {p}
              </button>
            ))}
          </div>
          {COMPONENTS.map((c) => (
            <label key={c} className="slider">
              <span>
                <i className="dot" style={{ background: COMPONENT_COLORS[c] }} />
                {COMPONENT_LABELS[c]}
              </span>
              <input type="range" min="0" max="100" value={weights[c]} onChange={(e) => setWeight(c, e.target.value)} />
              <b>{sumW ? Math.round((weights[c] / sumW) * 100) : 0}%</b>
            </label>
          ))}
          <p className="muted small">Weights are normalised to 100%. Missing data for a city is handled by re-weighting the rest.</p>
          <div className="field">
            <span>City type</span>
            <select value={tier} onChange={(e) => setTier(e.target.value)}>
              <option value="">All cities</option>
              <option value="metro">Metros</option>
              <option value="emerging">Emerging</option>
            </select>
          </div>
        </Card>
      </aside>

      <main>
        <Status loading={loading && !data} error={error}>
          <Card title="Investment score ranking" subtitle="Bars show how many points each factor contributes">
            <Plot
              height={Math.max(300, results.length * 34 + 90)}
              data={COMPONENTS.map((c) => ({
                type: 'bar',
                orientation: 'h',
                name: COMPONENT_LABELS[c],
                y: results.map((r) => r.city),
                x: results.map((r) => r.contributions?.[c] ?? 0),
                marker: { color: COMPONENT_COLORS[c] },
                hovertemplate: `%{y}: %{x:.1f} pts from ${COMPONENT_LABELS[c]}<extra></extra>`,
              }))}
              layout={{
                barmode: 'stack',
                yaxis: { autorange: 'reversed' },
                xaxis: { title: 'Investment score (0–100)', range: [0, 100] },
                margin: { l: 90, r: 20, t: 10, b: 60 },
              }}
            />
            {data?.not_scored?.length > 0 && (
              <p className="note">
                Not ranked (too little data): <b>{data.not_scored.join(', ')}</b>. {data.note}
              </p>
            )}
          </Card>

          <Card title="Risk vs return" subtitle="Growth score (y) against price stability (x). Top-right = growing steadily.">
            <Plot
              height={380}
              data={['metro', 'emerging'].map((t) => {
                const rows = results.filter((r) => r.tier_type === t)
                return {
                  type: 'scatter',
                  mode: 'markers+text',
                  name: t,
                  x: rows.map((r) => r.component_scores.stability),
                  y: rows.map((r) => r.component_scores.growth),
                  text: rows.map((r) => r.city),
                  textposition: 'top center',
                  marker: { size: rows.map((r) => 10 + (r.score ?? 0) / 4), color: t === 'metro' ? '#2563eb' : '#9333ea', opacity: 0.8 },
                }
              })}
              layout={{
                xaxis: { title: 'Stability score (higher = calmer prices)', range: [-8, 108] },
                yaxis: { title: 'Growth score', range: [-8, 122] },
                margin: { l: 55, r: 20, t: 40, b: 50 },
              }}
            />
            <p className="muted small">Marker size = total score. Cities without RBI HPI have no stability score and are not shown.</p>
          </Card>

          <Card title="Ranked table">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th><th>City</th><th>Type</th><th>Score</th><th>Rental yield</th>
                    <th>NHB ₹/sqft</th><th>HPI YoY</th><th>Catalyst</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.city}>
                      <td>{r.rank}</td>
                      <td><CityLink city={r.city} /></td>
                      <td><Badge tone={tierTone(r.tier_type)}>{r.tier_type}</Badge></td>
                      <td><b>{fmt(r.score, 1)}</b></td>
                      <td>{pct(r.metrics.gross_yield_pct)}</td>
                      <td>{fmt(r.metrics.nhb_price)}</td>
                      <td>{pct(r.metrics.hpi_yoy_pct)}</td>
                      <td>{fmt(r.metrics.catalyst_score)}/10</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </Status>
      </main>
    </div>
    </div>
  )
}
