/* Polling dashboard stats toutes les 30 secondes */
(function () {
  const INTERVAL = 30000;

  const el = (id) => document.getElementById(id);

  function formatDatetime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  async function refreshStats() {
    try {
      const res = await fetch('/api/dashboard/stats');
      if (!res.ok) return;
      const data = await res.json();

      const elOpen = el('kpi-incidents-open');
      if (elOpen) elOpen.textContent = data.incidents_open ?? '—';

      const elCrit = el('kpi-incidents-critical');
      if (elCrit) elCrit.textContent = data.incidents_critical ?? '—';

      const elTemp = el('kpi-temp');
      if (elTemp && data.last_temp != null) elTemp.textContent = data.last_temp + '°C';

      const elHum = el('kpi-hum');
      if (elHum && data.last_hum != null) elHum.textContent = data.last_hum + '%';

      if (data.latest_alert) {
        const elAlertName = el('kpi-last-alert-name');
        const elAlertSev  = el('kpi-last-alert-sev');
        if (elAlertName) elAlertName.textContent = data.latest_alert.rule_name || '—';
        if (elAlertSev) {
          elAlertSev.textContent = data.latest_alert.severity || '—';
          elAlertSev.className = 'badge sev-' + (data.latest_alert.severity || 'unknown');
        }
      }

      const elRefresh = el('last-refresh');
      if (elRefresh) elRefresh.textContent = 'Dernière actualisation : ' + formatDatetime(new Date().toISOString());

    } catch (_) { /* fail silently */ }
  }

  setInterval(refreshStats, INTERVAL);
})();
