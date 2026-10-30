import { Link } from 'react-router-dom'

export function Card({ title, subtitle, children, right }) {
  return (
    <section className="card">
      {(title || right) && (
        <div className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

export function Status({ loading, error, children }) {
  if (loading) return <div className="status">Loading…</div>
  if (error) return <div className="status error">{error}</div>
  return children
}

export function Badge({ children, tone = 'gray' }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

export const tierTone = (t) => (t === 'emerging' ? 'purple' : 'blue')
export const reliabilityTone = (r) => (r === 'medium' ? 'green' : r === 'low' ? 'amber' : 'red')

export function CityLink({ city }) {
  return <Link to={`/city/${encodeURIComponent(city)}`}>{city}</Link>
}

export function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} className={active === t.id ? 'tab on' : 'tab'} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {children && <div className="page-title-actions">{children}</div>}
    </div>
  )
}
