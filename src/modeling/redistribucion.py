"""Escenarios restringidos de intercambio territorial de cultivos."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from proyecto_agronomia.config import MODELS_DIR
from modeling.cultivos import (
    VARIABLES_CATEGORICAS,
    VARIABLES_NUMERICAS,
    preparar_cultivo,
    separar_xy,
)
from modeling.registry import cargar_modelo, ruta_version_modelo

CLAVES_BLOQUE = ["cvegeo", "Nomcicloproductivo", "Nommodalidad"]


def cultivos_con_modelo_valido(
    cultivos: list[str],
    version: str = "v1_principales",
    r2_espacial_minimo: float = 0.50,
) -> pd.DataFrame:
    """Filtra artefactos por R2 de la prueba espacio-temporal."""
    filas = []
    variables_esperadas = [*VARIABLES_NUMERICAS, *VARIABLES_CATEGORICAS]
    for cultivo in cultivos:
        destino = ruta_version_modelo(cultivo, version)
        requeridos = ["model.joblib", "metadata.json", "metrics.json", "features.json"]
        if not all((destino / nombre).is_file() for nombre in requeridos):
            continue
        metadata = json.loads((destino / "metadata.json").read_text(encoding="utf-8"))
        metricas = json.loads((destino / "metrics.json").read_text(encoding="utf-8"))
        esquema = json.loads((destino / "features.json").read_text(encoding="utf-8"))
        esquema_compatible = esquema.get("variables") == variables_esperadas
        ganador = metadata["algoritmo"]
        espacial = next(
            fila for fila in metricas["comparacion_modelos"]
            if fila["modelo"] == ganador
            and fila["particion"] == "prueba_espaciotemporal"
        )
        filas.append({
            "cultivo": cultivo,
            "version": version,
            "esquema_compatible": esquema_compatible,
            **espacial,
        })
    tabla = pd.DataFrame(filas)
    if tabla.empty:
        return tabla
    tabla["elegible"] = (
        tabla["esquema_compatible"] & tabla["r2"].ge(r2_espacial_minimo)
    )
    return tabla.sort_values("r2", ascending=False).reset_index(drop=True)


def construir_matriz_potencial(
    datos_principales: pd.DataFrame,
    cultivos: list[str],
    version: str = "v1_principales",
    anio_base: int = 2025,
    anios_clima: tuple[int, int] = (2022, 2025),
    minimo_anios_historia: int = 3,
) -> pd.DataFrame:
    """Predice rendimiento medio reciente solo donde existe soporte historico."""
    preparados = []
    for cultivo in cultivos:
        preparados.append(preparar_cultivo(datos_principales, cultivo))
    historia = pd.concat(preparados, ignore_index=True)

    conteo = (
        historia.groupby([*CLAVES_BLOQUE, "Nomcultivo"], observed=True)["Anio"]
        .nunique().rename("anios_historia").reset_index()
    )
    base = historia.loc[historia["Anio"].eq(anio_base)].copy()
    superficies = (
        base.groupby([*CLAVES_BLOQUE, "Nomcultivo"], as_index=False, observed=True)
        ["Cosechada"].sum().rename(columns={"Cosechada": "superficie_base_ha"})
    )
    superficies_bloque = (
        superficies.groupby(CLAVES_BLOQUE, as_index=False, observed=True)
        ["superficie_base_ha"].sum().rename(columns={"superficie_base_ha": "superficie_bloque_ha"})
    )

    reciente = historia.loc[historia["Anio"].between(*anios_clima)].copy()
    ambientes = (
        reciente
        # Las variables de historial son propias del cultivo. Conservar esta
        # clave evita asignar a un cultivo la trayectoria productiva de otro.
        .drop_duplicates([*CLAVES_BLOQUE, "Nomcultivo", "Anio"])
        .copy()
    )
    candidatos = conteo.loc[
        conteo["Nomcultivo"].isin(cultivos)
        & conteo["anios_historia"].ge(minimo_anios_historia)
    ].copy()
    # Toda asignacion observada en el anio base se conserva para garantizar
    # que la solucion inicial siempre sea factible.
    candidatos = pd.concat([
        candidatos,
        superficies[[*CLAVES_BLOQUE, "Nomcultivo"]].assign(anios_historia=0),
    ]).sort_values("anios_historia").drop_duplicates(
        [*CLAVES_BLOQUE, "Nomcultivo"], keep="last"
    )

    predicciones = []
    for cultivo in cultivos:
        soporte = candidatos.loc[candidatos["Nomcultivo"].eq(cultivo)]
        evaluacion = ambientes.loc[ambientes["Nomcultivo"].eq(cultivo)].merge(
            soporte,
            on=[*CLAVES_BLOQUE, "Nomcultivo"],
            how="inner",
            suffixes=("", "_soporte"),
        )
        if evaluacion.empty:
            continue
        modelo, _ = cargar_modelo(cultivo, version)
        X, _ = separar_xy(evaluacion.assign(Rendimiento=1.0))
        evaluacion["rendimiento_predicho"] = np.maximum(modelo.predict(X), 0)
        predicciones.append(
            evaluacion.groupby([*CLAVES_BLOQUE, "Nomcultivo"], as_index=False, observed=True)
            .agg(
                rendimiento_esperado=("rendimiento_predicho", "mean"),
                rendimiento_desviacion=("rendimiento_predicho", "std"),
                anios_clima=("Anio", "nunique"),
                anios_historia=("anios_historia", "max"),
                Nomestado=("Nomestado", "first"),
                Nommunicipio=("Nommunicipio", "first"),
            )
        )
    matriz = pd.concat(predicciones, ignore_index=True)
    matriz = matriz.merge(superficies, on=[*CLAVES_BLOQUE, "Nomcultivo"], how="left")
    matriz["superficie_base_ha"] = matriz["superficie_base_ha"].fillna(0.0)
    matriz = matriz.merge(superficies_bloque, on=CLAVES_BLOQUE, how="left")
    return matriz.loc[matriz["superficie_bloque_ha"].gt(0)].reset_index(drop=True)


def optimizar_intercambios(matriz: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Maximiza toneladas manteniendo areas por bloque y cultivo-ciclo-modalidad."""
    datos = matriz.reset_index(drop=True).copy()
    bloques = pd.factorize(pd.MultiIndex.from_frame(datos[CLAVES_BLOQUE]))[0]
    productos = pd.factorize(pd.MultiIndex.from_frame(
        datos[["Nomcultivo", "Nomcicloproductivo", "Nommodalidad"]]
    ))[0]
    n_bloques = bloques.max() + 1
    n_productos = productos.max() + 1
    columnas = np.arange(len(datos))
    A = coo_matrix(
        (
            np.ones(len(datos) * 2),
            (
                np.r_[bloques, n_bloques + productos],
                np.r_[columnas, columnas],
            ),
        ),
        shape=(n_bloques + n_productos, len(datos)),
    ).tocsr()
    b_bloques = datos.groupby(bloques, sort=False)["superficie_bloque_ha"].first().to_numpy()
    b_productos = datos.groupby(productos, sort=False)["superficie_base_ha"].sum().to_numpy()
    resultado = linprog(
        c=-datos["rendimiento_esperado"].to_numpy(),
        A_eq=A,
        b_eq=np.r_[b_bloques, b_productos],
        bounds=(0, None),
        method="highs",
    )
    if not resultado.success:
        raise RuntimeError(f"La optimizacion no convergio: {resultado.message}")
    diagnostico = {
        "exito": bool(resultado.success),
        "mensaje": resultado.message,
        "produccion_base_predicha": float(
            np.dot(datos["superficie_base_ha"], datos["rendimiento_esperado"])
        ),
        "produccion_optima_predicha": float(-resultado.fun),
    }
    return resultado.x, diagnostico


def crear_escenarios(
    matriz: pd.DataFrame,
    superficie_optima: np.ndarray,
    proporciones: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Interpola entre la distribucion observada y la optima factible."""
    proporciones = proporciones or {
        "conservador": 0.10, "intermedio": 0.25, "exploratorio": 0.40,
    }
    salida = matriz.copy()
    base = salida["superficie_base_ha"].to_numpy()
    for nombre, proporcion in proporciones.items():
        superficie = base + proporcion * (superficie_optima - base)
        salida[f"superficie_{nombre}_ha"] = superficie
        salida[f"cambio_{nombre}_ha"] = superficie - base
        salida[f"produccion_{nombre}_t"] = superficie * salida["rendimiento_esperado"]
    return salida
