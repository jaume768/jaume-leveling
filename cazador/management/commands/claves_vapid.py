"""Genera el par de claves VAPID para las notificaciones. Una sola vez:

    python manage.py claves_vapid

Copia las dos lineas al .env del servidor. Si se cambian, los moviles
suscritos tienen que volver a activar las notificaciones.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Genera las claves VAPID (Web Push) para el .env."

    def handle(self, *args, **opciones):
        privada = ec.generate_private_key(ec.SECP256R1())
        der = privada.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        publica = privada.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.stdout.write(f"VAPID_PUBLIC_KEY={_b64(publica)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={_b64(der)}")
