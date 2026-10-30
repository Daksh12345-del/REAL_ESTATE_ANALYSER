import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi } from '../api'
import Plot from '../components/Plot'
import { Card, PageHeader, Status, Tabs } from '../components/ui'
import { fmt, isNum, lakh, pct } from '../utils'

const SORTS = [
  ['score', 'Investment score'], ['cheapest', 'Cheapest first'], ['price', 'Most expensive first'],
  ['yield', 'Best rental yield'], ['listings', 'Most listings'],
]
const COLORS = ['#2563eb', '#16a34a', '#f59e0b', '#9333ea', '#dc2626']
const key = (i) => `${i.city}|${i.locality}`

export default function Localities() {
  const [params] = useSearchParams()
  const [city, setCity] = useState(params.get('city') || 'Pune')
  const [profile, setProfile] = useState('balanced')
  const [minListings, setMinListings] = useState(20)
  const [sort, setSort] = useState('score')
  const [tab, setTab] = useState('ranking')
  const [basket, setBasket] = useState([])

  const cities = useApi('/cities')
  const withListings = (cities.data?.cities ?? []).filter((c) => c.metrics.sale_rows > 0).map((c) => c.city)

  const toggle = (item) =>
    setBasket((b) => (b.some((x) => key(x) === key(item)) ? b.filter((x) => key(x) !== key(item)) : b.length < 5 ? [...b, item] : b))

  return (
    <div className="stack-lg">
      <PageHeader title="Locality explorer" subtitle="Find the most attractive localities inside a city, then put up to 5 side by side on a radar chart." />
      <Tabs
        tabs={[{ id: 'ranking', label: 'Ranking' }, { id: 'compare', label: `Compare (${basket.length})` }]}
        active={tab} onChange={setTab}
      />
      {tab === 'ranking' ? (
        <Ranking
          {...{ city, setCity, profile, setProfile, minListings, setMinListings, sort, setSort, withListings, basket, toggle }}
        />
      ) : (
        <CompareLocalities basket={basket} toggle={toggle} profile={profile} minListings={minListings} goRanking={() => setTab('ranking')} />
      )}
    </div>
  )
}

function Ranking(p) {
  const { data, error, loading } = useApi('/locality-scores', {
    city: p.city, profile: p.profile, min_listings: p.minListings, sort: p.sort, limit: 60,
  })
  const rows = data?.localities ?? []
  const top = [...rows].sort((a, b) => b.score - a.score).slice(0, 15)

  return (
    <div className="stack">
      <Card>
        <div className="form">
          <label>City
            <select value={p.city} onChange={(e) => p.setCity(e.target.value)}>
              {p.withListings.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label>Investor profile
            <select value={p.profile} onChange={(e) => p.setProfile(e.target.value)}>
              <option value="conservative">Conservative</option><option value="balanced">Balanced</option><option value="aggressive">Aggressive</option>
            </select>
          </label>
          <label>Minimum listings
            <select value={p.minListings} onChange={(e) => p.setMinListings(Number(e.target.value))}>
              {[10, 20, 30, 50, 100].map((n) => <option key={n} value={n}>{n}+</option>)}
            </select>
          </label>
          <label>Sort by
            <select value={p.sort} onChange={(e) => p.setSort(e.target.value)}>
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        </div>
      </Card>

      <Status loading={loading && !data} error={error}>
        {data && (
          <>
            <Card title={`Top localities in ${data.city}`} subtitle={`City score ${fmt(data.city_score, 1)}. ${data.count} localities have ${data.min_listings}+ listings.`}>
              <Plot
                height={Math.max(300, top.length * 28 + 80)}
                data={[{
                  type: 'bar', orientation: 'h', y: top.map((r) => r.locality), x: top.map((r) => r.score),
                  marker: { color: top.map((r) => r.score), colorscale: [[0, '#bfdbfe'], [1, '#1d4ed8']] },
                  hovertemplate: '%{y}: %{x:.1f}<extra></extra>',
                }]}
                layout={{ yaxis: { autorange: 'reversed' }, xaxis: { title: 'Locality investment score', range: [0, 100] }, margin: { l: 150, r: 20, t: 10, b: 50 } }}
              />
              <p className="note">{data.method}</p>
            </Card>

            <Card title="All localities" subtitle="Tick up to 5 to compare them on a radar chart">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th /><th>#</th><th>Locality</th><th>Score</th><th>Listings</th><th>₹/sqft</th><th>vs city</th><th>Median price</th><th>Rent ₹/sqft</th><th>Yield vs city</th></tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const item = { city: data.city, locality: r.locality }
                      const on = p.basket.some((x) => key(x) === key(item))
                      return (
                        <tr key={r.locality} className={on ? 'hl' : ''}>
                          <td><input type="checkbox" checked={on} onChange={() => p.toggle(item)} aria-label={`Compare ${r.locality}`} /></td>
                          <td>{r.rank}</td><td>{r.locality}</td><td><b>{fmt(r.score, 1)}</b></td><td>{fmt(r.listings)}</td>
                          <td>{fmt(r.median_price_psf)}</td>
                          <td className={r.price_vs_city_pct < 0 ? 'pos' : 'neg'}>{pct(r.price_vs_city_pct, 0)}</td>
                          <td>{lakh(r.median_price_lakh)}</td>
                          <td>{isNum(r.median_rent_psf) ? fmt(r.median_rent_psf, 1) : '—'}</td>
                          <td className={r.yield_vs_city_pct < 0 ? 'neg' : 'pos'}>{isNum(r.yield_vs_city_pct) ? pct(r.yield_vs_city_pct, 0) : '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="muted small">“vs city” is green when the locality is cheaper than the city median. “Yield vs city” compares rent-to-price with the city's own ratio; “—” means fewer than 10 rent listings.</p>
            </Card>
          </>
        )}
      </Status>
    </div>
  )
}

function CompareLocalities({ basket, toggle, profile, minListings, goRanking }) {
  const valid = basket.length >= 2
  const { data, error, loading } = useApi(valid ? '/locality-compare' : null, { item: basket.map(key), profile, min_listings: minListings })

  return (
    <div className="stack">
      <Card title="Your comparison" subtitle="Pick 2 to 5 localities in the Ranking tab. You can mix cities.">
        <div className="chips">
          {basket.map((b, i) => (
            <button key={key(b)} className="chip on" style={{ borderColor: COLORS[i] }} onClick={() => toggle(b)}>
              <i className="dot" style={{ background: COLORS[i] }} />{b.locality}, {b.city} ✕
            </button>
          ))}
          {basket.length === 0 && <span className="muted">Nothing selected yet.</span>}
        </div>
        {!valid && <p><button className="btn primary" onClick={goRanking}>Go pick localities</button> <span className="muted small">Select at least 2.</span></p>}
      </Card>

      {valid && (
        <Status loading={loading && !data} error={error}>
          {data && (
            <>
              <Card title="Radar comparison" subtitle="Each axis is 0–100. Further out is better.">
                <Plot
                  height={460}
                  data={data.items.map((it, i) => {
                    const labels = data.axes.map((a) => a.label)
                    const vals = data.axes.map((a) => it.radar[a.key] ?? 0)
                    return {
                      type: 'scatterpolar', mode: 'lines+markers', fill: 'toself', name: `${it.locality} (${it.city})`,
                      r: [...vals, vals[0]], theta: [...labels, labels[0]],
                      line: { color: COLORS[i] }, fillcolor: `${COLORS[i]}22`,
                      hovertemplate: '%{theta}: %{r:.0f}<extra>' + it.locality + '</extra>',
                    }
                  })}
                  layout={{ polar: { radialaxis: { range: [0, 100], tickvals: [0, 25, 50, 75, 100] } }, margin: { l: 60, r: 60, t: 30, b: 60 } }}
                />
                <p className="note">{data.note} An axis showing 0 may mean “no data” (for example, fewer than 10 rent listings for yield).</p>
              </Card>
              <Card title="Numbers">
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th /> {data.items.map((it) => <th key={key(it)}>{it.locality}<div className="muted small">{it.city}</div></th>)}</tr>
                    </thead>
                    <tbody>
                      {[
                        ['Investment score', (it) => <b>{fmt(it.score, 1)}</b>],
                        ['Rank in city', (it) => `#${it.rank_in_city} of ${it.localities_in_city}`],
                        ['Listings', (it) => fmt(it.listings)],
                        ['Median ₹/sqft', (it) => fmt(it.median_price_psf)],
                        ['vs city median', (it) => pct(it.price_vs_city_pct, 0)],
                        ['Median price', (it) => lakh(it.median_price_lakh)],
                        ['Median rent ₹/sqft', (it) => (isNum(it.median_rent_psf) ? fmt(it.median_rent_psf, 1) : '—')],
                        ['Yield vs city', (it) => (isNum(it.yield_vs_city_pct) ? pct(it.yield_vs_city_pct, 0) : '—')],
                      ].map(([label, f]) => (
                        <tr key={label}><td>{label}</td>{data.items.map((it) => <td key={key(it)}>{f(it)}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
              <p className="small muted">Want the bigger picture? See the <Link to="/cities">city rankings</Link>.</p>
            </>
          )}
        </Status>
      )}
    </div>
  )
}
