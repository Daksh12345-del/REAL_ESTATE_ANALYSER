import { useEffect } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import City from './pages/City'
import Compare from './pages/Compare'
import Deals from './pages/Deals'
import Home from './pages/Home'
import Localities from './pages/Localities'
import Methodology from './pages/Methodology'
import Rankings from './pages/Rankings'
import RentVsBuy from './pages/RentVsBuy'

const LINKS = [
  ['/', 'Home', true], ['/cities', 'Cities'], ['/localities', 'Localities'], ['/rent-vs-buy', 'Rent vs buy'],
  ['/deals', 'Fair price & deals'], ['/compare', 'Compare'], ['/methodology', 'Methodology'],
]

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0) // braces: an effect must not return scrollTo's result
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <header className="nav">
        <div className="nav-inner">
          <NavLink to="/" className="brand"><span className="logo">▲</span> Real Estate Analyzer</NavLink>
          <nav>
            {LINKS.map(([to, label, end]) => <NavLink key={to} to={to} end={end}>{label}</NavLink>)}
          </nav>
        </div>
      </header>
      <div className="container">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/cities" element={<Rankings />} />
          <Route path="/city/:name" element={<City />} />
          <Route path="/localities" element={<Localities />} />
          <Route path="/rent-vs-buy" element={<RentVsBuy />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="*" element={<div className="status">Page not found.</div>} />
        </Routes>
      </div>
      <footer className="footer">
        Educational project, not financial advice. Data comes from public sources of different years; see Methodology for the limits.
      </footer>
    </>
  )
}
