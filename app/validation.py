"""Validation rules shared by every request.

Each rule has a regular expression, a length limit and the Spanish message
the user sees when the value does not match. The frontend uses the same rules.
"""

from typing import Annotated

from pydantic import Field

LETTERS = "A-Za-zÁÉÍÓÚáéíóúÑñÜü"

# Regular expressions
NAME_RE = rf"^[{LETTERS}]+(?:[ '-][{LETTERS}]+)*$"
EMAIL_RE = r"^[a-z0-9._%+-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})*\.[a-z]{2,10}$"
PHONE_RE = r"^3[0-9]{9}$"
DOCUMENT_RE = r"^[0-9]{6,10}$"
PASSWORD_DIGEST_RE = r"^[a-f0-9]{64}$"
PLATE_RE = r"^[A-Z]{3}[0-9]{3}$"
LICENSE_RE = r"^[0-9]{6,12}$"
QR_RE = r"^RS-[A-Z0-9]{4,8}(?:-[A-Z0-9]{4})?$"
CODE_RE = r"^[a-z][a-z_]{1,29}$"
DANE_RE = r"^[0-9]{12}$"
LABEL_RE = rf"^[{LETTERS}0-9]+(?:[ .,#°º()'/-]+[{LETTERS}0-9]+)*[.)]?$"
FREE_TEXT_RE = r"^[^<>{}$\\]+$"
UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
WEATHER_CODES_RE = r"^[0-9]{1,2}(?:,[0-9]{1,2}){0,19}$"

# Reusable field types
PersonName = Annotated[str, Field(min_length=2, max_length=50, pattern=NAME_RE)]
Email = Annotated[str, Field(min_length=6, max_length=120, pattern=EMAIL_RE)]
Phone = Annotated[str, Field(min_length=10, max_length=10, pattern=PHONE_RE)]
DocumentNumber = Annotated[str, Field(min_length=6, max_length=10, pattern=DOCUMENT_RE)]
PasswordDigest = Annotated[
    str,
    Field(
        min_length=64,
        max_length=64,
        pattern=PASSWORD_DIGEST_RE,
        description="Hash SHA-256 de la contraseña, calculado en el navegador. La contraseña real nunca viaja.",
    ),
]
Plate = Annotated[str, Field(min_length=6, max_length=6, pattern=PLATE_RE)]
LicenseNumber = Annotated[str, Field(min_length=6, max_length=12, pattern=LICENSE_RE)]
QrCode = Annotated[str, Field(min_length=7, max_length=20, pattern=QR_RE)]
CatalogCode = Annotated[str, Field(min_length=2, max_length=30, pattern=CODE_RE)]
CatalogName = Annotated[str, Field(min_length=2, max_length=60, pattern=LABEL_RE)]
Label = Annotated[str, Field(min_length=3, max_length=80, pattern=LABEL_RE)]
ShortText = Annotated[str, Field(min_length=3, max_length=200, pattern=FREE_TEXT_RE)]
LongText = Annotated[str, Field(min_length=10, max_length=500, pattern=FREE_TEXT_RE)]
DaneCode = Annotated[str, Field(min_length=12, max_length=12, pattern=DANE_RE)]
ClientEventId = Annotated[str, Field(min_length=36, max_length=36, pattern=UUID_RE)]
WeatherCodes = Annotated[str, Field(max_length=120, pattern=WEATHER_CODES_RE)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Id = Annotated[int, Field(ge=1, le=2_147_483_647)]
DelayMinutes = Annotated[int, Field(ge=0, le=120)]

# Spanish message per field when the regular expression does not match.
FIELD_HINTS = {
    "first_name": "Solo letras y espacios, de 2 a 50 caracteres.",
    "last_name": "Solo letras y espacios, de 2 a 50 caracteres.",
    "email": "Escriba un correo válido, por ejemplo nombre@dominio.com.",
    "username": "Escriba un correo válido, por ejemplo nombre@dominio.com.",
    "phone": "Celular de 10 dígitos que empiece por 3.",
    "document_number": "Solo números, de 6 a 10 dígitos.",
    "password": "La contraseña debe llegar cifrada (hash SHA-256 de 64 caracteres).",
    "plate": "Placa de 3 letras mayúsculas y 3 números, por ejemplo ABC123.",
    "license_number": "Solo números, de 6 a 12 dígitos.",
    "qr_code": "Código QR inválido. Formato esperado: RS-XXXX o RS-XXXX-XXXX.",
    "code": "Solo letras minúsculas y guion bajo, de 2 a 30 caracteres.",
    "name": "Use solo letras, números y signos básicos.",
    "description": "No use los caracteres < > { } $ \\.",
    "dane_code": "El código DANE tiene 12 dígitos.",
    "client_event_id": "Identificador de evento inválido.",
    "weather_codes": "Números de 0 a 99 separados por comas.",
}
