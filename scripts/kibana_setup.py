"""Crée les data views, visualisations et dashboards Kibana, puis les exporte.

Deux dashboards :
- « Renseignement TASS » sur l'index tass_articles (sortie du NER) ;
- « Monitoring API » sur l'index api_logs (une ligne par requête à l'API).

Les objets sont exportés dans kibana/dashboards.ndjson : on peut les réimporter
à l'identique (Stack Management > Saved objects > Import).

Usage : python scripts/kibana_setup.py   (Kibana sur http://localhost:5601)
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
KIBANA = "http://localhost:5601"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
EXPORT = ROOT / "kibana" / "dashboards.ndjson"

DATA_VIEWS = {
    "dv-tass": ("tass_articles", "date"),
    "dv-api-logs": ("api_logs", "@timestamp"),
}


def put(kind, obj_id, attributes, references):
    r = requests.post(
        f"{KIBANA}/api/saved_objects/{kind}/{obj_id}?overwrite=true",
        headers=HEADERS,
        json={"attributes": attributes, "references": references},
        timeout=30,
    )
    r.raise_for_status()


def data_view(obj_id, index, time_field):
    put("index-pattern", obj_id, {"title": index, "timeFieldName": time_field}, [])


def agg(i, type_, schema, **params):
    return {"id": str(i), "enabled": True, "type": type_, "schema": schema, "params": params}


def terms(i, field, size, schema="segment"):
    return agg(i, "terms", schema, field=field, size=size, order="desc", orderBy="1")


def date_hist(i, field, interval, schema="segment"):
    return agg(i, "date_histogram", schema, field=field, interval=interval,
               min_doc_count=1, extended_bounds={})


def vis(obj_id, title, vis_type, aggs, dv_id, params=None):
    vis_state = {"title": title, "type": vis_type, "aggs": aggs, "params": params or {}}
    put(
        "visualization",
        obj_id,
        {
            "title": title,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "description": "",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {"query": {"query": "", "language": "kuery"}, "filter": [],
                     "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"}
                )
            },
        },
        [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern",
          "id": dv_id}],
    )


def markdown(obj_id, title, text):
    vis_state = {"title": title, "type": "markdown", "aggs": [],
                 "params": {"markdown": text, "fontSize": 12, "openLinksInNewTab": False}}
    put("visualization", obj_id, {
        "title": title, "visState": json.dumps(vis_state), "uiStateJSON": "{}",
        "description": "",
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(
            {"query": {"query": "", "language": "kuery"}, "filter": []})},
    }, [])


def bar(horizontal=False):
    return {"type": "histogram" if not horizontal else "horizontal_bar",
            "addTooltip": True, "addLegend": False, "legendPosition": "right"}


def dashboard(obj_id, title, panels, time_from, time_to):
    panels_json, refs = [], []
    for n, (vis_id, x, y, w, h) in enumerate(panels):
        ref = f"panel_{n}"
        panels_json.append({"panelIndex": str(n), "gridData": {"x": x, "y": y, "w": w, "h": h,
                            "i": str(n)}, "panelRefName": ref, "embeddableConfig": {},
                            "version": "8.15.3", "type": "visualization"})
        refs.append({"name": ref, "type": "visualization", "id": vis_id})
    put("dashboard", obj_id, {
        "title": title,
        "panelsJSON": json.dumps(panels_json),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "timeRestore": True, "timeFrom": time_from, "timeTo": time_to,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(
            {"query": {"query": "", "language": "kuery"}, "filter": []})},
    }, refs)


def count_metric(i="1"):
    return agg(i, "count", "metric")


def build_intel():
    dv = "dv-tass"
    for field, label in (("weapons", "armes (WEAPON)"), ("mil_units", "unités (MIL_UNIT)"),
                         ("mil_orgs", "organisations (MIL_ORG)")):
        vis(f"vis-top-{field}", f"Top 15 {label}", "horizontal_bar",
            [count_metric(), terms(2, field, 15)], dv, bar(horizontal=True))
    vis("vis-articles-month", "Articles par mois", "histogram",
        [count_metric(), date_hist(2, "date", "M")], dv, bar())
    vis("vis-weapons-time", "Top 5 des armes citées chaque année (articles)",
        "line", [count_metric(), date_hist(2, "date", "y"), terms(3, "weapons", 5, "group")], dv,
        {"addLegend": True, "legendPosition": "right", "addTooltip": True})
    vis("vis-cooc", "Co-occurrences armes × organisations (articles)", "table",
        [count_metric(), terms(2, "weapons", 10, "bucket"), terms(3, "mil_orgs", 3, "bucket")],
        dv, {"perPage": 15, "showPartialRows": False, "showTotal": False})
    markdown("vis-intel-note", "Lecture",
             "**Source : TASS, agence de presse d'État russe.** Ces graphiques comptent ce que "
             "la source *affirme*, pas des faits vérifiés. Entités extraites par un modèle NER "
             "spaCy entraîné sur 15 000 phrases pré-annotées par un LLM.")
    dashboard("dash-intel", "Renseignement TASS — entités militaires", [
        ("vis-intel-note", 0, 0, 48, 5),
        ("vis-top-weapons", 0, 5, 16, 18),
        ("vis-top-mil_units", 16, 5, 16, 18),
        ("vis-top-mil_orgs", 32, 5, 16, 18),
        ("vis-articles-month", 0, 23, 24, 15),
        ("vis-weapons-time", 24, 23, 24, 15),
        ("vis-cooc", 0, 38, 48, 16),
    ], "2015-01-01T00:00:00.000Z", "2025-12-31T23:59:59.000Z")


def build_monitoring():
    dv = "dv-api-logs"
    vis("vis-mon-requests", "Requêtes par minute (par code HTTP)", "histogram",
        [count_metric(), date_hist(2, "@timestamp", "m"), terms(3, "status", 5, "group")], dv,
        {"addLegend": True, "legendPosition": "right", "addTooltip": True})
    vis("vis-mon-latency", "Latence de /extract (ms) : moyenne et 95e centile", "line",
        [agg(1, "avg", "metric", field="latency_ms"),
         agg(4, "percentiles", "metric", field="latency_ms", percents=[95]),
         date_hist(2, "@timestamp", "m")], dv,
        {"addLegend": True, "legendPosition": "right", "addTooltip": True})
    vis("vis-mon-status", "Répartition des codes HTTP", "pie",
        [count_metric(), terms(2, "status", 5)], dv,
        {"addLegend": True, "legendPosition": "right", "isDonut": True, "addTooltip": True})
    vis("vis-mon-entities", "Entités prédites par minute (suivi de dérive)", "line",
        [agg(1, "sum", "metric", field="n_weapons", customLabel="WEAPON"),
         agg(3, "sum", "metric", field="n_mil_units", customLabel="MIL_UNIT"),
         agg(4, "sum", "metric", field="n_mil_orgs", customLabel="MIL_ORG"),
         date_hist(2, "@timestamp", "m")], dv,
        {"addLegend": True, "legendPosition": "right", "addTooltip": True})
    vis("vis-mon-kpi", "Indicateurs", "metric",
        [count_metric(), agg(2, "avg", "metric", field="latency_ms", customLabel="latence moy. (ms)"),
         agg(3, "max", "metric", field="latency_ms", customLabel="latence max (ms)")], dv,
        {"addLegend": False, "addTooltip": True, "type": "metric",
         "metric": {"percentageMode": False, "useRanges": False, "colorSchema": "Green to Red",
                    "metricColorMode": "None", "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True}, "invertColors": False,
                    "style": {"bgFill": "#000", "bgColor": False, "labelColor": False,
                              "subText": "", "fontSize": 36}}})
    dashboard("dash-monitoring", "Monitoring API — NER TASS", [
        ("vis-mon-kpi", 0, 0, 24, 10),
        ("vis-mon-status", 24, 0, 24, 10),
        ("vis-mon-requests", 0, 10, 24, 16),
        ("vis-mon-latency", 24, 10, 24, 16),
        ("vis-mon-entities", 0, 26, 48, 16),
    ], *traffic_window())


def traffic_window():
    """Période couverte par api_logs, élargie d'une minute de chaque côté."""
    r = requests.post("http://localhost:9200/api_logs/_search", timeout=30, json={
        "size": 0, "aggs": {"first": {"min": {"field": "@timestamp"}},
                            "last": {"max": {"field": "@timestamp"}}}})
    r.raise_for_status()
    aggs = r.json()["aggregations"]
    if aggs["first"]["value"] is None:
        return "now-1h", "now"
    pad = 60_000
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    first = datetime.fromtimestamp((aggs["first"]["value"] - pad) / 1000, UTC)
    last = datetime.fromtimestamp((aggs["last"]["value"] + pad) / 1000, UTC)
    return first.strftime(fmt), last.strftime(fmt)


def export():
    r = requests.post(f"{KIBANA}/api/saved_objects/_export", headers=HEADERS, timeout=60,
                      json={"objects": [{"type": "dashboard", "id": "dash-intel"},
                                        {"type": "dashboard", "id": "dash-monitoring"}],
                            "includeReferencesDeep": True})
    r.raise_for_status()
    EXPORT.parent.mkdir(exist_ok=True)
    EXPORT.write_text(r.text, encoding="utf-8")
    print(f"{len(r.text.splitlines())} objets exportés -> {EXPORT}")


def main():
    for obj_id, (index, time_field) in DATA_VIEWS.items():
        data_view(obj_id, index, time_field)
    build_intel()
    build_monitoring()
    export()


if __name__ == "__main__":
    main()
