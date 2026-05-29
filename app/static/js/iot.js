/* Graphique IoT — Chart.js double axe Y + refresh 60s */
(function () {
  const INTERVAL = 60000;
  const canvas = document.getElementById('iotChart');
  if (!canvas) return;

  let chart = null;

  function formatLabel(isoString) {
    const d = new Date(isoString);
    return d.getHours().toString().padStart(2, '0') + ':' +
           d.getMinutes().toString().padStart(2, '0');
  }

  function buildChart(readings) {
    const labels = readings.map(r => formatLabel(r.recorded_at));
    const temps  = readings.map(r => r.temperature);
    const hums   = readings.map(r => r.humidity);

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Température (°C)',
            data: temps,
            borderColor: 'rgba(220, 53, 69, 0.9)',
            backgroundColor: 'rgba(220, 53, 69, 0.1)',
            yAxisID: 'yTemp',
            tension: 0.3,
            pointRadius: readings.length > 60 ? 0 : 3,
          },
          {
            label: 'Humidité (%)',
            data: hums,
            borderColor: 'rgba(13, 110, 253, 0.9)',
            backgroundColor: 'rgba(13, 110, 253, 0.1)',
            yAxisID: 'yHum',
            tension: 0.3,
            pointRadius: readings.length > 60 ? 0 : 3,
          }
        ]
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { labels: { color: '#adb5bd' } },
        },
        scales: {
          x: {
            ticks: { color: '#6c757d', maxTicksLimit: 12 },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          yTemp: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: '°C', color: 'rgba(220,53,69,0.9)' },
            ticks: { color: 'rgba(220,53,69,0.9)' },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          yHum: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: '%', color: 'rgba(13,110,253,0.9)' },
            ticks: { color: 'rgba(13,110,253,0.9)' },
            grid: { drawOnChartArea: false },
          },
        }
      }
    };

    if (chart) {
      chart.data = config.data;
      chart.update();
    } else {
      chart = new Chart(canvas, config);
    }
  }

  async function loadData() {
    const statusEl = document.getElementById('chart-status');
    try {
      const res = await fetch('/api/iot/readings?hours=24');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const readings = await res.json();
      buildChart(readings);
      if (statusEl) statusEl.textContent = readings.length + ' mesures (24h)';
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Erreur de chargement';
    }
  }

  /* Initialisation avec les données injectées par le template (pas de fetch initial) */
  if (typeof IOT_HISTORY_JSON !== 'undefined' && IOT_HISTORY_JSON.length > 0) {
    buildChart(IOT_HISTORY_JSON);
    const statusEl = document.getElementById('chart-status');
    if (statusEl) statusEl.textContent = IOT_HISTORY_JSON.length + ' mesures (24h)';
  } else {
    loadData();
  }

  setInterval(loadData, INTERVAL);
})();
