import os
import urllib3
import requests

from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_STATUS_OK = {3}
_STATUS_WARNING = {4}
_STATUS_ERROR = {5, 14}


def _base_url():
    return os.getenv('PRTG_BASE_URL', 'https://172.16.1.5')


def _auth_params():
    params = {'username': os.getenv('PRTG_USERNAME', 'prtgadmin'), 'output': 'json'}
    passhash = os.getenv('PRTG_PASSHASH', '')
    if passhash:
        params['passhash'] = passhash
    else:
        params['password'] = os.getenv('PRTG_PASSWORD', '')
    return params


def _get(endpoint, extra_params=None):
    params = _auth_params()
    if extra_params:
        params.update(extra_params)
    resp = requests.get(f'{_base_url()}{endpoint}', params=params, verify=False, timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_sensor_summary():
    try:
        sensors = _get('/api/table.json', {'content': 'sensors', 'columns': 'objid,status_raw'}).get('sensors', [])
        return {
            'total':   len(sensors),
            'ok':      sum(1 for s in sensors if s.get('status_raw') in _STATUS_OK),
            'warning': sum(1 for s in sensors if s.get('status_raw') in _STATUS_WARNING),
            'error':   sum(1 for s in sensors if s.get('status_raw') in _STATUS_ERROR),
        }
    except Exception as e:
        logger.warning(f'PRTG get_sensor_summary: {e}')
        return {}


def get_sensors():
    try:
        return _get('/api/table.json', {
            'content': 'sensors',
            'columns': 'objid,name,status,status_raw,message,lastvalue,device,group',
        }).get('sensors', [])
    except Exception as e:
        logger.warning(f'PRTG get_sensors: {e}')
        return []


def get_sensor(sensor_id):
    try:
        sensors = _get('/api/table.json', {
            'content': 'sensors',
            'filter_objid': sensor_id,
            'columns': 'objid,name,status,status_raw,message,lastvalue,device,group',
        }).get('sensors', [])
        return sensors[0] if sensors else {}
    except Exception as e:
        logger.warning(f'PRTG get_sensor({sensor_id}): {e}')
        return {}


def get_device_status(ip):
    try:
        devices = _get('/api/table.json', {
            'content': 'devices',
            'filter_host': ip,
            'columns': 'objid,status_raw',
        }).get('devices', [])
        return bool(devices) and devices[0].get('status_raw') in _STATUS_OK
    except Exception as e:
        logger.warning(f'PRTG get_device_status({ip}): {e}')
        return False


# ── Vue d'ensemble pour le dashboard ─────────────────────────────────────
_STATUS_LABELS = {
    1: 'Inconnu', 2: 'Analyse', 3: 'OK', 4: 'Avertissement', 5: 'Erreur',
    6: 'Pas de sonde', 7: 'Pause (man.)', 8: 'Pause (dép.)', 9: 'Pause (planif.)',
    10: 'Inhabituel', 11: 'Non licencié', 12: 'Pause (tempo.)', 13: 'Erreur (acq.)',
    14: 'Erreur (part.)',
}


def _status_category(raw):
    if raw in _STATUS_OK:
        return 'ok'
    if raw in _STATUS_WARNING or raw == 10:
        return 'warning'
    if raw in _STATUS_ERROR or raw == 13:
        return 'error'
    if raw in (7, 8, 9, 12):
        return 'paused'
    return 'other'


def get_prtg_overview(cache_ttl=None):
    from .cache import cached
    return cached('prtg_overview', cache_ttl, _compute_prtg_overview)


def _compute_prtg_overview():
    """Vue d'ensemble PRTG pour le dashboard : appareils, services, états, taux.

    Renvoie {'available': False} si PRTG est injoignable, pour un repli propre côté UI.
    Utilise les colonnes *_raw (valeurs numériques nettes) plutôt que les colonnes
    HTML renvoyées par l'API.
    """
    try:
        devices_raw = _get('/api/table.json', {
            'content': 'devices', 'count': '1000',
            'columns': 'objid,device,host,group,status,status_raw,upsens,downsens,warnsens,totalsens',
        }).get('devices', [])
        sensors_raw = _get('/api/table.json', {
            'content': 'sensors', 'count': '5000',
            'columns': 'objid,sensor,device,status,status_raw,message,lastvalue',
        }).get('sensors', [])
    except Exception as e:
        logger.warning(f'PRTG get_prtg_overview: {e}')
        return {'available': False}

    devices = []
    dev_ok = dev_warn = dev_down = 0
    for d in devices_raw:
        cat = _status_category(d.get('status_raw'))
        if cat == 'ok':
            dev_ok += 1
        elif cat == 'warning':
            dev_warn += 1
        elif cat == 'error':
            dev_down += 1
        devices.append({
            'name': d.get('device'), 'host': d.get('host'), 'group': d.get('group'),
            'status_raw': d.get('status_raw'),
            'status_label': _STATUS_LABELS.get(d.get('status_raw'), '—'),
            'category': cat,
            'up': d.get('upsens_raw', 0), 'down': d.get('downsens_raw', 0),
            'warn': d.get('warnsens_raw', 0), 'total': d.get('totalsens_raw', 0),
        })

    s_ok = s_warn = s_err = s_other = 0
    problems = []
    for s in sensors_raw:
        cat = _status_category(s.get('status_raw'))
        if cat == 'ok':
            s_ok += 1
        elif cat == 'warning':
            s_warn += 1
        elif cat == 'error':
            s_err += 1
        else:
            s_other += 1
        if cat in ('warning', 'error'):
            problems.append({
                'name': s.get('sensor'), 'device': s.get('device'),
                'status_raw': s.get('status_raw'),
                'status_label': _STATUS_LABELS.get(s.get('status_raw'), '—'),
                'category': cat,
                'message': (s.get('message') or '').strip(),
                'lastvalue': s.get('lastvalue') or '—',
            })

    total_s = len(sensors_raw)
    problems.sort(key=lambda p: 0 if p['category'] == 'error' else 1)

    return {
        'available': True,
        'devices_total': len(devices_raw),
        'devices_ok': dev_ok, 'devices_warning': dev_warn, 'devices_down': dev_down,
        'devices': sorted(devices, key=lambda x: (x['down'] == 0 and x['warn'] == 0, (x['name'] or '').lower())),
        'sensors_total': total_s,
        'sensors_ok': s_ok, 'sensors_warning': s_warn, 'sensors_error': s_err, 'sensors_other': s_other,
        'uptime_rate': round(s_ok / total_s * 100, 1) if total_s else 0.0,
        'problem_sensors': problems[:20],
    }
