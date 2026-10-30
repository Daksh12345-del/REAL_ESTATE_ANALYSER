import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get, useApi, useDebounced } from '../api'
import Plot from '../components/Plot'
import { Badge, Card, CityLink, PageHeader, Stat, Status } from '../components/ui'
import { fmt, isNum, lakh, pct } from '../utils'

const DEFAULTS = {
  down_payment_pct: 20, loan_rate_pct: 8, tenure_years: 20, appreciation_pct: 5, rent_growth_pct: 5,
  investment_return_pct: 8, horizon_years: 25, buying_cost_pct: 6, upkeep_pct: 0.75, selling_cost_pct: 2,
}

function Field({ label, hint, value, onChange, step = 1, min, max }) {
  return (
    <label className="field-row">
      <span>{label}{hint && <em className="muted small"> {hint}</em>}</span>
      <input type="number" value={value} step={step} min={min} max={max} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
    </label>
  )
}

export default function RentVsBuy() {
  const [qs] = useSearchParams()
  const cities = useApi('/cities')
  const withRent = (cities.data?.cities ?? []).filter((c) => c.metrics.rent_rows >= 100).map((c) => c.city)
  const [city, setCity] = useState(qs.get('city') || 'Pune')
  const [area, setArea] = useState(1000)
  const [f, setF] = useState({ ...DEFAULTS, price_lakh: 100, monthly_rent: 25000 })
  const [note, setNote] = useState(null)
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }))

  // load city defaults whenever the city or size changes
  const debArea = useDebounced(area, 500)
  useEffect(() => {
    let alive = true
    get('/rent-vs-buy/defaults', { city, area_sqft: debArea })
      .then((d) => {
        if (!alive) return
        setNote(d.monthly_rent ? d.note : `No rent data for ${city}; enter the rent yourself.`)
        setF((x) => ({ ...x, price_lakh: d.price_lakh, monthly_rent: d.monthly_rent ?? x.monthly_rent, appreciation_pct: d.appreciation_pct }))
      })
      .catch((e) => alive && setNote(e.message))
    return () => { alive = false }
  }, [city, debArea])

  const ready = isNum(f.price_lakh) && isNum(f.monthly_rent) && f.price_lakh > 0 && f.monthly_rent > 0
  const debF = useDebounced(f, 400)
  const sim = useApi(ready ? '/rent-vs-buy' : null, debF)
  const table = useApi('/rent-vs-buy/cities', { area_sqft: debArea })

  return (
    <div className="stack-lg">
      <PageHeader title="Rent vs buy" subtitle="Does buying beat renting and investing the difference? Change the assumptions and see when (and whether) buying pulls ahead." />
      <div className="grid two-col">
        <aside>
          <Card title="Your home" subtitle="City values are pre-filled; edit anything">
            <label className="field-row"><span>City</span>
              <select value={city} onChange={(e) => setCity(e.target.value)}>
                {(withRent.length ? withRent : [city]).map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <Field label="Size" hint="sq ft" value={area} onChange={setArea} step={50} min={200} max={5000} />
            <Field label="Price" hint="₹ lakh" value={f.price_lakh} onChange={set('price_lakh')} step={5} min={5} />
            <Field label="Monthly rent" hint="₹" value={f.monthly_rent} onChange={set('monthly_rent')} step={500} min={1000} />
            {note && <p className="note">{note}</p>}
          </Card>
          <Card title="Loan and growth">
            <Field label="Down payment" hint="%" value={f.down_payment_pct} onChange={set('down_payment_pct')} min={0} max={90} />
            <Field label="Loan interest" hint="% a year" value={f.loan_rate_pct} onChange={set('loan_rate_pct')} step={0.1} min={0} max={20} />
            <Field label="Loan tenure" hint="years" value={f.tenure_years} onChange={set('tenure_years')} min={1} max={30} />
            <Field label="Property price growth" hint="% a year" value={f.appreciation_pct} onChange={set('appreciation_pct')} step={0.5} min={-10} max={25} />
            <Field label="Rent growth" hint="% a year" value={f.rent_growth_pct} onChange={set('rent_growth_pct')} step={0.5} min={-10} max={25} />
            <Field label="Return if money is invested" hint="% a year" value={f.investment_return_pct} onChange={set('investment_return_pct')} step={0.5} min={0} max={25} />
            <Field label="Compare over" hint="years" value={f.horizon_years} onChange={set('horizon_years')} min={1} max={35} />
            <details>
              <summary>More assumptions</summary>
              <Field label="Stamp duty + registration" hint="%" value={f.buying_cost_pct} onChange={set('buying_cost_pct')} step={0.5} min={0} max={15} />
              <Field label="Upkeep + property tax" hint="% of value a year" value={f.upkeep_pct} onChange={set('upkeep_pct')} step={0.05} min={0} max={5} />
              <Field label="Selling cost" hint="%" value={f.selling_cost_pct} onChange={set('selling_cost_pct')} step={0.5} min={0} max={10} />
            </details>
            <p className="muted small">Home-loan rates vary by lender and date (roughly 7% to 9%). Check current offers; tax benefits are not included.</p>
          </Card>
        </aside>

        <main>
          <Status loading={sim.loading && !sim.data} error={sim.error}>
            {sim.data && <Result d={sim.data} />}
          </Status>
          <Card title="Which cities favour buying?" subtitle={`A ${fmt(debArea)} sq ft home with default assumptions (20% down, 8% loan, 8% investment return, 5% rent growth)`}>
            <Status loading={table.loading} error={table.error}>
              {table.data && (
                <>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>City</th><th>Price</th><th>Rent / month</th><th>Rental yield</th><th>Price growth used</th><th>Break-even</th><th>Break-even at 5% growth</th></tr></thead>
                      <tbody>
                        {table.data.cities.map((c) => (
                          <tr key={c.city}>
                            <td><CityLink city={c.city} /></td><td>{lakh(c.price_lakh)}</td><td>₹{fmt(c.monthly_rent)}</td>
                            <td>{pct(c.gross_rental_yield_pct)}</td><td>{pct(c.appreciation_pct)}</td>
                            <td>{isNum(c.break_even_years) ? <Badge tone="green">{c.break_even_years} yrs</Badge> : <Badge tone="gray">never</Badge>}</td>
                            <td>{isNum(c.break_even_years_at_5pct) ? <Badge tone="green">{c.break_even_years_at_5pct} yrs</Badge> : <Badge tone="gray">never</Badge>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="note">{table.data.assumptions} “Never” means renting and investing the difference stays ahead for the whole 25 years. Cities that look good for buying mostly do so because of the high price growth assumed for them, which is exactly what is hardest to predict.</p>
                </>
              )}
            </Status>
          </Card>
        </main>
      </div>
    </div>
  )
}

function Result({ d }) {
  const yrs = d.yearly.map((y) => y.year)
  const gap = Math.abs(d.final_gap_lakh)
  return (
    <div className="stack">
      <div className={`verdict ${d.buyer_wins_at_horizon ? 'good' : 'warn'}`}>
        {d.buyer_wins_at_horizon
          ? <>Buying overtakes renting after about <b>{d.break_even_years} years</b>, and is ahead by <b>{lakh(gap)}</b> after {d.inputs.horizon_years} years.</>
          : <>Under these assumptions, renting and investing the difference stays ahead of buying, by <b>{lakh(gap)}</b> after {d.inputs.horizon_years} years.</>}
      </div>
      <div className="stats">
        <Stat label="Monthly EMI" value={`₹${fmt(d.emi)}`} hint={`+ upkeep: ₹${fmt(d.first_year_monthly_outflow)} a month`} />
        <Stat label="Cash needed up front" value={lakh(d.upfront_cash_lakh)} hint="down payment + buying costs" />
        <Stat label="Rental yield" value={pct(d.gross_rental_yield_pct)} hint="annual rent / price" />
        <Stat label="Price-to-rent" value={`${d.price_to_annual_rent}x`} hint="years of rent to equal price" />
      </div>
      <Card title="Net worth over time" subtitle="Buyer: property value after selling costs minus loan. Renter: the invested up-front cash plus every month's saving.">
        <Plot
          height={360}
          data={[
            { type: 'scatter', mode: 'lines', name: 'Buy', x: yrs, y: d.yearly.map((y) => y.buyer_net_worth_lakh), line: { color: '#2563eb', width: 3 } },
            { type: 'scatter', mode: 'lines', name: 'Rent and invest', x: yrs, y: d.yearly.map((y) => y.renter_net_worth_lakh), line: { color: '#f59e0b', width: 3 } },
          ]}
          layout={{
            xaxis: { title: 'Years' }, yaxis: { title: 'Net worth (₹ lakh)' },
            shapes: isNum(d.break_even_years) ? [{ type: 'line', x0: d.break_even_years, x1: d.break_even_years, yref: 'paper', y0: 0, y1: 1, line: { color: '#16a34a', dash: 'dot' } }] : [],
            annotations: isNum(d.break_even_years) ? [{ x: d.break_even_years, yref: 'paper', y: 1, text: 'break-even', showarrow: false, font: { color: '#16a34a' } }] : [],
          }}
        />
      </Card>
      <Card title="How much does the answer depend on price growth?" subtitle="Everything else unchanged. This is the assumption that matters most and the hardest to know.">
        <div className="grid two-col-even">
          <Plot
            height={280}
            data={[{
              type: 'bar', x: d.sensitivity.map((s) => `${s.appreciation_pct}%`), y: d.sensitivity.map((s) => s.final_gap_lakh),
              marker: { color: d.sensitivity.map((s) => (s.final_gap_lakh >= 0 ? '#16a34a' : '#dc2626')) },
              hovertemplate: 'Growth %{x}: buying is %{y:.0f} lakh ahead<extra></extra>',
            }]}
            layout={{ xaxis: { title: 'Property price growth a year', type: 'category' }, yaxis: { title: 'Buy minus rent (₹ lakh)' }, margin: { l: 60, r: 20, t: 10, b: 50 } }}
          />
          <div className="table-wrap">
            <table>
              <thead><tr><th>Price growth</th><th>Break-even</th><th>Buy minus rent</th></tr></thead>
              <tbody>
                {d.sensitivity.map((s) => (
                  <tr key={s.appreciation_pct}>
                    <td>{s.appreciation_pct}% a year</td>
                    <td>{isNum(s.break_even_years) ? `${s.break_even_years} years` : 'never'}</td>
                    <td className={s.final_gap_lakh >= 0 ? 'pos' : 'neg'}>{s.final_gap_lakh >= 0 ? '+' : '−'}{lakh(Math.abs(s.final_gap_lakh))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Card>
    </div>
  )
}
