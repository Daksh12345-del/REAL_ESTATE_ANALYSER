export const COMPONENTS = ['growth', 'yield', 'affordability', 'catalyst', 'stability']
export const COMPONENT_LABELS = {
  growth: 'Price growth',
  yield: 'Rental yield',
  affordability: 'Affordability',
  catalyst: 'Catalysts',
  stability: 'Stability',
}
export const COMPONENT_COLORS = {
  growth: '#2563eb',
  yield: '#16a34a',
  affordability: '#f59e0b',
  catalyst: '#9333ea',
  stability: '#64748b',
}
// Mirrors backend/services/scoring.py PROFILES (in %). The sliders send custom weights, so a mismatch is harmless.
export const PROFILES = {
  conservative: { growth: 15, yield: 30, affordability: 15, catalyst: 15, stability: 25 },
  balanced: { growth: 25, yield: 20, affordability: 15, catalyst: 25, stability: 15 },
  aggressive: { growth: 35, yield: 10, affordability: 10, catalyst: 35, stability: 10 },
}

export const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
export const fmt = (v, d = 0) =>
  isNum(v) ? v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—'
export const pct = (v, d = 1) => (isNum(v) ? `${v.toFixed(d)}%` : '—')
export const rs = (v) => (isNum(v) ? `₹${fmt(v)}` : '—')
export const lakh = (v) => {
  if (!isNum(v)) return '—'
  return v >= 100 ? `₹${(v / 100).toFixed(2)} Cr` : `₹${v.toFixed(1)} L`
}