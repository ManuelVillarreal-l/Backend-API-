"""Swagger UI page translated to Spanish.

Swagger UI has no built-in language option, so this module serves the normal
Swagger page plus a small script that replaces its English labels
(buttons, titles, dialogs) with Spanish text as the page is drawn.
"""

import json

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import HTMLResponse

DOCS_URL = "/docs"
OAUTH2_REDIRECT_URL = "/docs/oauth2-redirect"

# English label shown by Swagger UI -> Spanish label shown to the user.
SPANISH_LABELS = {
    # Operation panel
    "Try it out": "Probar",
    "Cancel": "Cancelar",
    "Execute": "Ejecutar",
    "Clear": "Limpiar",
    "Parameters": "Parámetros",
    "No parameters": "Sin parámetros",
    "Name": "Nombre",
    "Description": "Descripción",
    "Request body": "Cuerpo de la solicitud",
    "required": "obligatorio",
    "Send empty value": "Enviar valor vacío",
    "Example Value": "Valor de ejemplo",
    "Edit Value": "Editar valor",
    "Schema": "Esquema",
    "Schemas": "Esquemas",
    "Media type": "Tipo de contenido",
    "Controls Accept header.": "Controla el encabezado Accept.",
    "Loading...": "Cargando...",
    # Responses
    "Responses": "Respuestas",
    "Request URL": "URL de la solicitud",
    "Server response": "Respuesta del servidor",
    "Code": "Código",
    "Details": "Detalles",
    "Links": "Enlaces",
    "No links": "Sin enlaces",
    "Response body": "Cuerpo de la respuesta",
    "Response headers": "Encabezados de la respuesta",
    "Download": "Descargar",
    "Undocumented": "No documentado",
    "Successful Response": "Respuesta exitosa",
    "Validation Error": "Error de validación",
    "Error: Bad Request": "Error: Solicitud incorrecta",
    "Error: Unauthorized": "Error: No autorizado",
    "Error: Forbidden": "Error: Sin permisos",
    "Error: Not Found": "Error: No encontrado",
    "Error: Conflict": "Error: Conflicto",
    "Error: Unprocessable Content": "Error: Datos no válidos",
    "Error: Unprocessable Entity": "Error: Datos no válidos",
    "Error: Internal Server Error": "Error: Error interno del servidor",
    "Failed to fetch.": "No se pudo conectar con el servidor.",
    # Authorization dialog
    "Authorize": "Autorizar",
    "Available authorizations": "Autorizaciones disponibles",
    "Authorized": "Autorizado",
    "Logout": "Cerrar sesión",
    "Close": "Cerrar",
    "Auth Error": "Error de autenticación",
    "Token URL:": "URL del token:",
    "Flow:": "Flujo:",
    "username:": "usuario (correo):",
    "password:": "contraseña:",
    "Client credentials location:": "Ubicación de las credenciales del cliente:",
    "Authorization header": "Encabezado Authorization",
    "client_id:": "client_id (dejar vacío):",
    "client_secret:": "client_secret (dejar vacío):",
    "Scopes are used to grant an application different levels of access to data "
    "on behalf of the end user. Each API may declare one or more scopes.":
        "Los alcances (scopes) otorgan distintos niveles de acceso. Esta API no los usa.",
    "API requires the following scopes. Select which ones you want to grant to Swagger UI.":
        "Escriba su correo y contraseña para autorizar las pruebas.",
}

# Some labels are drawn with CSS instead of text, so they are replaced here.
SPANISH_CSS = """
<style>
  .swagger-ui .parameter__name.required:after { content: "obligatorio" !important; }
  .swagger-ui .loading-container .loading:after { content: "cargando" !important; }
  .swagger-ui .response-control-media-type__accept-message { display: none; }
</style>
"""

TRANSLATION_SCRIPT = """
<script>
(function () {
  const labels = %s;

  function translateTextNode(node) {
    const original = node.nodeValue;
    const key = original.trim();
    if (key && Object.prototype.hasOwnProperty.call(labels, key)) {
      node.nodeValue = original.replace(key, labels[key]);
    }
  }

  function translate(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      translateTextNode(node);
    }
    if (root.querySelectorAll) {
      root.querySelectorAll("[placeholder], [title], [aria-label]").forEach(function (el) {
        ["placeholder", "title", "aria-label"].forEach(function (attr) {
          const value = el.getAttribute(attr);
          if (value && labels[value.trim()]) {
            el.setAttribute(attr, labels[value.trim()]);
          }
        });
      });
    }
  }

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (mutation.type === "characterData") {
        translateTextNode(mutation.target);
      }
      mutation.addedNodes.forEach(function (added) {
        if (added.nodeType === Node.TEXT_NODE) {
          translateTextNode(added);
        } else if (added.nodeType === Node.ELEMENT_NODE) {
          translate(added);
        }
      });
    });
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  translate(document.body);
})();
</script>
"""


def register_spanish_docs(app: FastAPI) -> None:
    """Serve the Spanish Swagger UI at /docs. The app must be created with docs_url=None."""

    @app.get(DOCS_URL, include_in_schema=False)
    def swagger_ui_spanish() -> HTMLResponse:
        page = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Documentación",
            oauth2_redirect_url=OAUTH2_REDIRECT_URL,
            swagger_ui_parameters={
                "persistAuthorization": True,  # keep the login after pressing F5
                "tryItOutEnabled": True,       # show "Ejecutar" directly, no "Probar" click needed
                "defaultModelsExpandDepth": -1,  # hide the technical "Schemas" section
            },
        )
        script = TRANSLATION_SCRIPT % json.dumps(SPANISH_LABELS, ensure_ascii=False)
        html = page.body.decode("utf-8")
        html = html.replace("</head>", SPANISH_CSS + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        html = html.replace('<html>', '<html lang="es">', 1)
        return HTMLResponse(html)

    @app.get(OAUTH2_REDIRECT_URL, include_in_schema=False)
    def swagger_ui_redirect() -> HTMLResponse:
        return get_swagger_ui_oauth2_redirect_html()
