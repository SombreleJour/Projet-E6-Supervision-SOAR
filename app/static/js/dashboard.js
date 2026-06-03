/* Polling dashboard stats — intervalle piloté par l'onglet Paramètres */
(function () {
  const INTERVAL = (window.SUPERVISION && window.SUPERVISION.refreshMs) || 30000;
  const SECS = Math.round(INTERVAL / 1000);

  const el = (id) => document.getElementById(id);

  function timeNow() {
    return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Libellé initial : reflète la fréquence configurée dans les Paramètres.
  const labelInit = el('last-refresh');
  if (labelInit) labelInit.textContent = 'Actualisation toutes les ' + SECS + 's';

  async function refreshStats() {
    try {
      const res = await fetch('/api/dashboard/stats', { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (res.status === 401) { window.location.replace('/login?reason=timeout'); return; }
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
      if (elRefresh) elRefresh.textContent = 'Actualisation toutes les ' + SECS + 's · maj ' + timeNow();

    } catch (_) { /* fail silently */ }
  }

  /* Sections d'intégration (PRTG/Wazuh) : on remplace le fragment HTML rendu serveur. */
  async function pollSection(id, url) {
    const box = document.getElementById(id);
    if (!box) return;
    try {
      const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, cache: 'no-store' });
      if (res.status === 401) { window.location.replace('/login?reason=timeout'); return; }
      if (!res.ok) return;
      box.innerHTML = await res.text();
    } catch (_) { /* silencieux */ }
  }

  function pollIntegrations() {
    pollSection('prtg-section', '/dashboard/prtg-section');
    pollSection('wazuh-section', '/dashboard/wazuh-section');
  }

  refreshStats();
  setInterval(refreshStats, INTERVAL);
  setInterval(pollIntegrations, INTERVAL);
})();
