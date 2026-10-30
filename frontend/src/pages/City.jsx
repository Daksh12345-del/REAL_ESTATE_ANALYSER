import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../api'
import Plot, { band } from '../components/Plot'
import { Badge, Card, PageHeader, Stat, Status, Tabs, reliabilityTone, tierTone } from '../components/ui'
import { COMPONENTS, COMPONENT_COLORS, COMPONENT_LABELS, fmt, isNum, lakh, pct } from '../utils'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'trends', label: 'Trends & forecast' },
  { id: 'localities', label: 'Localities' },
  { id: 'catalysts', label: 'Catalysts & risks' },
]

export default function City() {
  const { name } = useParams()
  const [tab, setTab] = useState('overview')
  const city = useApi(`/city/${name}`)

  return (
    <Status loading={city.loading && !city.data} error={city.error}>
      {city.data && (
        <div className="stack-lg">
          <PageHeader
            title={<>{city.data.city} <Badge tone={tierTone(city.data.tier_type)}>{city.data.tier_type}</Badge></>}
            subtitle={city.data.state}
          >
            <div className="score-big">
              {isNum(city.data.score) ? (
                <><div className="score-num">{fmt(city.data.score, 1)}</div><div className="muted small">Investment score · rank #{city.data.rank}</div></>
              ) : <Badge tone="amber">Not ranked: not enough data</Badge>}
            </div>
          </PageHeader>
          <div className="btn-row">
            <Link className="btn" to={`/localities?city=${city.data.city}`}>Explore localities</Link>
            <Link className="btn" to={`/rent-vs-buy?city=${city.data.city}`}>Rent vs buy here</Link>
            <Link className="btn" to={`/compare`}>Compare with other cities</Link>
          </div>
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          {tab === 'overview' && <Overview c={city.data} />}
          {tab === 'trends' && <TrendsTab name={city.data.city} />}
          {tab === 'localities' && <LocalitiesTab name={city.data.city} />}
          {tab === 'catalysts' && <CatalystsTab c={city.data} />}
        </div>
      )}
    </Status>
  )
}

function Overview({ c }) {
  const m = c.metrics
  return (
    <div className="stack">
      <div className="stats">
        <Stat label="Price (NHB, carpet)" value={`₹${fmt(m.nhb_price)}/sqft`} hint={`momentum ${pct(m.nhb_momentum_pct)} a year`} />
        <Stat label="Listing median" value={m.median_price_psf ? `₹${fmt(m.median_price_psf)}/sqft` : '—'} hint={`${fmt(m.sale_rows)} listings`} />
        <Stat label="Rental yield" value={pct(m.gross_yield_pct)} hint={`${fmt(m.rent_rows)} rent listings`} />
        <Stat label="RBI HPI YoY" value={pct(m.hpi_yoy_pct)} hint={m.hpi_latest_quarter || 'not in RBI 18 cities'} />
        <Stat label="Catalyst score" value={`${fmt(m.catalyst_score)}/10`} hint="author's judgement" />
      </div>
      <Card title="Why this score?" subtitle={`Profile: ${c.profile}. Each bar is the city's 0–100 score on that factor.`}>
        <div className="grid two-col-even">
          <Plot
            height={290}
            data={[{
              type: 'bar',
              x: COMPONENTS.map((k) => COMPONENT_LABELS[k]),
              y: COMPONENTS.map((k) => c.component_scores[k] ?? 0),
              marker: { color: COMPONENTS.map((k) => (isNum(c.component_scores[k]) ? COMPONENT_COLORS[k] : '#cbd5e1')) },
              text: COMPONENTS.map((k) => (isNum(c.component_scores[k]) ? fmt(c.component_scores[k], 0) : 'no data')),
              textposition: 'outside', hoverinfo: 'skip',
            }]}
            layout={{ yaxis: { range: [0, 118], title: 'Score (0–100)' }, margin: { l: 55, r: 20, t: 10, b: 40 } }}
          />
          <div className="table-wrap">
            <table>
              <thead><tr><th>Factor</th><th>Score</th><th>Points added</th></tr></thead>
              <tbody>
                {c.explanation.map((e) => (
                  <tr key={e.component}>
                    <td><i className="dot" style={{ background: COMPONENT_COLORS[e.component] }} />{COMPONENT_LABELS[e.component]}</td>
                    <td>{isNum(e.score_0_100) ? fmt(e.score_0_100, 0) : 'no data'}</td>
                    <td>{isNum(e.points_added) ? `+${fmt(e.points_added, 1)}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {c.data_gaps?.length > 0 && <p className="note">Missing data: {c.data_gaps.join('; ')}. Weights of the other factors were scaled up.</p>}
      </Card>
    </div>
  )
}

function TrendsTab({ name }) {
  const trends = useApi('/trends', { city: name })
  const fc = useApi('/forecast', { city: name, quarters: 4, years: 5 })
  return (
    <div className="stack">
      <Trends t={trends} />
      <Forecast fc={fc} />
    </div>
  )
}

function Trends({ t }) {
  return (
    <Card title="Price trends" subtitle="RBI House Price Index (base 2022-23 = 100) and NHB Residex carpet-area price">
      <Status loading={t.loading} error={t.error}>
        {t.data && (
          <div className="grid two-col-even">
            {t.data.has_hpi ? (
              <Plot
                data={[{
                  type: 'scatter', mode: 'lines+markers', name: 'HPI',
                  x: t.data.hpi.map((p) => p.quarter_end), y: t.data.hpi.map((p) => p.hpi),
                  marker: { color: t.data.hpi.map((p) => (p.provisional ? '#f59e0b' : '#2563eb')), size: 7 },
                  line: { color: '#2563eb' }, hovertemplate: '%{x|%b %Y}: %{y:.1f}<extra></extra>',
                }]}
                layout={{ title: { text: 'RBI HPI (orange = provisional)', font: { size: 13 } }, yaxis: { title: 'Index' } }}
              />
            ) : <p className="muted">This city is not among the RBI HPI's 18 cities.</p>}
            {t.data.has_nhb ? (
              <Plot
                data={['small', 'medium', 'large'].map((k, i) => ({
                  type: 'scatter', mode: 'lines+markers', name: k,
                  x: t.data.nhb.map((p) => p.quarter_end), y: t.data.nhb.map((p) => p[k]),
                  line: { color: ['#94a3b8', '#2563eb', '#0f172a'][i] },
                }))}
                layout={{ title: { text: 'NHB price by flat size (₹/sqft, 4 quarters)', font: { size: 13 } }, yaxis: { title: '₹ per sqft' } }}
              />
            ) : <p className="muted">No NHB price data for this city.</p>}
          </div>
        )}
      </Status>
    </Card>
  )
}

function Forecast({ fc }) {
  return (
    <Card title="Forecast and scenarios" subtitle="Model forecasts only where RBI history exists. Everything else is a labelled scenario.">
      <Status loading={fc.loading} error={null}>
        {fc.error && <p className="muted">No price history for this city yet, so there is nothing to forecast. See the catalyst notes.</p>}
        {fc.data && (
          <div className="stack">
            <ModelForecast mf={fc.data.model_forecast} />
            <Scenarios s={fc.data.scenarios} />
          </div>
        )}
      </Status>
    </Card>
  )
}

function ModelForecast({ mf }) {
  if (!mf?.available) return <p className="muted">Model forecast unavailable: {mf?.reason}</p>
  const h = mf.history
  const f = mf.forecast
  const fx = f.map((p) => p.quarter_end)
  const lastX = h[h.length - 1].quarter_end
  const lastY = h[h.length - 1].hpi
  const join = (arr) => [lastY, ...arr]
  return (
    <div className="stack">
      <div className="btn-row">
        <Badge tone={reliabilityTone(mf.reliability)}>reliability: {mf.reliability.replace('_', ' ')}</Badge>
        <Badge tone="gray">model: {mf.model_used}</Badge>
        <Badge tone={mf.beats_no_change_baseline ? 'green' : 'amber'}>
          {mf.beats_no_change_baseline ? 'beats the “no change” baseline' : 'does NOT beat the “no change” baseline'}
        </Badge>
        <b>{pct(mf.forecast_change_pct)}</b> <span className="muted small">over {f.length} quarters</span>
      </div>
      <Plot
        height={360}
        data={[
          band([lastX, ...fx], join(f.map((p) => p.lower_95)), join(f.map((p) => p.upper_95)), 'rgba(37,99,235,0.10)', '95% band'),
          band([lastX, ...fx], join(f.map((p) => p.lower_80)), join(f.map((p) => p.upper_80)), 'rgba(37,99,235,0.22)', '80% band'),
          { type: 'scatter', mode: 'lines+markers', name: 'History', x: h.map((p) => p.quarter_end), y: h.map((p) => p.hpi), line: { color: '#0f172a' } },
          { type: 'scatter', mode: 'lines+markers', name: 'Forecast', x: [lastX, ...fx], y: join(f.map((p) => p.forecast)), line: { color: '#2563eb', dash: 'dash' } },
          ...(mf.provisional_actual?.length ? [{
            type: 'scatter', mode: 'markers', name: 'RBI provisional actual',
            x: mf.provisional_actual.map((p) => p.quarter_end), y: mf.provisional_actual.map((p) => p.hpi),
            marker: { color: '#f59e0b', size: 11, symbol: 'diamond' },
          }] : []),
        ]}
        layout={{ yaxis: { title: 'HPI (2022-23 = 100)' } }}
      />
      <p className="note">{mf.interval_note}{mf.capped_to_25pct_per_year ? ' The forecast was capped at ±25% a year.' : ''}</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Model (backtest)</th><th>Error (index pts)</th><th>Error %</th><th>What it does</th></tr></thead>
          <tbody>
            {mf.model_comparison.map((m) => (
              <tr key={m.model} className={m.model === mf.model_used ? 'hl' : ''}>
                <td>{m.model}{m.model === mf.model_used && ' ✓'}</td>
                <td>{fmt(m.mae_index_points, 2)}</td><td>{fmt(m.mape_pct, 2)}</td><td>{m.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Scenarios({ s }) {
  if (!s || s.available === false) return <p className="muted">Scenarios unavailable: {s?.reason}</p>
  const a = s.assumptions
  const line = (k, color) => ({
    type: 'scatter', mode: 'lines+markers', name: `${k} (${pct(a[`${k}_growth_pct`])} a year)`,
    x: s.scenarios[k].map((p) => p.year), y: s.scenarios[k].map((p) => p.price_per_sqft), line: { color },
  })
  return (
    <div className="stack">
      <h4>Price scenarios (₹ per sqft, from {s.starting_quarter})</h4>
      <Plot height={300} data={[line('bear', '#dc2626'), line('base', '#2563eb'), line('bull', '#16a34a')]}
        layout={{ xaxis: { title: 'Years from now', dtick: 1 }, yaxis: { title: '₹ per sqft' } }} />
      <p className="note">{s.disclaimer}</p>
    </div>
  )
}

function LocalitiesTab({ name }) {
  const locs = useApi('/locality-scores', { city: name, limit: 12 })
  return (
    <Card title="Top localities" subtitle="Ranked by locality investment score" right={<Link className="btn" to={`/localities?city=${name}`}>Open full explorer</Link>}>
      <Status loading={locs.loading} error={null}>
        {locs.error && <p className="muted">No locality-level listing data for this city, only city-level figures.</p>}
        {locs.data && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>#</th><th>Locality</th><th>Score</th><th>Listings</th><th>₹/sqft</th><th>vs city</th><th>Median price</th></tr></thead>
              <tbody>
                {locs.data.localities.map((l) => (
                  <tr key={l.locality}>
                    <td>{l.rank}</td><td>{l.locality}</td><td><b>{fmt(l.score, 1)}</b></td><td>{fmt(l.listings)}</td>
                    <td>{fmt(l.median_price_psf)}</td>
                    <td className={l.price_vs_city_pct < 0 ? 'pos' : 'neg'}>{pct(l.price_vs_city_pct, 0)}</td>
                    <td>{lakh(l.median_price_lakh)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Status>
    </Card>
  )
}

function CatalystsTab({ c }) {
  return (
    <Card title="Catalysts and risks" right={<span className="muted small">checked {c.catalysts.last_checked}</span>}>
      <div className="grid two-col-even">
        <div><h4>What could drive prices up</h4><p>{c.catalysts.summary}</p></div>
        <div><h4>Risks and setbacks</h4><p>{c.catalysts.risks}</p></div>
      </div>
      <p className="small">Sources: {c.catalysts.sources.map((s, i) => (
        <span key={s}><a href={s} target="_blank" rel="noreferrer">[{i + 1}]</a>{' '}</span>
      ))}</p>
      <p className="note">The catalyst score ({fmt(c.metrics.catalyst_score)}/10) is the author's judgement based on these sources, not an official rating.</p>
    </Card>
  )
}
