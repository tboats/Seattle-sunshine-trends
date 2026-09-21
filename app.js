/**
 * Seattle Sunshine Trends (1950-2026) - Interactive Visualizer
 */

let state = {
  data: null,
  activeMetric: 'total_sun_hours',
  showTrendline: true,
  showRolling: true,
  colorByEnso: true,
  charts: {}
};

const METRIC_CONFIGS = {
  total_sun_hours: {
    title: 'Annual Sunshine Hours in Seattle (1950–2026)',
    desc: 'Total hours per year where direct solar irradiance exceeded 120 W/m² (WMO standard). Solid emerald line shows the Sen\'s slope trendline.',
    unit: 'Hours',
    yLabel: 'Sunshine Hours / Year'
  },
  clear_days: {
    title: 'Strict Clear Days (NOAA Definition: ≤30% Cloud Cover)',
    desc: 'Days per year with average daytime cloud cover between 0% and 30%. Seattle averages ~74 such days.',
    unit: 'Days',
    yLabel: 'Clear Days / Year'
  },
  any_sun_days: {
    title: 'Any Sun / Sun Break Days (Clear + Partly Cloudy: ≤70% Clouds)',
    desc: 'Days where Seattle was not completely overcast. Accounts for ~165 days per year.',
    unit: 'Days',
    yLabel: 'Days with Sun / Year'
  },
  half_sunny_days: {
    title: 'Majority Sun Days (≥50% of Daylight with Direct Sun)',
    desc: 'Days where direct sunshine was present for more than half of the astronomical sunrise-to-sunset period.',
    unit: 'Days',
    yLabel: 'Majority Sun Days / Year'
  },
  glorious_days: {
    title: 'Glorious Seattle Days (≥70% Daylight Sun + Zero Rain)',
    desc: 'The quintessential brilliant Pacific Northwest day: blue skies, high sunshine, and absolutely zero precipitation.',
    unit: 'Days',
    yLabel: 'Glorious Days / Year'
  },
  total_rad_gj: {
    title: 'Annual Global Solar Energy (Shortwave Radiation)',
    desc: 'Total surface solar irradiance in Gigajoules per square meter (GJ/m²). Directly captures total light energy reaching the ground.',
    unit: 'GJ/m²',
    yLabel: 'Solar Energy (GJ/m²)'
  }
};

const ENSO_COLORS = {
  'Super El Niño': '#f43f5e',
  'Strong El Niño': '#fb923c',
  'El Niño': '#f59e0b',
  'Neutral': '#94a3b8',
  'La Niña': '#38bdf8',
  'Strong La Niña': '#0284c7'
};

async function init() {
  if (window.SEATTLE_SUNSHINE_TRENDS) {
    state.data = window.SEATTLE_SUNSHINE_TRENDS;
  } else {
    try {
      const resp = await fetch('data/sunshine_trends.json');
      state.data = await resp.json();
    } catch (err) {
      console.error('Failed to load sunshine trends data:', err);
      return;
    }
  }

  setupEventListeners();
  updateTopMetrics();
  renderMainChart();
  renderThresholdComparisonChart();
  renderSeasonalShiftChart();
  renderEnsoScatterChart();
  renderDecadalTable();
}

function setupEventListeners() {
  // Metric selector tabs
  document.querySelectorAll('#metric-selector .btn-tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('#metric-selector .btn-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeMetric = btn.dataset.metric;
      updateMainChart();
    });
  });

  // Toggles
  document.getElementById('toggle-trendline').addEventListener('change', (e) => {
    state.showTrendline = e.target.checked;
    updateMainChart();
  });

  document.getElementById('toggle-rolling').addEventListener('change', (e) => {
    state.showRolling = e.target.checked;
    updateMainChart();
  });

  document.getElementById('toggle-enso-colors').addEventListener('change', (e) => {
    state.colorByEnso = e.target.checked;
    updateMainChart();
  });
}

function updateTopMetrics() {
  const d = state.data;
  if (!d) return;

  const sunTrend = d.trends.total_sun_hours;
  const slopeVal = sunTrend.sens_slope_per_decade;
  const pVal = sunTrend.mann_kendall.p_value;

  const elSlope = document.getElementById('val-trend-slope');
  if (elSlope) {
    elSlope.textContent = (slopeVal >= 0 ? '+' : '') + slopeVal + ' hrs/dec';
  }
  
  const elSig = document.getElementById('val-trend-sig');
  if (elSig) {
    elSig.textContent = `p = ${pVal.toFixed(3)} (${sunTrend.mann_kendall.trend === 'no_trend' ? 'No Trend' : sunTrend.mann_kendall.trend})`;
  }

  // Clear vs Any Sun ratio
  const lastDec = d.decadal_summary[d.decadal_summary.length - 1];
  const elRatio = document.getElementById('val-clear-ratio');
  if (elRatio && lastDec) {
    elRatio.textContent = `${Math.round(lastDec.avg_clear_days)} vs. ${Math.round(lastDec.avg_any_sun_days)} Days`;
  }

  // Rain vs Cloud Decoupling (-16.6 in)
  const firstDec = d.decadal_summary[0];
  const elSummer = document.getElementById('val-summer-growth');
  if (elSummer && firstDec && lastDec) {
    const rainDiff = (lastDec.avg_precip_in - firstDec.avg_precip_in).toFixed(1);
    elSummer.textContent = `${rainDiff} in Rain`;
  }

  // ENSO Spread: Strong El Niño vs Strong La Niña
  const elEnso = document.getElementById('val-enso-boost');
  if (elEnso) {
    const sElNino = d.enso_attribution.stats_by_phase['Strong El Niño']?.avg_sun_hours || 3093.1;
    const sLaNina = d.enso_attribution.stats_by_phase['Strong La Niña']?.avg_sun_hours || 2995.9;
    const spread = (sElNino - sLaNina).toFixed(1);
    elEnso.textContent = `+${spread} hrs`;
  }

  // Stat pills in text
  const pText = document.getElementById('stat-mk-p');
  if (pText) pText.textContent = `p = ${pVal.toFixed(3)}`;
  const sText = document.getElementById('stat-slope-text');
  if (sText) sText.textContent = `${(slopeVal >= 0 ? '+' : '')}${slopeVal} hrs/decade`;
}

// -------------------------------------------------------------
// Chart 1: Multi-Decadal Time Series (Main)
// -------------------------------------------------------------
function renderMainChart() {
  const ctx = document.getElementById('main-trend-chart');
  if (!ctx) return;

  const d = state.data;
  // Strictly filter to complete years (1950 - 2025) so incomplete 2026 does not distort fits or rolling averages
  const records = d.annual_records.filter(r => r.is_complete_year);
  const metric = state.activeMetric;
  const cfg = METRIC_CONFIGS[metric];

  document.getElementById('main-chart-title').textContent = cfg.title + ' (1950–2025 Complete Baseline)';
  document.getElementById('main-chart-desc').textContent = cfg.desc + ' Note: Statistical fit and rolling averages strictly include complete years (1950–2025).';

  const years = records.map(r => r.year);
  const values = records.map(r => r[metric]);

  // Sen's slope line values formatted as {x, y}
  const tr = d.trends[metric];
  const slopeData = tr ? years.map(yr => ({
    x: yr,
    y: +(tr.sens_intercept + tr.sens_slope_per_year * yr).toFixed(2)
  })) : [];

  // 10-year rolling mean computed strictly on complete years
  const rollingData = [];
  for (let i = 0; i < values.length; i++) {
    const startIdx = Math.max(0, i - 9);
    const slice = values.slice(startIdx, i + 1).filter(v => v !== null && v !== undefined);
    const avg = slice.reduce((a, b) => a + b, 0) / slice.length;
    rollingData.push({ x: years[i], y: +avg.toFixed(2) });
  }

  // Point background colors
  const pointColors = records.map(r => {
    if (!state.colorByEnso) return '#f59e0b';
    return ENSO_COLORS[r.enso_phase] || '#94a3b8';
  });

  const scatterData = records.map(r => ({
    x: r.year,
    y: r[metric]
  }));

  const datasets = [
    {
      label: 'Observed Annual ' + cfg.unit + ' (1950–2025)',
      data: scatterData,
      type: 'scatter',
      pointBackgroundColor: pointColors,
      pointBorderColor: 'rgba(255, 255, 255, 0.4)',
      pointBorderWidth: 1,
      pointRadius: records.map(r => r.enso_phase === 'Super El Niño' ? 6.5 : 4.5),
      pointHoverRadius: 8,
      order: 1
    }
  ];

  if (state.showRolling) {
    datasets.push({
      label: '10-Year Rolling Mean',
      data: rollingData,
      type: 'line',
      borderColor: '#38bdf8',
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      order: 2
    });
  }

  if (state.showTrendline && tr) {
    datasets.push({
      label: `Sen's Trendline (${tr.sens_slope_per_decade >= 0 ? '+' : ''}${tr.sens_slope_per_decade} ${cfg.unit}/dec)`,
      data: slopeData,
      type: 'line',
      borderColor: '#10b981',
      borderWidth: 2,
      borderDash: [5, 5],
      pointRadius: 0,
      order: 3
    });
  }

  if (state.charts.main) {
    state.charts.main.destroy();
  }

  state.charts.main = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          labels: {
            color: '#94a3b8',
            font: { family: 'Inter', size: 12 }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(17, 23, 38, 0.95)',
          titleColor: '#f8fafc',
          bodyColor: '#cbd5e1',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            title: function(items) {
              const yr = years[items[0].dataIndex];
              const r = records[items[0].dataIndex];
              return `${yr} (${r.enso_phase})`;
            },
            label: function(item) {
              const r = records[item.dataIndex];
              return [
                `Observed: ${r[metric]} ${cfg.unit}`,
                `Strict Clear Days: ${r.clear_days} days`,
                `Any Sun Days: ${r.any_sun_days} days`,
                `Annual Rain: ${r.total_precip_in} in`,
                `Winter ONI: ${r.oni_winter_djf >= 0 ? '+' : ''}${r.oni_winter_djf}°C`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          position: 'bottom',
          min: 1949,
          max: 2027,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#64748b',
            stepSize: 10,
            callback: v => v.toString()
          }
        },
        y: {
          title: {
            display: true,
            text: cfg.yLabel,
            color: '#94a3b8'
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

function updateMainChart() {
  renderMainChart();
}

// -------------------------------------------------------------
// Chart 2: Definition Sensitivity Comparison (Decadal Bars)
// -------------------------------------------------------------
function renderThresholdComparisonChart() {
  const ctx = document.getElementById('threshold-comparison-chart');
  if (!ctx) return;

  const decs = state.data.decadal_summary;
  const labels = decs.map(d => d.decade);

  if (state.charts.thresh) {
    state.charts.thresh.destroy();
  }

  state.charts.thresh = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Strict Clear (≤30% clouds)',
          data: decs.map(d => d.avg_clear_days),
          backgroundColor: '#38bdf8'
        },
        {
          label: 'Majority Sun (≥50% daylight)',
          data: decs.map(d => d.avg_half_sunny_days),
          backgroundColor: '#f59e0b'
        },
        {
          label: 'Glorious Days (≥70% + 0 rain)',
          data: decs.map(d => d.avg_glorious_days),
          backgroundColor: '#10b981'
        },
        {
          label: 'Any Sun / Breaks (≤70% clouds)',
          data: decs.map(d => d.avg_any_sun_days),
          backgroundColor: 'rgba(255, 255, 255, 0.2)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: function(c) {
              return `${c.dataset.label}: ${c.raw.toFixed(1)} days/year`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: 'Average Days per Year', color: '#94a3b8' },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

// -------------------------------------------------------------
// Chart 3: Seasonal Shift Breakdown
// -------------------------------------------------------------
function renderSeasonalShiftChart() {
  const ctx = document.getElementById('seasonal-shift-chart');
  if (!ctx) return;

  const d = state.data;
  const decs = d.decadal_summary;
  const sTrends = d.seasonal_trends;

  // Aggregate seasonal records by decade
  const sRecs = d.seasonal_records;
  const seasons = ['Summer', 'Spring', 'Autumn', 'Winter'];
  const colors = {
    'Summer': '#f59e0b',
    'Spring': '#10b981',
    'Autumn': '#fb923c',
    'Winter': '#38bdf8'
  };

  const decadeBins = [
    { label: '1950s', y1: 1950, y2: 1959 },
    { label: '1960s', y1: 1960, y2: 1969 },
    { label: '1970s', y1: 1970, y2: 1979 },
    { label: '1980s', y1: 1980, y2: 1989 },
    { label: '1990s', y1: 1990, y2: 1999 },
    { label: '2000s', y1: 2000, y2: 2009 },
    { label: '2010s', y1: 2010, y2: 2019 },
    { label: '2020s', y1: 2020, y2: 2025 }
  ];

  const datasets = seasons.map(sName => {
    const data = decadeBins.map(bin => {
      const match = sRecs.filter(r => r.season === sName && r.year >= bin.y1 && r.year <= bin.y2);
      if (!match.length) return null;
      return +(match.reduce((acc, curr) => acc + curr.total_sun_hours, 0) / match.length).toFixed(1);
    });
    
    const slope = sTrends[sName].sun_hours.sens_slope_per_decade;
    return {
      label: `${sName} (${slope >= 0 ? '+' : ''}${slope} hrs/dec)`,
      data: data,
      borderColor: colors[sName],
      backgroundColor: colors[sName],
      borderWidth: 2.5,
      tension: 0.2
    };
  });

  if (state.charts.seasonal) {
    state.charts.seasonal.destroy();
  }

  state.charts.seasonal = new Chart(ctx, {
    type: 'line',
    data: {
      labels: decadeBins.map(b => b.label),
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: function(c) {
              return `${c.dataset.label.split(' ')[0]}: ${c.raw} hrs average`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: 'Total Seasonal Sun Hours', color: '#94a3b8' },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

// -------------------------------------------------------------
// Chart 4: ENSO De-Aliasing & Attribution Scatter
// -------------------------------------------------------------
function renderEnsoScatterChart() {
  const ctx = document.getElementById('enso-scatter-chart');
  if (!ctx) return;

  const d = state.data;
  // Strictly complete years (1950 - 2025)
  const records = d.annual_records.filter(r => r.is_complete_year);

  const scatterData = records.map(r => ({
    x: r.oni_winter_djf,
    y: r.total_sun_hours,
    year: r.year,
    phase: r.enso_phase
  }));

  // Fitted regression line across ONI range: -2.0 to +2.5
  const reg = d.enso_attribution.regression;
  const avgYrOffset = (2025 - 1950) / 2.0; // center at ~1987
  const regLine = [-2.0, 0.0, 2.0, 2.5].map(xVal => ({
    x: xVal,
    y: +(reg.b0_baseline_1950 + reg.b1_secular_slope_hrs_per_yr * avgYrOffset + reg.b2_enso_sensitivity_hrs_per_degC * xVal).toFixed(1)
  }));

  if (state.charts.enso) {
    state.charts.enso.destroy();
  }

  state.charts.enso = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Observed Years (Color by ENSO)',
          data: scatterData,
          pointBackgroundColor: records.map(r => ENSO_COLORS[r.enso_phase] || '#94a3b8'),
          pointBorderColor: 'rgba(255, 255, 255, 0.5)',
          pointBorderWidth: 1,
          pointRadius: records.map(r => r.year === 2026 ? 8 : (r.enso_phase === 'Super El Niño' ? 7 : 5)),
          order: 1
        },
        {
          label: `ENSO Sensitivity Slope (+${Math.round(reg.b2_enso_sensitivity_hrs_per_degC)} hrs / °C anomaly)`,
          data: regLine,
          type: 'line',
          borderColor: '#f43f5e',
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
          order: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { size: 12 } }
        },
        tooltip: {
          callbacks: {
            title: function(items) {
              const pt = items[0].raw;
              return `${pt.year} (${pt.phase})`;
            },
            label: function(item) {
              const pt = item.raw;
              return [
                `Winter ONI: ${pt.x >= 0 ? '+' : ''}${pt.x}°C`,
                `Total Sun: ${pt.y} Hours`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Winter Oceanic Niño Index (DJF SST Anomaly in °C)',
            color: '#94a3b8'
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#94a3b8',
            callback: v => `${v >= 0 ? '+' : ''}${v}°C`
          }
        },
        y: {
          title: {
            display: true,
            text: 'Annual Total Sunshine Hours',
            color: '#94a3b8'
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

// -------------------------------------------------------------
// Table: Decadal Summary
// -------------------------------------------------------------
function renderDecadalTable() {
  const tbody = document.getElementById('decadal-table-body');
  if (!tbody) return;

  const decs = state.data.decadal_summary;
  tbody.innerHTML = '';

  decs.forEach((d, idx) => {
    const tr = document.createElement('tr');
    if (idx === decs.length - 1) {
      tr.className = 'highlight-row';
    }
    tr.innerHTML = `
      <td><strong>${d.decade}</strong></td>
      <td><span class="stat-pill">${d.avg_sun_hours} hrs</span></td>
      <td>${d.avg_clear_days} days</td>
      <td>${d.avg_any_sun_days} days</td>
      <td>${d.avg_half_sunny_days} days</td>
      <td>${d.avg_glorious_days} days</td>
      <td>${d.avg_cloudy_days} days</td>
      <td>${d.avg_precip_in} in</td>
    `;
    tbody.appendChild(tr);
  });
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', init);
