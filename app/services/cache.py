import time
import threading

_store = {}
_lock = threading.Lock()


def cached(key, ttl, producer):
    """Renvoie une valeur mise en cache (TTL en secondes) ou la (re)produit.

    Cache mémoire par worker gunicorn — suffisant pour éviter de marteler les API
    externes (PRTG/Wazuh) quand plusieurs onglets/clients pollent à intervalle court.
    ttl falsy/<=0 => pas de cache (toujours recalculé).
    """
    if not ttl or ttl <= 0:
        return producer()
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = producer()
    with _lock:
        _store[key] = (time.monotonic(), value)
    return value
