"""
    Parse encodings
    Formatting Codebooks
"""
from scripts.config import REF_PATH
import pandas as pd

# Definimos donde guardaremos nuestras herramientas
AUXILIAR_PATH = REF_PATH / ".." / "data" / "interim"


def get_encoding(filepath):
    with open(filepath, 'rb') as file:
        data=file.read()
        res = cchardet.detect(data)
    return res


def format_codebook(code):
    content = code.iloc[8:33].reset_index(drop=True)
    content.columns = content.iloc[0]
    content = content.iloc[1:]
    content.set_index(content.columns[1], inplace=True)
    content = content.drop(columns="Consecutivo\nen la base")

    w = code.iloc[34:38, :1]
    w.columns = ['Variable']
    values = [v.split(":") for v in w['Variable']]
    code_index = [l[0] for l in values]
    col_vals = [l[1].strip("") for l in values]
    w.index = code_index
    w['Variable'] = col_vals
    return content, w