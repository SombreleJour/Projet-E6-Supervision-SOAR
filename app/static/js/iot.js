/* Graphique IoT — historique complet, défilable horizontalement + refresh piloté par les Paramètres */
(function () {
  const INTERVAL = (window.SUPERVISION && window.SUPERVISION.refreshMs) || 60000;
  const thresholds = (typeof IOT_THRESHOLDS !== 'undefined') ? IOT_THRESHOLDS : null;
  const PX_PER_POINT = 6;            // largeur allouée par mesure (défilement horizontal)

  const canvas   = document.getElementById('iotChart');
  const scroller = document.getElementById('iot-chart-scroll');
  const inner    = document.getElementById('iot-chart-inner');

  // Libellé « Actualisation toutes les Xs » synchronisé avec les Paramètres.
  const labelEl = document.getElementById('iot-refresh-label');
  if (labelEl) labelEl.textContent = 'Actualisation toutes les ' + Math.round(INTERVAL / 1000) + 's';

  if (!canvas) return;

  let chart = null;
  let firstRender = true;

  function pad(n) { return n.toString().padStart(2, '0'); }

  function formatLabel(iso) {
    const d = new Date(iso);
    return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function buildChart(readings) {
    const labels = readings.map(r => formatLabel(r.recorded_at));
    const temps  = readings.map(r => r.temperature);
    const hums   = readings.map(r => r.humidity);
    const dense  = readings.length > 500;

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
            tension: dense ? 0 : 0.3,
            pointRadius: readings.length > 60 ? 0 : 3,
            borderWidth: 1.5,
          },
          {
            label: 'Humidité (%)',
            data: hums,
            borderColor: 'rgba(13, 110, 253, 0.9)',
            backgroundColor: 'rgba(13, 110, 253, 0.1)',
            yAxisID: 'yHum',
            tension: dense ? 0 : 0.3,
            pointRadius: readings.length > 60 ? 0 : 3,
            borderWidth: 1.5,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { labels: { color: '#adb5bd' } },
        },
        scales: {
          x: {
            ticks: { color: '#6c757d', autoSkip: true, maxRotation: 0, autoSkipPadding: 24 },
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
      chart.update('none');
    } else {
      chart = new Chart(canvas, config);
    }
  }

  /* Largeur de la zone graphique ∝ nombre de mesures (déborde => défilement). */
  function applyWidth(n) {
    if (!inner) return;
    const minW = scroller ? scroller.clientWidth : 0;
    inner.style.width = Math.max(minW, n * PX_PER_POINT) + 'px';
  }

  /* Rend le graphe en préservant la position de défilement de l'utilisateur. */
  function render(readings) {
    if (!scroller || !inner) { buildChart(readings); return; }
    const atRight = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 5;
    const prevLeft = scroller.scrollLeft;
    buildChart(readings);
    applyWidth(readings.length);
    requestAnimationFrame(() => {
      // Vue par défaut = dernières mesures (droite) ; on défile vers la gauche
      // pour remonter jusqu'à la première donnée enregistrée.
      scroller.scrollLeft = (firstRender || atRight) ? scroller.scrollWidth : prevLeft;
      firstRender = false;
    });
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
      const res = await fetch('/api/iot/readings?all=1', { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (res.status === 401) { window.location.replace('/login?reason=timeout'); return; }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const readings = await res.json();
      render(readings);
      if (readings.length) updateLive(readings[readings.length - 1]);
      if (statusEl) statusEl.textContent = readings.length + ' mesures (historique complet)';
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Erreur de chargement';
    }
  }

  /* Initialisation avec les données injectées par le template (pas de fetch initial). */
  if (typeof IOT_HISTORY_JSON !== 'undefined' && IOT_HISTORY_JSON.length > 0) {
    render(IOT_HISTORY_JSON);
    updateLive(IOT_HISTORY_JSON[IOT_HISTORY_JSON.length - 1]);
    const statusEl = document.getElementById('chart-status');
    if (statusEl) statusEl.textContent = IOT_HISTORY_JSON.length + ' mesures (historique complet)';
  } else {
    loadData();
  }

  setInterval(loadData, INTERVAL);

  // Recalcule la largeur minimale du graphe si la fenêtre est redimensionnée.
  window.addEventListener('resize', () => { if (chart) applyWidth(chart.data.labels.length); });
})();
