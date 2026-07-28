import json
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from d3_dpa_chile.models import Comuna, Provincia, Region

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "dpa_chile.json"


class Command(BaseCommand):
    help = "Populate Political-Administrative Division of Chile"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            metavar="URL",
            help=(
                "URL de un JSON con el mismo esquema que el archivo de datos "
                "empaquetado (fuente oficial: Geoportal IDE Chile / SUBDERE). "
                "Por defecto se usan los datos incluidos en el paquete."
            ),
        )

    def load_data(self, source):
        if source:
            self.stdout.write(self.style.WARNING(f"Descargando datos desde {source}..."))
            try:
                response = requests.get(source, timeout=60)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                raise CommandError(f"Failed to retrieve data - Exception: {e}")
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise CommandError(f"No se pudo leer {DATA_FILE} - Exception: {e}")

    def handle(self, *args, **options):
        if Region.objects.all().exists():
            self.stdout.write(
                self.style.WARNING("La base de datos ya ha sido poblada anteriormente.")
            )
            return

        data = self.load_data(options["source"])
        if data.get("fuente"):
            self.stdout.write(self.style.WARNING(f"Fuente: {data['fuente']}"))

        for region in data["regiones"]:
            try:
                self.stdout.write(self.style.SUCCESS(f"Region: {region['nombre']}"))

                region_fields = {
                    "tipo": "region",
                    "nombre": region["nombre"],
                    "lat": str(region["lat"]),
                    "lng": str(region["lng"]),
                    "url": "",
                }

                region_obj, region_created = Region.objects.update_or_create(
                    codigo=region["codigo"], defaults=region_fields
                )

                self.create_provincias(region_obj, region["provincias"])
            except Exception as e:
                raise CommandError(f"Fail to populate region - Exception: {e}")

        self.stdout.write(self.style.SUCCESS("Successfully populated DPA Chile"))

    def create_provincias(self, region, provincias):
        for provincia in provincias:
            try:
                self.stdout.write(
                    self.style.SUCCESS(f"Provincia: {provincia['nombre']}")
                )

                provincia_fields = {
                    "tipo": "provincia",
                    "nombre": provincia["nombre"],
                    "lat": str(provincia["lat"]),
                    "lng": str(provincia["lng"]),
                    "url": "",
                    "region": region,
                }

                provincia_obj, provincia_created = Provincia.objects.update_or_create(
                    codigo=provincia["codigo"], defaults=provincia_fields
                )

                self.create_comunas(region, provincia_obj, provincia["comunas"])
            except Exception as e:
                raise CommandError(f"Fail to populate provincia - Exception: {e}")

    def create_comunas(self, region, provincia, comunas):
        for comuna in comunas:
            try:
                self.stdout.write(self.style.SUCCESS(f"Comuna: {comuna['nombre']}"))

                comuna_fields = {
                    "tipo": "comuna",
                    "nombre": comuna["nombre"],
                    "lat": str(comuna["lat"]),
                    "lng": str(comuna["lng"]),
                    "url": "",
                    "region": region,
                    "provincia": provincia,
                }

                comuna_obj, comuna_created = Comuna.objects.update_or_create(
                    codigo=comuna["codigo"], defaults=comuna_fields
                )
            except Exception as e:
                raise CommandError(f"Fail to populate comunas - Exception: {e}")
