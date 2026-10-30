import { Link } from 'react-router-dom'
import { useApi } from '../api'
import { Badge, Status, tierTone } from '../components/ui'
import { fmt, pct } from '../utils'

const TOOLS = [
  { to: '/cities', icon: '🏙️', title: 'City rankings', text: 'Investment score for 13 cities. Pick an investor profile or drag the weights yourself.' },
  { to: '/localities', icon: '📍', title: 'Locality explorer', text: 'Score localities inside a city, then compare them on a radar chart.' },
  { to: '/rent-vs-buy', icon: '⚖️', title: 'Rent vs buy', text: 'EMI, break-even year and how sensitive the answer is to price growth.' },
  { to: '/deals', icon: '🏷️', title: 'Fair price & deals', text: 'A model estimates a fair price; listings priced far below it are flagged to verify.' },
  { to: '/compare', icon: '🔀', title: 'Compare cities', text: 'Side-by-side metrics, score breakdown and price index for up to 6 cities.' },
  { to: '/methodology', icon: '🧪', title: 'Methodology', text: 'How the scores and models work, and what this data cannot tell you.' },
]

export default function Home() {
  const top = useApi('/opportunities', { top: 3, profile: 'balanced' })
  const info = useApi('/model-info')
  const cities = useApi('/cities')

  return (
    <div className="stack-lg">
      <section className="hero">
        <div>
          <span className="eyebrow">Real estate market analysis · India</span>
          <h1>Where should you invest: an established metro or a fast-growing industrial city?</h1>
          <p>
            Compare 13 cities and hundreds of localities using RBI price indices, NHB prices, {info.data ? fmt(info.data.listings) : '100,000+'} listings
            and a sourced list of infrastructure and industry catalysts. Every score comes with its reasoning and its limits.
          </p>
          <div className="btn-row">
            <Link className="btn primary lg" to="/cities">Explore city rankings</Link>
            <Link className="btn lg" to="/rent-vs-buy">Try rent vs buy</Link>
          </div>
        </div>
        <div className="hero-stats">
          <div><b>{cities.data ? cities.data.cities.length : '13'}</b><span>cities</span></div>
          <div><b>{info.data ? `${Math.round(info.data.listings / 1000)}k` : '128k'}</b><span>sale listings</span></div>
          <div><b>17</b><span>RBI HPI quarters</span></div>
          <div><b>5</b><span>score factors</span></div>
        </div>
      </section>

      <section>
        <h2 className="section-title">Top picks right now <span className="muted small">balanced profile</span></h2>
        <Status loading={top.loading} error={top.error}>
          <div className="grid three">
            {top.data?.results.map((r) => (
              <Link key={r.city} to={`/city/${r.city}`} className="pick">
                <div className="pick-head">
                  <span className="pick-rank">#{r.rank}</span>
                  <Badge tone={tierTone(r.tier_type)}>{r.tier_type}</Badge>
                </div>
                <h3>{r.city}</h3>
                <div className="pick-score">{fmt(r.score, 1)}<span> / 100</span></div>
                <p className="small muted">
                  Yield {pct(r.metrics.gross_yield_pct)} · HPI YoY {pct(r.metrics.hpi_yoy_pct)} · Catalysts {fmt(r.metrics.catalyst_score)}/10
                </p>
                <p className="small clamp">{r.catalysts.summary}</p>
              </Link>
            ))}
          </div>
        </Status>
      </section>

      <section>
        <h2 className="section-title">Tools</h2>
        <div className="grid three">
          {TOOLS.map((t) => (
            <Link key={t.to} to={t.to} className="tool">
              <span className="tool-icon">{t.icon}</span>
              <h3>{t.title}</h3>
              <p className="small muted">{t.text}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="how">
        <h2 className="section-title">How it works</h2>
        <div className="grid three">
          <div><b>1. Measure</b><p className="small muted">Price growth and stability from the RBI House Price Index, current prices from NHB Residex, rental yield from listings.</p></div>
          <div><b>2. Score</b><p className="small muted">Five factors are scaled 0 to 100 and weighted by your investor profile. Missing data re-weights the rest instead of being guessed.</p></div>
          <div><b>3. Stress-test</b><p className="small muted">Forecasts are backtested against a "no change" baseline, and rent vs buy shows how the answer flips with the growth assumption.</p></div>
        </div>
        <p className="note">Educational project. Listing data comes from public datasets of different years, so treat absolute prices as indicative. See Methodology for every limitation.</p>
      </section>
    </div>
  )
}
