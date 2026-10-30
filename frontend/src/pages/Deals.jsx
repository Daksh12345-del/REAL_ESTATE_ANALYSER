import { useState } from 'react'
import { get, useApi } from '../api'
import { Badge, Card, PageHeader, Status, Tabs } from '../components/ui'
import { fmt, lakh, pct } from '../utils'

export default function Deals() {
  const [tab, setTab] = useState('price')
  const cities = useApi('/cities')
  const withListings = (cities.data?.cities ?? []).filter((c) => c.metrics.sale_rows > 0).map((c) => c.city)
  return (
    <div className="stack-lg">
      <PageHeader title="Fair price & deals" subtitle="A machine-learning model estimates what a property should cost, based on similar listings." />
      <Tabs tabs={[{ id: 'price', label: 'Fair price checker' }, { id: 'deals', label: 'Undervalued listings' }]} active={tab} onChange={setTab} />
      <Status loading={cities.loading} error={cities.error}>
        {tab === 'price' ? <Checker cities={withListings} /> : <DealsList cities={withListings} />}
      </Status>
    </div>
  )
}

function Checker({ cities }) {
  const [f, setF] = useState({ city: 'Gurugram', locality: '', area_sqft: 1200, bhk: 2, asking_price_lakh: '' })
  const [res, setRes] = useState({ data: null, error: null, loading: false })
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setRes({ data: null, error: null, loading: true })
    try {
      setRes({ data: await get('/valuate', f), error: null, loading: false })
    } catch (err) {
      setRes({ data: null, error: err.message, loading: false })
    }
  }
  const d = res.data
  const tone = !d?.verdict ? 'gray' : d.verdict.startsWith('inside') ? 'green' : d.verdict.startsWith('below') ? 'amber' : 'red'

  return (
    <Card title="Fair price checker" subtitle="Typical error is about 15%, so treat it as a sanity check, not a valuation">
      <form className="form" onSubmit={submit}>
        <label>City
          <select value={f.city} onChange={set('city')}>{cities.map((c) => <option key={c}>{c}</option>)}</select>
        </label>
        <label>Locality / sector
          <input value={f.locality} onChange={set('locality')} placeholder="e.g. Sector 65" />
        </label>
        <label>Area (sq ft)<input type="number" min="200" max="10000" value={f.area_sqft} onChange={set('area_sqft')} /></label>
        <label>BHK<input type="number" min="1" max="10" value={f.bhk} onChange={set('bhk')} /></label>
        <label>Asking price (lakh, optional)<input type="number" min="0" value={f.asking_price_lakh} onChange={set('asking_price_lakh')} /></label>
        <button className="btn primary" type="submit">Estimate</button>
      </form>
      {res.loading && <div className="status">Estimating…</div>}
      {res.error && <div className="status error">{res.error}</div>}
      {d && (
        <div className="result">
          <div className="score-num">{lakh(d.fair_price_lakh)}</div>
          <p>Fair price estimate · ₹{fmt(d.fair_price_per_sqft)}/sqft · likely range {lakh(d.likely_range_lakh[0])} to {lakh(d.likely_range_lakh[1])}</p>
          <p className="muted small">{d.range_note}</p>
          {d.warning && <p className="note">{d.warning}</p>}
          {d.verdict && <p><Badge tone={tone}>{d.verdict}</Badge> <span className="muted small">asking is {pct(Math.abs(d.vs_fair_pct), 0)} {d.vs_fair_pct >= 0 ? 'below' : 'above'} the estimate</span></p>}
        </div>
      )}
    </Card>
  )
}

function DealsList({ cities }) {
  const [city, setCity] = useState('Noida')
  const { data, error, loading } = useApi('/undervalued', { city, limit: 25 })
  return (
    <Card
      title="Undervalued listing candidates"
      subtitle="Listings priced 15–35% below what the model expects. Candidates to verify, not recommendations."
      right={<select value={city} onChange={(e) => setCity(e.target.value)}>{cities.map((c) => <option key={c}>{c}</option>)}</select>}
    >
      <Status loading={loading} error={error}>
        {data && (
          <>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Locality</th><th>BHK</th><th>Area</th><th>Asking</th><th>Model fair price</th><th>Below fair</th><th>Similar listings</th></tr></thead>
                <tbody>
                  {data.listings.map((l, i) => (
                    <tr key={i}>
                      <td>{l.locality}</td><td>{l.bhk ?? '—'}</td><td>{fmt(l.area_sqft)} sqft</td>
                      <td>{lakh(l.price_lakh)}</td><td>{lakh(l.fair_price_lakh)}</td>
                      <td className="pos"><b>{pct(l.discount_pct, 0)}</b></td><td>{fmt(l.locality_listings)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note">{data.warning}</p>
          </>
        )}
      </Status>
    </Card>
  )
}
