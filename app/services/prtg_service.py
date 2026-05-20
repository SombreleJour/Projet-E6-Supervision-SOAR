import os
import urllib3
import requests

from app.utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# PRTG status_raw codes: 3=Up, 4=Warning, 5=Down, 14=Unknown
_STATUS_OK = {3}
_STATUS_WARNING = {4}
_STATUS_ERROR = {5, 14}


def _base_url():
    return os.getenv('PRTG_BASE_URL', 'http://172.16.1.5:443')


def _auth_params():
    params = {
        'username': os.getenv('PRTG_USERNAME', 'prtgadmin'),
        'output': 'json',
    }
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
    resp = requests.get(
        f'{_base_url()}{endpoint}',
        params=params,
        verify=False,
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def get_sensor_summary():
    """Retourne un dict résumé : total / ok / warning / error."""
    try:
        data = _get('/api/table.json', {
            'content': 'sensors',
            'columns': 'objid,name,status,status_raw',
        })
        sensors = data.get('sensors', [])
        return {
            'total': len(sensors),
            'ok': sum(1 for s in sensors if s.get('status_raw') in _STATUS_OK),
            'warning': sum(1 for s in sensors if s.get('status_raw') in _STATUS_WARNING),
            'error': sum(1 for s in sensors if s.get('status_raw') in _STATUS_ERROR),
        }
    except Exception as e:
        logger.warning(f'PRTG get_sensor_summary failed: {e}')
        return {}


def get_sensors():
    """Retourne la liste complète des capteurs PRTG."""
    try:
        data = _get('/api/table.json', {
            'content': 'sensors',
            'columns': 'objid,name,status,status_raw,message,lastvalue,device,group',
        })
        return data.get('sensors', [])
    except Exception as e:
        logger.warning(f'PRTG get_sensors failed: {e}')
        return []


def get_sensor(sensor_id):
    """Retourne le détail d'un capteur PRTG par son objid."""
    try:
        data = _get('/api/table.json', {
            'content': 'sensors',
            'filter_objid': sensor_id,
            'columns': 'objid,name,status,status_raw,message,lastvalue,device,group',
        })
        sensors = data.get('sensors', [])
        return sensors[0] if sensors else {}
    except Exception as e:
        logger.warning(f'PRTG get_sensor({sensor_id}) failed: {e}')
        return {}


def get_device_status(ip):
    """Retourne True si le device avec cette IP est en statut Up dans PRTG."""
    try:
        data = _get('/api/table.json', {
            'content': 'devices',
            'filter_host': ip,
            'columns': 'objid,name,host,status,status_raw',
        })
        devices = data.get('devices', [])
        if not devices:
            return False
        return devices[0].get('status_raw') in _STATUS_OK
    except Exception as e:
        logger.warning(f'PRTG get_device_status({ip}) failed: {e}')
        return False
