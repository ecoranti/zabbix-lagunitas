"""Pruebas de la lógica de descubrimiento (sin Zabbix):  .venv/bin/python -m pytest tests"""
import pytest

from lagunitas import descubrimiento as d
from lagunitas.config import ROOT, load_inventory


def equipo(ip, **servicios):
    return d.clasificar({"ip": ip, "dns": "", "servicios": {"icmp": "", **servicios}, "visto": 0})


def test_rangos():
    assert len(d.direcciones("10.50.0.0/24")) == 254
    assert [str(x) for x in d.direcciones("10.50.0.1-3")] == ["10.50.0.1", "10.50.0.2", "10.50.0.3"]
    assert len(d.direcciones("10.50.0.5, 10.50.0.10-11")) == 3
    assert len(d.direcciones("10.50.0.0/22")) == 1022
    for malo in ("10.50.0.0/16", "10.50.0.9-3", "10.50.0.1-10.50.0.5", "10.50.0.1/32", "hola", ""):
        with pytest.raises(ValueError):
            d.direcciones(malo)


def test_clasificacion_lab():
    m = equipo("10.50.0.10", descr="RouterOS RB750Gr3", objeto="1.3.6.1.4.1.14988.1", nombre="Gateway Mikrotik")
    assert (m["tipo"], m["perfiles"], m["funcion"], m["modelo"]) == (
        "mikrotik", ["icmp", "mikrotik_snmp"], "router", "Mikrotik RB750Gr3")
    assert m["host_sugerido"] == "Gateway_Mikrotik"
    a = equipo("10.50.0.11", descr="Linux 2.6.32 #1 mips", objeto=".1.3.6.1.4.1.10002.1", nombre="Torre")
    assert (a["tipo"], a["perfiles"], a["funcion"]) == ("airmax", ["icmp", "airos_snmp"], None)
    assert equipo("10.50.0.40", https="")["tipo"] == "web"
    p = equipo("10.50.0.41")
    assert (p["tipo"], p["host_sugerido"]) == ("ping", "Equipo_10_50_0_41")


def test_comparar_y_propuesta():
    inv = load_inventory(ROOT / "config" / "inventory.lab.yaml")
    conocido = next(x for x in inv["todos"] if "airos_snmp" not in x["perfiles"] and x["estado"] == "operativo")
    eqs = [equipo(str(conocido["ip"]), descr="Linux", objeto="1.3.6.1.4.1.41112.1"),
           equipo("10.50.0.250", descr="RouterOS hAP", nombre=conocido["host"])]
    c = d.comparar(eqs, inv, "10.50.0.0/24")
    assert [e["ip"] for e in c["nuevos"]] == ["10.50.0.250"]
    assert c["conocidos"][0]["faltan_perfiles"] == ["airos_snmp"]
    assert conocido["ip"] not in [x["ip"] for x in c["ausentes"]]
    y = d.propuesta_yaml(c["nuevos"], set(inv["por_host"]))
    assert f"host: {conocido['host']}_2" in y  # no repite un nombre del inventario
    assert "funcion: router" in y and "padre: COMPLETAR" in y


def test_yaml_valido_con_textos_raros():
    import yaml
    e = equipo("10.50.0.99", descr="RouterOS hAP: lite #2", nombre="Casa: Kika #1")
    y = d.propuesta_yaml([e])
    datos = yaml.safe_load(y)
    assert datos[0]["nombre"] == "Casa: Kika #1" and datos[0]["modelo"] == "Mikrotik hAP: lite #2"


class ApiFalsa:
    """Responde como Zabbix 7.0 a drule.get / dhost.get con un escaneo del LAB."""

    def __init__(self):
        self.llamadas = []

    def call(self, metodo, params=None):
        self.llamadas.append((metodo, params))
        if metodo == "drule.get":
            return [{"druleid": "7", "iprange": "10.50.0.0/24", "dchecks": [
                {"dcheckid": "1", "type": "12", "key_": ""},
                {"dcheckid": "2", "type": "11", "key_": d.OID_DESCR},
                {"dcheckid": "3", "type": "11", "key_": d.OID_OBJETO},
                {"dcheckid": "4", "type": "11", "key_": d.OID_NOMBRE},
                {"dcheckid": "5", "type": "14", "key_": ""}]}]
        if metodo == "dhost.get":
            s = lambda c, ip, v="", st="0": {"dcheckid": c, "ip": ip, "dns": ip, "value": v, "status": st,
                                            "lastup": "100"}
            return [{"dhostid": "1", "dservices": [s("1", "10.50.0.10"), s("2", "10.50.0.10", "RouterOS RB750Gr3"),
                                                   s("4", "10.50.0.10", "Gateway Mikrotik"), s("5", "10.50.0.10", st="1")]},
                    {"dhostid": "2", "dservices": [s("1", "10.50.0.9"), s("5", "10.50.0.9")]}]
        if metodo == "drule.create":
            return {"druleids": ["8"]}
        return []


def test_resultados_desde_api():
    res = d.resultados(ApiFalsa())
    assert [(e["ip"], e["tipo"]) for e in res] == [("10.50.0.9", "web"), ("10.50.0.10", "mikrotik")]
    assert res[0]["host_sugerido"] == "Equipo_10_50_0_9"  # el DNS igual a la IP no se usa como nombre


def test_iniciar_recrea_la_regla():
    api = ApiFalsa()
    assert d.iniciar(api, "10.50.0.0/24") == "8"
    metodos = [m for m, _ in api.llamadas]
    assert metodos == ["drule.get", "drule.delete", "drule.create"]
    crear = api.llamadas[-1][1]
    assert crear["iprange"] == "10.50.0.0/24" and len(crear["dchecks"]) == 5
    assert crear["dchecks"][1]["snmp_community"] == "{$SNMP_COMMUNITY}"
