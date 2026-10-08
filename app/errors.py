"""Spanish error responses.

FastAPI and Pydantic produce some error messages in English
("Not authenticated", "Field required", "Not Found"...).
These handlers return them in Spanish, keeping the same JSON structure.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Default English HTTP messages -> Spanish.
HTTP_MESSAGES = {
    "Not Found": "Recurso no encontrado",
    "Method Not Allowed": "Método no permitido",
    "Not authenticated": "No autenticado. Inicie sesión con el botón Autorizar.",
    "Unauthorized": "No autorizado",
    "Forbidden": "Sin permisos",
    "Internal Server Error": "Error interno del servidor",
}


def validation_message(error: dict) -> str:
    """Translate one Pydantic validation error into Spanish."""
    error_type = error.get("type", "")
    ctx = error.get("ctx") or {}

    if error_type == "missing":
        return "Campo obligatorio"
    if error_type == "enum":
        return f"Valor no válido. Opciones permitidas: {ctx.get('expected', '')}"
    if error_type in ("int_parsing", "int_type", "int_from_float"):
        return "Debe ser un número entero"
    if error_type in ("float_parsing", "float_type"):
        return "Debe ser un número"
    if error_type in ("string_type",):
        return "Debe ser un texto"
    if error_type in ("bool_parsing", "bool_type"):
        return "Debe ser verdadero o falso"
    if error_type == "string_too_short":
        return f"Debe tener al menos {ctx.get('min_length')} caracteres"
    if error_type == "string_too_long":
        return f"Debe tener máximo {ctx.get('max_length')} caracteres"
    if error_type == "greater_than_equal":
        return f"Debe ser mayor o igual a {ctx.get('ge')}"
    if error_type == "less_than_equal":
        return f"Debe ser menor o igual a {ctx.get('le')}"
    if error_type == "json_invalid":
        return "El JSON está mal escrito (revise comas, comillas y llaves)"
    if error_type in ("list_type",):
        return "Debe ser una lista"
    if error_type in ("model_attributes_type", "dict_type"):
        return "Debe ser un objeto JSON"
    return error.get("msg", "Dato no válido")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def spanish_validation_errors(request: Request, exc: RequestValidationError):
        details = [
            {
                "loc": list(error.get("loc", [])),
                "msg": validation_message(error),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})

    @app.exception_handler(StarletteHTTPException)
    async def spanish_http_errors(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            detail = HTTP_MESSAGES.get(detail, detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )
