"""
Cliente de la Intención de Siembra y de Cosecha (agroprograma) del DGSIAP.

El formulario es una copia del de avance_agricola, pero cada combo y la
tabla de resultados se piden con un POST a control/ctrl.siembras.cosechas.php
con action=<token>&rnd=<n>&<filtros>. El token es el atributo
data-verificacion del elemento en la página; los combos regresan JSON
[{"ID": ..., "NOMBRE": ...}] y el reporte un fragmento HTML con la tabla.
"""

from functools import cached_property
from io import StringIO
import random
import re

from bs4 import BeautifulSoup
import pandas as pd
import requests

from scripts.avance import NIVEL, TIPO, AvanceAgricola
from scripts.config import source_links

URL = source_links["DGSIAP"]["agroprograma"]
CONTROL = URL / "control" / "ctrl.siembras.cosechas.php"

CLAVES = ("CVEGEO", "Clave Entidad", "Clave Municipio")
ALIAS = {"alfalfa": "alfalfa verde"}


class AgroPrograma:
    def __init__(self, timeout=120):
        self.session = requests.Session()
        self.timeout = timeout

    @cached_property
    def tokens(self):
        """
        Lee de la página el token de cada acción: {id_elemento: token}.

        Hoy son fijos y no dependen de la sesión, pero se leen en cada
        instancia por si cambian con una actualización del sitio.
        """
        r = self.session.get(URL, timeout=self.timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        tokens = {
            e["id"]: e["data-verificacion"]
            for e in soup.select("[data-verificacion]")
        }
        for e in soup.select("#reporteInit, #cargaUM, #cargaVar"):
            tokens[e["id"]] = e["value"]
        return tokens

    def _post(self, accion, **params):
        """
        Ejecuta una acción del controlador y devuelve la respuesta.

        Con un token inválido el servidor responde HTTP 200 sin contenido.
        """
        r = self.session.post(
            CONTROL,
            timeout=self.timeout,
            data={
                "action": self.tokens[accion],
                "rnd": random.randrange(10_000),
                **params,
            },
        )
        r.raise_for_status()
        if not r.text.strip():
            raise RuntimeError(f"{accion}{params}: respuesta vacía.")
        return r

    def _opciones(self, accion, **params):
        """Devuelve las opciones {valor: texto} que llenan un combo."""
        return {
            str(o["ID"]): o["NOMBRE"].strip()
            for o in self._post(accion, **params).json()
        }

    def anios(self):
        return self._opciones("anioagric", CLAVE=1)

    def ciclos(self):
        return self._opciones("cicloProd", CLAVE=1)

    def modalidades(self):
        return self._opciones("modalidad", CLAVE=1)

    def entidades(self):
        return self._opciones("entidad", CLAVE=1)

    def distritos(self, entidad):
        return self._opciones("distrito", estado=entidad)

    def municipios(self, entidad, distrito=0):
        return self._opciones("municipio", estado=entidad, distrito=distrito)

    def cultivos(self, anio, ciclo=5, entidad=0):
        return self._opciones("cultivo", anio=anio, edo=entidad, ciclo=ciclo)

    def unidades(self, cultivo):
        return self._opciones("cargaUM", cultivo=cultivo)

    def variedades(self, cultivo, unidad=None):
        if unidad is None:
            unidad = next(iter(self.unidades(cultivo)))
        return self._opciones("cargaVar", cultivo=cultivo, unidMedida=unidad)

    def anio_vigente(self):
        """Año agrícola que la página consulta por defecto."""
        return int(self._post("reporteInit", VAL=1).json()["ANIO_AGRICOLA"])

    def reporte(
        self,
        anio=0,
        ciclo=5,
        modalidad=3,
        entidad=0,
        distrito=0,
        municipio=0,
        cultivo=0,
        variedad=0,
        nivel="entidad",
        tipo="geografico",
    ):
        """
        Consulta la intención de siembra y devuelve la tabla como DataFrame.

        anio=0 usa el año agrícola vigente. Con un cultivo se agregan la
        producción a obtener y el rendimiento esperado. Las claves
        (CVEGEO, entidad, municipio) se conservan como texto y el título
        con los filtros aplicados queda en df.attrs["encabezado"].

        Con variedad el servidor sí filtra, pero en el encabezado rotula
        la variedad con el nombre de otro cultivo (busca solo por ID); el
        nombre correcto es el de variedades(cultivo).
        """
        html = self._post(
            "Consultar",
            tipo=TIPO[tipo],
            anioagric=anio or self.anio_vigente(),
            cicloProd=ciclo,
            modalidad=modalidad,
            entidad=entidad,
            distrito=distrito,
            municipio=municipio,
            cultivo=cultivo,
            unidMed=0,
            variedad=variedad,
            opcionDDRMpio=NIVEL[nivel],
        ).text
        soup = BeautifulSoup(html, "html.parser")
        if soup.table is None:
            msg = soup.get_text(" ", strip=True)
            raise RuntimeError(f"reporte: sin datos. {msg}")
        df = pd.read_html(
            StringIO(html), thousands=",", converters=dict.fromkeys(CLAVES, str)
        )[0]
        df = df[df["No."] != "Total"].drop(columns="No.").reset_index(drop=True)
        df.attrs["encabezado"] = " ".join(
            e.get_text(" ", strip=True)
            for e in soup.select("#subTitleMod, #titulosFiltros")
        )
        return df


def _nombre_base(nombre):
    """Quita la unidad entre paréntesis y homologa "en verde" a "verde"."""
    base = re.sub(r"\s*\(.*?\)", "", nombre.lower())
    base = " ".join(base.replace(" en verde", " verde").split())
    return ALIAS.get(base, base)


def equivalencia_cultivos(anio, ciclo=5):
    """
    Relaciona las claves de cultivo de agroprograma y avance_agricola.

    Los sitios numeran distinto (Maíz grano es 19700 aquí y 225 en
    avance), así que se emparejan por nombre. Una fila con NaN es un
    cultivo sin pareja en el otro catálogo para ese año y ciclo.
    """
    catalogos = {
        "agroprograma": AgroPrograma().cultivos(anio, ciclo),
        "avance": AvanceAgricola().cultivos(anio, 0, ciclo),
    }
    tablas = [
        pd.DataFrame(
            [(_nombre_base(n), k, n) for k, n in cultivos.items() if k != "0"],
            columns=["base", f"id_{sitio}", f"cultivo_{sitio}"],
        )
        for sitio, cultivos in catalogos.items()
    ]
    return (
        tablas[0].merge(tablas[1], on="base", how="outer").drop(columns="base")
    )
