/* Graphique IoT — Chart.js double axe Y + rafraîchissement piloté par les Paramètres */
(function () {
  const INTERVAL = (window.SUPERVISION && window.SUPERVISION.refreshMs) || 60000;
  const thresholds = (typeof IOT_THRESHOLDS !== 'undefined') ? IOT_THRESHOLDS : null;
  const canvas = document.getElementById('iotChart');

  // Libellé « Actualisation toutes les Xs » synchronisé avec les Paramètres.
  const labelEl = document.getElementById('iot-refresh-label');
  if (labelEl) labelEl.textContent = 'Actualisation toutes les ' + Math.round(INTERVAL / 1000) + 's';

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

  /* Met à jour le panneau « Dernière mesure » avec la lecture la plus récente. */
  function updateLive(reading) {
    if (!reading) return;
    const tempEl = document.getElementById('live-temp');
    const humEl  = document.getElementById('live-hum');
    const timeEl = document.getElementById('live-time');

    if (tempEl && reading.temperature != null) {
      tempEl.textContent = reading.temperature + '°C';
      if (thresholds) {
        const hot = reading.temperature > thresholds.temp_max || reading.temperature < thresholds.temp_min;
        tempEl.classList.toggle('text-red-400', hot);
        tempEl.classList.toggle('text-fg', !hot);
      }
    }
    if (humEl && reading.humidity != null) {
      humEl.textContent = reading.humidity + '%';
      if (thresholds) {
        const bad = reading.humidity > thresholds.hum_max || reading.humidity < thresholds.hum_min;
        humEl.classList.toggle('text-yellow-400', bad);
        humEl.classList.toggle('text-fg', !bad);
      }
    }
    if (timeEl && reading.recorded_at) {
      const d = new Date(reading.recorded_at);
      timeEl.textContent = d.toLocaleDateString('fr-FR') + ' à ' +
        d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }

  async function loadData() {
    const statusEl = document.getElementById('chart-status');
    try {
      const res = await fetch('/api/iot/readings?hours=24', { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (res.status === 401) { window.location.replace('/login?reason=timeout'); return; }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const readings = await res.json();
      buildChart(readings);
      if (readings.length) updateLive(readings[readings.length - 1]);
      if (statusEl) statusEl.textContent = readings.length + ' mesures (24h)';
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Erreur de chargement';
    }
  }

  /* Initialisation avec les données injectées par le template (pas de fetch initial). */
  if (typeof IOT_HISTORY_JSON !== 'undefined' && IOT_HISTORY_JSON.length > 0) {
    buildChart(IOT_HISTORY_JSON);
    updateLive(IOT_HISTORY_JSON[IOT_HISTORY_JSON.length - 1]);
    const statusEl = document.getElementById('chart-status');
    if (statusEl) statusEl.textContent = IOT_HISTORY_JSON.length + ' mesures (24h)';
  } else {
    loadData();
  }

  setInterval(loadData, INTERVAL);
})();
