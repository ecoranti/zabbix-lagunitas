"""Cliente mínimo de la API JSON-RPC de Zabbix 7.0."""
from __future__ import annotations

import itertools

import requests


class ZabbixError(RuntimeError):
    pass


class ZabbixAPI:
    def __init__(self, url: str, token: str | None = None, user: str | None = None,
                 password: str | None = None, verify_tls: bool = True, timeout: int = 30):
        self.url = url
        self.verify = verify_tls
        self.timeout = timeout
        self._ids = itertools.count(1)
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json-rpc"
        self._logged_in = False
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"
        elif user and password:
            auth = self.call("user.login", {"username": user, "password": password})
            self._session.headers["Authorization"] = f"Bearer {auth}"
            self._logged_in = True
        else:
            raise ZabbixError("Definí ZABBIX_API_TOKEN o ZABBIX_USER/ZABBIX_PASSWORD en .env")

    def call(self, method: str, params=None):
        payload = {"jsonrpc": "2.0", "method": method, "params": params if params is not None else {},
                   "id": next(self._ids)}
        r = self._session.post(self.url, json=payload, timeout=self.timeout, verify=self.verify)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            err = data["error"]
            raise ZabbixError(f"{method}: {err.get('message')} {err.get('data')}")
        return data["result"]

    def version(self) -> str:
        # apiinfo.version debe llamarse sin cabecera de autorización.
        payload = {"jsonrpc": "2.0", "method": "apiinfo.version", "params": {}, "id": next(self._ids)}
        r = requests.post(self.url, json=payload, timeout=self.timeout, verify=self.verify,
                          headers={"Content-Type": "application/json-rpc"})
        r.raise_for_status()
        return r.json()["result"]

    def close(self) -> None:
        if self._logged_in:
            try:
                self.call("user.logout", {})
            except Exception:  # noqa: BLE001 - el cierre de sesión no es crítico
                pass
