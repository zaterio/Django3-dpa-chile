import requests
import ssl
import socket
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from d3_dpa_chile.models import Region, Provincia, Comuna
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://apis.digital.gob.cl/dpa/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
}


class Command(BaseCommand):
    help = "Populate Political-Administrative Division of Chile"

    def check_certificate_validity(self):
        """
        Verifica la vigencia del certificado SSL de BASE_URL.
        Si está vencido, consulta al usuario si desea continuar.
        """
        try:
            hostname = (
                BASE_URL.replace("https://", "").replace("http://", "").rstrip("/")
            )

            self.stdout.write(self.style.WARNING("Verificando certificado SSL..."))

            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

            # Extraer fecha de vencimiento del certificado
            not_after_str = cert.get("notAfter")
            not_after = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")

            current_date = datetime.now()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Certificado válido hasta: {not_after.strftime('%d/%m/%Y')}"
                )
            )

            if current_date > not_after:
                self.stdout.write(
                    self.style.ERROR(
                        f"⚠️  El certificado SSL está VENCIDO desde {not_after.strftime('%d/%m/%Y')}"
                    )
                )
                response = (
                    input("¿Deseas continuar con el certificado vencido? (s/n): ")
                    .lower()
                    .strip()
                )
                if response != "s":
                    raise CommandError("Ejecución cancelada por el usuario.")
                self.stdout.write(
                    self.style.WARNING("Continuando con certificado vencido...")
                )

            return True

        except socket.timeout:
            self.stdout.write(
                self.style.WARNING("Timeout al conectarse al servidor SSL")
            )
            return False
        except ssl.SSLError as e:
            # Si el certificado es inválido o vencido, ssl lanza una excepción
            self.stdout.write(self.style.ERROR(f"Error SSL detectado: {e}"))
            response = (
                input("¿Deseas continuar sin validar el certificado? (s/n): ")
                .lower()
                .strip()
            )
            if response != "s":
                raise CommandError("Ejecución cancelada por el usuario.")
            self.stdout.write(
                self.style.WARNING("Continuando sin validación de certificado SSL...")
            )
            return True
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"No se pudo verificar el certificado: {e}")
            )
            return True

    def handle(self, *args, **options):
        if Region.objects.all().exists():
            self.stdout.write(
                self.style.WARNING("La base de datos ya ha sido poblada anteriormente.")
            )
            return

        # Verificar certificado SSL antes de hacer solicitudes
        self.check_certificate_validity()

        try:
            self.stdout.write(
                self.style.WARNING("Descargando la información de la API...")
            )
            response = requests.get(
                f"{BASE_URL}regiones", headers=HEADERS, verify=False
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise CommandError(f"Failed to retrieve regions - Exception: {e}")

        for region in data:
            try:
                self.stdout.write(self.style.SUCCESS(f"Region: {region['nombre']}"))

                region_fields = {
                    "tipo": region["tipo"],
                    "nombre": region["nombre"],
                    "lat": str(region["lat"]),
                    "lng": str(region["lng"]),
                    "url": region["url"],
                }

                region_obj, region_created = Region.objects.update_or_create(
                    codigo=region["codigo"], defaults=region_fields
                )

                self.create_provincias(region_obj)
            except Exception as e:
                raise CommandError(f"Fail to populate region - Exception: {e}")

        self.stdout.write(self.style.SUCCESS("Successfully populated DPA Chile"))

    def create_provincias(self, region):
        try:
            response = requests.get(
                f"{BASE_URL}regiones/{region.codigo}/provincias",
                headers=HEADERS,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise CommandError(f"Failed to retrieve provincia - Exception: {e}")

        for provincia in data:
            try:
                self.stdout.write(
                    self.style.SUCCESS(f"Provincia: {provincia['nombre']}")
                )

                provincia_fields = {
                    "tipo": provincia["tipo"],
                    "nombre": provincia["nombre"],
                    "lat": str(provincia["lat"]),
                    "lng": str(provincia["lng"]),
                    "url": provincia["url"],
                    "region": region,
                }

                provincia_obj, provincia_created = Provincia.objects.update_or_create(
                    codigo=provincia["codigo"], defaults=provincia_fields
                )

                self.create_comunas(provincia_obj)
            except Exception as e:
                raise CommandError(f"Fail to populate provincia - Exception: {e}")

    def create_comunas(self, provincia):
        try:
            response = requests.get(
                f"{BASE_URL}regiones/{provincia.region.codigo}/provincias/{provincia.codigo}/comunas",
                headers=HEADERS,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise CommandError(f"Failed to retrieve comunas - Exception: {e}")

        for comuna in data:
            try:
                self.stdout.write(self.style.SUCCESS(f"Comuna: {comuna['nombre']}"))

                comuna_fields = {
                    "tipo": comuna["tipo"],
                    "nombre": comuna["nombre"],
                    "lat": str(comuna["lat"]),
                    "lng": str(comuna["lng"]),
                    "url": comuna["url"],
                    "region": provincia.region,
                    "provincia": provincia,
                }

                comuna_obj, comuna_created = Comuna.objects.update_or_create(
                    codigo=comuna["codigo"], defaults=comuna_fields
                )
            except Exception as e:
                raise CommandError(f"Fail to populate comunas - Exception: {e}")
