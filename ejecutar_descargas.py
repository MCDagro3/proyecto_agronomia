"""Ejecuta secuencialmente las notebooks de adquisición del proyecto.

Uso básico::

    python ejecutar_descargas.py

Las notebooks sólo se guardan cuando terminan correctamente. Cada una utiliza
las funciones del paquete, por lo que conserva sus mecanismos de caché y evita
volver a descargar archivos que ya existen.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time

try:
    import nbformat
    from nbclient import NotebookClient
except ModuleNotFoundError as error:
    raise SystemExit(
        "Faltan dependencias para ejecutar notebooks. Instala el entorno con "
        "`python -m pip install -r requirements.txt`."
    ) from error


PROJ_ROOT = Path(__file__).resolve().parent
NOTEBOOKS_DIR = PROJ_ROOT / "notebooks"

# INEGI se ejecuta primero porque la notebook climática utiliza sus geometrías
# municipales para obtener los puntos de consulta de NASA POWER.
NOTEBOOKS_DESCARGA = (
    "descargar_inegi.ipynb",
    "descarga_agricola.ipynb",
    "descarga_edafologia.ipynb",
    "descarga_clima_nasa.ipynb",
)


def ejecutar_notebook(
    ruta: Path,
    *,
    timeout: int | None = None,
    guardar: bool = True,
) -> float:
    """Ejecuta una notebook desde la raíz del proyecto y devuelve segundos."""
    inicio = time.perf_counter()
    notebook = nbformat.read(ruta, as_version=4)
    cliente = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(PROJ_ROOT)}},
        allow_errors=False,
    )
    cliente.execute()

    # Guardado atómico: la notebook original sólo se reemplaza tras completar
    # todas sus celdas y escribir correctamente el archivo temporal.
    if guardar:
        temporal = ruta.with_suffix(".executed.tmp.ipynb")
        try:
            nbformat.write(notebook, temporal)
            temporal.replace(ruta)
        finally:
            temporal.unlink(missing_ok=True)
    return time.perf_counter() - inicio


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ejecuta las cuatro notebooks de descarga del proyecto.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Límite por celda en segundos; 0 significa sin límite.",
    )
    parser.add_argument(
        "--continuar-si-error",
        action="store_true",
        help="Continúa con las demás notebooks si una falla.",
    )
    parser.add_argument(
        "--sin-guardar",
        action="store_true",
        help="Ejecuta las notebooks sin reemplazar sus salidas guardadas.",
    )
    parser.add_argument(
        "--solo",
        choices=NOTEBOOKS_DESCARGA,
        action="append",
        help="Ejecuta sólo esta notebook; puede repetirse varias veces.",
    )
    return parser


def main() -> int:
    argumentos = construir_parser().parse_args()
    seleccion = tuple(argumentos.solo or NOTEBOOKS_DESCARGA)
    faltantes = [nombre for nombre in seleccion if not (NOTEBOOKS_DIR / nombre).is_file()]
    if faltantes:
        print(f"No se encontraron notebooks: {', '.join(faltantes)}", file=sys.stderr)
        return 2

    timeout = None if argumentos.timeout == 0 else argumentos.timeout
    errores: list[tuple[str, str]] = []
    inicio_total = time.perf_counter()
    print(f"Inicio: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"Raíz de ejecución: {PROJ_ROOT}")
    print(f"Notebooks seleccionadas: {len(seleccion)}\n")

    for numero, nombre in enumerate(seleccion, start=1):
        ruta = NOTEBOOKS_DIR / nombre
        print(f"[{numero}/{len(seleccion)}] Ejecutando {nombre}...")
        try:
            segundos = ejecutar_notebook(
                ruta,
                timeout=timeout,
                guardar=not argumentos.sin_guardar,
            )
        except Exception as error:
            # Captura fallas de celdas, del kernel o de escritura. No captura
            # KeyboardInterrupt, para que Ctrl+C conserve su comportamiento.
            mensaje = f"{type(error).__name__}: {error}"
            errores.append((nombre, mensaje))
            print(f"  ERROR: {mensaje}", file=sys.stderr)
            if not argumentos.continuar_si_error:
                print("Ejecución detenida. Usa --continuar-si-error para continuar.")
                break
        else:
            accion = "ejecutada y guardada" if not argumentos.sin_guardar else "ejecutada"
            print(f"  OK: {accion} en {segundos / 60:.1f} minutos.\n")

    duracion = time.perf_counter() - inicio_total
    print(f"Tiempo total: {duracion / 60:.1f} minutos.")
    if errores:
        print(f"Notebooks con error: {len(errores)}", file=sys.stderr)
        for nombre, mensaje in errores:
            primera_linea = mensaje.splitlines()[0]
            print(f"  - {nombre}: {primera_linea}", file=sys.stderr)
        return 1
    print("Las notebooks seleccionadas terminaron correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
