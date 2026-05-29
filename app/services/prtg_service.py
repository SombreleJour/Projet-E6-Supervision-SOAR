import os
import urllib3
import requests

from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_STATUS_OK = {3}
_STATUS_WARNING = {4}
_STATUS_ERROR = {5, 14}


def _base_url():
    return os.getenv('PRTG_BASE_URL', 'http://172.16.1.5:443')


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
