"""Registro local y reproducible de modelos entrenados."""

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from joblib import dump, load

from proyecto_agronomia.config import MODELS_DIR


def normalizar_identificador(texto: str) -> str:
    """Convierte un nombre legible en un identificador estable para rutas."""
    identificador = texto.strip().lower()
    reemplazos = str.maketrans("áéíóúüñ", "aeiouun")
    identificador = identificador.translate(reemplazos)
    identificador = re.sub(r"[^a-z0-9]+", "_", identificador).strip("_")
    if not identificador:
        raise ValueError("No fue posible construir un identificador válido.")
    return identificador


def ruta_version_modelo(
    cultivo: str,
    version: str,
    familia: str = "rendimiento",
    directorio: Path = MODELS_DIR,
) -> Path:
    """Construye ``models/familia/cultivo/version`` sin crearla."""
    return (
        Path(directorio)
        / normalizar_identificador(familia)
        / normalizar_identificador(cultivo)
        / normalizar_identificador(version)
    )


def _guardar_json(datos: Any, ruta: Path) -> None:
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def guardar_modelo(
    modelo: Any,
    cultivo: str,
    version: str,
    metadata: dict[str, Any],
    metricas: dict[str, Any],
    variables: list[str],
    familia: str = "rendimiento",
    directorio: Path = MODELS_DIR,
    sobrescribir: bool = False,
) -> Path:
    """Guarda pipeline, metadatos, métricas y esquema de variables."""
    destino = ruta_version_modelo(cultivo, version, familia, directorio)
    ruta_modelo = destino / "model.joblib"
    if ruta_modelo.exists() and not sobrescribir:
        raise FileExistsError(
            f"Ya existe {ruta_modelo}. Usa otra versión o sobrescribir=True."
        )
    destino.mkdir(parents=True, exist_ok=True)
    metadata_completa = {
        **metadata,
        "cultivo": cultivo,
        "familia": familia,
        "version": version,
        "fecha_guardado_utc": datetime.now(UTC).isoformat(),
        "artefacto": ruta_modelo.name,
    }
    dump(modelo, ruta_modelo, compress=3)
    _guardar_json(metadata_completa, destino / "metadata.json")
    _guardar_json(metricas, destino / "metrics.json")
    _guardar_json({"variables": variables}, destino / "features.json")
    return destino


def cargar_modelo(
    cultivo: str,
    version: str,
    familia: str = "rendimiento",
    directorio: Path = MODELS_DIR,
) -> tuple[Any, dict[str, Any]]:
    """Carga un artefacto local confiable y sus metadatos."""
    destino = ruta_version_modelo(cultivo, version, familia, directorio)
    ruta_modelo = destino / "model.joblib"
    ruta_metadata = destino / "metadata.json"
    if not ruta_modelo.is_file() or not ruta_metadata.is_file():
        raise FileNotFoundError(f"Modelo incompleto o inexistente: {destino}")
    modelo = load(ruta_modelo)
    metadata = json.loads(ruta_metadata.read_text(encoding="utf-8"))
    return modelo, metadata
