"""
Cliente del Avance de Siembras y Cosechas del DGSIAP.

La página funciona con xajax 0.2.5: cada combo y la tabla de resultados
se piden al servidor con xajax=<función> y xajaxargs[]=<argumento>. La
respuesta es un XML cuyos comandos <cmd n="as" t="id"> traen el HTML que
se asigna a cada elemento del formulario.
"""

from io import StringIO
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import pandas as pd
import requests

from scripts.config import source_links

URL = source_links["DGSIAP"]["avance"]

TIPO = {"geografico": 1, "cultivo": 2}
NIVEL = {"entidad": 2, "distrito_municipio": 3, "distrito": 0, "municipio": 1}


class AvanceAgricola:
    def __init__(self, timeout=120):
        self.session = requests.Session()
        self.timeout = timeout

    def _xajax(self, funcion, *args):
        """
        Ejecuta una función xajax y devuelve {id_elemento: html}.

        El servidor declara iso-8859-1 pero envía windows-1252, y reporta
        sus errores como warnings de PHP con HTTP 200 en lugar del XML.
        """
        r = self.session.get(
            URL,
            timeout=self.timeout,
            params={
                "xajax": funcion,
                "xajaxr": 1,
                "xajaxargs[]": [str(a) for a in args],
            },
        )
        r.raise_for_status()
        texto = r.content.decode("cp1252", errors="replace")
        previo, _, xml = texto.partition("<xjx>")
        cmds = ET.fromstring("<xjx>" + xml) if xml else []
        out = {
            c.get("t"): c.text
            for c in cmds
            if c.get("n") == "as" and (c.text or "").strip()
        }
        if not out:
            msg = BeautifulSoup(previo, "html.parser").get_text(" ", strip=True)
            raise RuntimeError(f"{funcion}{args}: sin datos. {msg}")
        return out

    def _opciones(self, funcion, *args):
        """Devuelve las opciones {valor: texto} que llenan un combo."""
        html = next(iter(self._xajax(funcion, *args).values()))
        soup = BeautifulSoup(html, "html.parser")
        return {
            o.get("value", ""): o.get_text(strip=True)
            for o in soup.find_all("option")
        }

    def anios(self):
        return self._opciones("llenaAnios")

    def meses(self, anio):
        return self._opciones("llenaMes", anio)

    def ciclos(self):
        return self._opciones("llenaCiclo")

    def modalidades(self):
        return self._opciones("llenaModa")

    def entidades(self):
        return self._opciones("llenaEntidades")

    def distritos(self, entidad):
        return self._opciones("llenaDistrito", entidad)

    def municipios(self, entidad, distrito=0):
        return self._opciones("cargaMuni", entidad, distrito)

    def cultivos(self, anio, mes, ciclo=5, entidad=0, distrito=0, municipio=0):
        return self._opciones(
            "llenaCultivo", anio, entidad, mes, ciclo, distrito, municipio
        )

    def unidades(self, cultivo):
        return self._opciones("llenaUnidMed", cultivo)

    def variedades(self, cultivo, unidad=None):
        if unidad is None:
            unidad = next(iter(self.unidades(cultivo)))
        return self._opciones("llenaVariedad", cultivo, unidad)

    def reporte(
        self,
        anio=0,
        mes=0,
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
        Consulta el avance y devuelve la tabla como DataFrame.

        anio=0 y mes=0 devuelven el último corte publicado. El servidor
        ignora la unidad de medida: la toma del propio cultivo y la muestra
        junto a su nombre en df.attrs["encabezado"], donde también quedan
        los filtros aplicados y la fecha de corte.
        """
        html = self._xajax(
            "reporte",
            TIPO[tipo],
            anio,
            ciclo,
            modalidad,
            entidad,
            distrito,
            municipio,
            cultivo,
            0,
            variedad,
            NIVEL[nivel],
            0,
            0,
            0,
            mes,
        )["Resultado"]
        df = pd.read_html(StringIO(html), thousands=",")[0]
        df.columns = [
            b if not b.startswith("Unnamed") else a for a, b in df.columns
        ]
        df = df.iloc[:, 1:]
        df = df[df.iloc[:, 0] != "Total"].reset_index(drop=True)
        titulo = BeautifulSoup(html, "html.parser").select_one(".titulosTabla")
        df.attrs["encabezado"] = titulo.get_text(" ", strip=True)
        return df
