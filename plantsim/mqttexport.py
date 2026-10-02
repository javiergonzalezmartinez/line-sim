"""Replay export: Sparkplug-style MQTT messages and an OPC UA-style node list, as files (no broker, no network).

Topic namespace follows the Eclipse Sparkplug specification: namespace/group_id/message_type/edge_node_id[/device_id]
(https://sparkplug.eclipse.org/specification/version/2.2/documents/sparkplug-specification-2.2.pdf and the 3.x asciidoc at
https://github.com/eclipse-sparkplug/sparkplug, read 2 Oct 2026). Message types used: NBIRTH, DBIRTH, DDATA, NDEATH.
Each message carries a `seq` (0-255, wraps) and metrics (name, timestamp in ms, datatype, value) as in the spec's payload description.
HONEST LIMITS: payloads are written as JSON for readability. Real Sparkplug B payloads are Protocol Buffers on the wire, so this
is a readable rendering of the same structure, not a wire-compatible capture. No broker, no QoS, no retained flags, no
will-message handling beyond writing NDEATH at the end, no NCMD/DCMD, no STATE topic of a primary host.
The OPC UA-style node list is a flat description (NodeId, BrowseName, DataType) in a string namespace. It is NOT an OPC UA
information model (no NodeSet2 XML, no references, no type definitions) and no server is implemented.
All names, ids and values come from the synthetic simulation.
"""
from __future__ import annotations

import datetime
import json
from typing import Dict, List

GROUP = "SYNTH_PHARMA_PLANT"
NODE = "LINESIM_EDGE_01"


def _ms(iso: str) -> int:
    return int(datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


def _dtype(el: dict) -> str:
    return "String" if "string_value" in el else "Double"


def _val(el: dict):
    return el["string_value"] if "string_value" in el else el["value"]


def sparkplug_messages(tele: List[dict], group: str = GROUP, node: str = NODE) -> List[dict]:
    """Messages in time order. A device is born (DBIRTH) at its first telemetry event; later events become DDATA."""
    out: List[dict] = []
    seq = 0

    def nxt():
        nonlocal seq
        s = seq
        seq = (seq + 1) % 256
        return s

    if not tele:
        return out
    t0 = _ms(tele[0]["event_time"])
    out.append({"topic": f"spBv1.0/{group}/NBIRTH/{node}", "payload": {"timestamp": t0, "seq": nxt(), "metrics": [{"name": "bdSeq", "timestamp": t0, "datatype": "Int64", "value": 0}]}})
    born = set()
    last = t0
    for e in tele:
        dev = e["equipment_id"]
        ms = _ms(e["event_time"])
        last = max(last, ms)
        metrics = [{"name": s["signal_id"], "timestamp": _ms(s["time"]), "datatype": _dtype(s), "value": _val(s)} for s in e["sensor_elements"]]
        kind = "DDATA" if dev in born else "DBIRTH"
        born.add(dev)
        out.append({"topic": f"spBv1.0/{group}/{kind}/{node}/{dev}", "payload": {"timestamp": ms, "seq": nxt(), "metrics": metrics}})
    out.append({"topic": f"spBv1.0/{group}/NDEATH/{node}", "payload": {"timestamp": last, "metrics": [{"name": "bdSeq", "timestamp": last, "datatype": "Int64", "value": 0}]}})
    return out


def opcua_nodes(tele: List[dict], root: str = "LineSim") -> List[dict]:
    """One variable node per (equipment, signal) seen in the telemetry, with how many data changes were observed."""
    seen: Dict[tuple, dict] = {}
    for e in tele:
        for s in e["sensor_elements"]:
            k = (e["equipment_id"], s["signal_id"])
            n = seen.setdefault(k, {"NodeId": f"ns=2;s={root}/{e['equipment_id']}/{s['signal_id']}", "BrowseName": f"2:{s['signal_id']}",
                                    "DisplayName": s["measurement_type"], "NodeClass": "Variable",
                                    "DataType": "String" if "string_value" in s else "Double", "DataChanges": 0})
            n["DataChanges"] += 1
    return [seen[k] for k in sorted(seen)]


def write_jsonl(rows: List[dict], path: str) -> int:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(rows)


def render_html(msgs: List[dict], nodes: List[dict], limit: int = 14) -> str:
    import html as H
    from collections import Counter
    c = Counter(m["topic"].split("/")[2] for m in msgs)
    chips = "".join(f'<span class=chip>{k}: <b>{v}</b></span>' for k, v in sorted(c.items()))
    mrows = "".join(f"<tr><td>{H.escape(m['topic'])}</td><td>{m['payload']['seq'] if 'seq' in m['payload'] else '-'}</td><td><code>{H.escape(json.dumps(m['payload']['metrics'][:2])[:150])}</code></td></tr>" for m in msgs[:limit])
    nrows = "".join(f"<tr><td>{H.escape(n['NodeId'])}</td><td>{n['DisplayName']}</td><td>{n['DataType']}</td><td>{n['DataChanges']}</td></tr>" for n in nodes[:limit])
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Replay export (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1180px}}table{{border-collapse:collapse;width:100%;margin-bottom:14px}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:3px 8px;border-bottom:1px solid #dde3ea;font-size:12px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}.chip{{background:#e6f4f2;border-radius:10px;padding:2px 10px;margin-right:6px}}code{{font-size:11px}}</style></head><body><h2>Replay export: Sparkplug-style messages and OPC UA-style nodes (synthetic)</h2><div class=n>Synthetic. Topic layout follows the Eclipse Sparkplug namespace (spBv1.0/group/message_type/node/device). Payloads are JSON renderings, not the protobuf wire format; no broker is involved. The node list is flat, not an OPC UA information model.</div><p>{len(msgs)} messages. {chips}</p>
<h3>First {limit} messages</h3><table><tr><th>Topic</th><th>seq</th><th>First metrics</th></tr>{mrows}</table>
<h3>Node list ({len(nodes)} variable nodes, first {limit})</h3><table><tr><th>NodeId</th><th>Display name</th><th>DataType</th><th>Data changes</th></tr>{nrows}</table></body></html>"""
