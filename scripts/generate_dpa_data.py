#!/usr/bin/env python3
"""
Genera d3_dpa_chile/data/dpa_chile.json desde la fuente oficial del
Gobierno de Chile: Geoportal IDE Chile / SUBDERE, dataset
"División Política Administrativa 2023".

Uso:
    pip install pyshp requests
    python scripts/generate_dpa_data.py                 # descarga el zip oficial
    python scripts/generate_dpa_data.py --zip ruta.zip  # usa un zip local
    python scripts/generate_dpa_data.py --url <URL>     # otra URL de descarga

Requiere: pyshp (https://pypi.org/project/pyshp/) y requests.
Este script es solo para mantenedores; NO se incluye en el paquete.
"""

import argparse
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

DEFAULT_URL = (
    "https://geoportal.cl/geoportal/catalog/download/"
    "912598ad-ac92-35f6-8045-098f214bd9c2"
)
FUENTE = "IDE Chile / SUBDERE - División Política Administrativa 2023 (geoportal.cl)"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "d3_dpa_chile" / "data" / "dpa_chile.json"

try:
    import shapefile  # pyshp
except ImportError:
    sys.exit("Falta pyshp. Instala con: pip install pyshp")


def ring_area_centroid(points):
    """Área con signo y centroide de un anillo de polígono (fórmula del área de Gauss)."""
    a = cx = cy = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i][0], points[i][1]
        x2, y2 = points[(i + 1) % n][0], points[(i + 1) % n][1]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a *= 0.5
    if a == 0:
        return 0.0, None
    return a, (cx / (6 * a), cy / (6 * a))


def shape_centroid(shape):
    """Centroide de la parte de mayor área absoluta del shape.

    Las geometrías están en GCS SIRGAS-Chile (grados, compatible WGS84),
    por lo que x = longitud, y = latitud directamente.
    """
    points = shape.points
    best_area, best_centroid = 0.0, None
    parts = list(shape.parts) + [len(points)]
    for i in range(len(parts) - 1):
        ring = points[parts[i] : parts[i + 1]]
        area, centroid = ring_area_centroid(ring)
        if centroid and abs(area) > best_area:
            best_area, best_centroid = abs(area), centroid
    if best_centroid is None:
        raise ValueError("Shape sin geometría utilizable")
    lng, lat = best_centroid
    return round(lat, 6), round(lng, 6)


def read_layer(zf, prefix, fields):
    """Lee un layer (shp+dbf) desde el zip y retorna lista de dicts con
    los campos pedidos más lat/lng del centroide."""
    shp = io.BytesIO(zf.read(f"{prefix}.shp"))
    dbf = io.BytesIO(zf.read(f"{prefix}.dbf"))
    reader = shapefile.Reader(shp=shp, dbf=dbf, encoding="utf8")
    field_names = [f[0] for f in reader.fields[1:]]  # salta DeletionFlag
    rows = []
    for sr in reader.iterShapeRecords():
        full = dict(zip(field_names, sr.record))
        rec = {name: str(full[name]).strip() for name in fields}
        lat, lng = shape_centroid(sr.shape)
        rec["lat"] = lat
        rec["lng"] = lng
        rows.append(rec)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", dest="zip_path", help="Ruta a un zip ya descargado")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL de descarga del zip oficial")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta del JSON de salida")
    args = parser.parse_args()

    if args.zip_path:
        zip_path = Path(args.zip_path)
    else:
        import requests

        print(f"Descargando {args.url} (~310 MB)...")
        resp = requests.get(args.url, timeout=600)
        resp.raise_for_status()
        zip_path = Path("/tmp/dpa_oficial.zip")
        zip_path.write_bytes(resp.content)
        print(f"Guardado temporal en {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        regiones = read_layer(zf, "REGIONES/REGIONES_v1", ["CUT_REG", "REGION"])
        provincias = read_layer(
            zf, "PROVINCIAS/PROVINCIAS_v1", ["CUT_REG", "CUT_PROV", "PROVINCIA"]
        )
        comunas = read_layer(
            zf, "COMUNAS/COMUNAS_v1", ["CUT_PROV", "CUT_COM", "COMUNA"]
        )

    comunas_por_prov = {}
    for c in comunas:
        comunas_por_prov.setdefault(c["CUT_PROV"], []).append(
            {"codigo": c["CUT_COM"], "nombre": c["COMUNA"], "lat": c["lat"], "lng": c["lng"]}
        )

    provs_por_reg = {}
    for p in provincias:
        provs_por_reg.setdefault(p["CUT_REG"], []).append(
            {
                "codigo": p["CUT_PROV"],
                "nombre": p["PROVINCIA"],
                "lat": p["lat"],
                "lng": p["lng"],
                "comunas": sorted(
                    comunas_por_prov.get(p["CUT_PROV"], []), key=lambda c: c["codigo"]
                ),
            }
        )

    data = {
        "fuente": FUENTE,
        "url_fuente": DEFAULT_URL,
        "generado": date.today().isoformat(),
        "regiones": [
            {
                "codigo": r["CUT_REG"],
                "nombre": r["REGION"],
                "lat": r["lat"],
                "lng": r["lng"],
                "provincias": sorted(
                    provs_por_reg.get(r["CUT_REG"], []), key=lambda p: p["codigo"]
                ),
            }
            for r in sorted(regiones, key=lambda r: r["CUT_REG"])
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")

    n_prov = sum(len(r["provincias"]) for r in data["regiones"])
    n_com = sum(len(p["comunas"]) for r in data["regiones"] for p in r["provincias"])
    print(f"OK: {out}")
    print(f"Regiones: {len(data['regiones'])} | Provincias: {n_prov} | Comunas: {n_com}")


if __name__ == "__main__":
    main()
