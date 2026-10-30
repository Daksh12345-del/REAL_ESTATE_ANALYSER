import Plotly from 'plotly.js/lib/core'
import Scatter from 'plotly.js/lib/scatter'
import Bar from 'plotly.js/lib/bar'
import ScatterPolar from 'plotly.js/lib/scatterpolar'
import createPlotlyComponent from 'react-plotly.js/factory'

Plotly.register([Scatter, Bar, ScatterPolar])
const factory = createPlotlyComponent.default || createPlotlyComponent
const PlotComponent = factory(Plotly)

/** Thin wrapper with shared layout defaults. */
export default function Plot({ data, layout = {}, height = 340 }) {
  return (
    <PlotComponent
      data={data}
      layout={{
        autosize: true,
        height,
        margin: { l: 55, r: 20, t: 30, b: 50 },
        font: { family: 'system-ui, -apple-system, Segoe UI, sans-serif', size: 12, color: '#1e293b' },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        legend: { orientation: 'h', y: -0.22 },
        ...layout,
      }}
      config={{ displayModeBar: false, responsive: true }}
      useResizeHandler
      style={{ width: '100%' }}
    />
  )
}

/** Filled band between lo and hi (for confidence intervals). */
export function band(x, lo, hi, color, name) {
  return {
    x: [...x, ...[...x].reverse()],
    y: [...hi, ...[...lo].reverse()],
    fill: 'toself',
    fillcolor: color,
    line: { width: 0 },
    hoverinfo: 'skip',
    name,
    type: 'scatter',
    mode: 'lines',
  }
}
