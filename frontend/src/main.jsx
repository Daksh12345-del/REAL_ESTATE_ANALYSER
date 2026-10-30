import { Component, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'

// Shows the real error on screen when a component crashes, instead of a blank page.
class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <pre style={{ whiteSpace: 'pre-wrap', margin: 16, padding: 16, background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', borderRadius: 8, font: '13px/1.6 monospace' }}>
          {'A component crashed. Please copy this message:\n\n'}
          {String(this.state.error?.stack || this.state.error)}
        </pre>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
