"""
Servicio de generación de códigos QR para el check-in de turnos.

Genera el QR en memoria (sin tocar disco) y retorna una data URI base64
lista para ser embebida en <img src="..."> en HTML/email.
"""
import base64
import io

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer


def generate_checkin_qr(token: str) -> str:
    """Genera un QR PNG a partir del token de check-in.

    El QR codifica solo el token (no una URL) para evitar dependencias
    de hostname o IPs de red local.

    Returns:
        Data URI base64: "data:image/png;base64,<png_bytes_b64>"
    """
    qr = qrcode.QRCode(
        version=None,          # auto-selecciona el tamaño mínimo necesario
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # ~15% de corrección
        box_size=8,
        border=3,
    )
    qr.add_data(token)
    qr.make(fit=True)

    # Usamos la imagen estándar con módulos cuadrados para 100% de compatibilidad
    # con bibliotecas de escaneo JS como html5-qrcode.
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    b64 = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"
