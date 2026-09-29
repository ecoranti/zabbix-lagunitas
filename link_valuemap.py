import requests

URL = "http://localhost:8090/api_jsonrpc.php"
HEADERS = {"Content-Type": "application/json-rpc"}

def call(method, params, auth=None, rid=1):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": rid}
    if auth:
        payload["auth"] = auth
    r = requests.post(URL, json=payload, headers=HEADERS).json()
    if "error" in r:
        raise Exception(r["error"])
    return r["result"]

# login
auth = call("user.login", {"username": "Admin", "password": "zabbix"})

VALUEMAP_NAME = "Estado disponibilidad"

# get every host, with its value maps
hosts = call("host.get", {
    "output": ["hostid", "host", "name"],
    "selectValueMaps": ["valuemapid", "name"]
}, auth)

updated = []
skipped = []

for h in hosts:
    hostid = h["hostid"]
    hostname = h["host"]

    vmap = next((vm for vm in h["valuemaps"] if vm["name"] == VALUEMAP_NAME), None)
    if not vmap:
        skipped.append((hostname, "sin value map 'Estado disponibilidad'"))
        continue

    valuemapid = vmap["valuemapid"]

    # find the icmpping item on this host (the 0/1 status item, not icmppingsec)
    items = call("item.get", {
        "output": ["itemid", "key_", "valuemapid"],
        "hostids": hostid,
        "search": {"key_": "icmpping"}
    }, auth)

    icmpping_item = next((i for i in items if i["key_"] == "icmpping"), None)
    if not icmpping_item:
        skipped.append((hostname, "no tiene item icmpping"))
        continue

    if icmpping_item["valuemapid"] == valuemapid:
        skipped.append((hostname, "ya estaba linkeado"))
        continue

    call("item.update", {
        "itemid": icmpping_item["itemid"],
        "valuemapid": valuemapid
    }, auth)
    updated.append(hostname)

print(f"\nActualizados ({len(updated)}):")
for u in updated:
    print(f"  - {u}")

print(f"\nOmitidos ({len(skipped)}):")
for name, reason in skipped:
    print(f"  - {name}: {reason}")
