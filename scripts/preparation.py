"""
    Data preparation.
    1. get_encoding(). Detectar la codificación de un archivo.
    2. format_codebook(). Formatear el diccionario de datos y las variables.
    3. load_filetree(). Descargar los archivos de un árbol de archivos.
    4. encode_block(). Detectar la codificación de los archivos de un bloque de datos.
    5. formatted_data(). Formatear los archivos de un bloque de datos y generar los diccionarios de datos y variables.
"""
from scripts.config import DATA_FOLDERS
from scripts.File import File
import cchardet
import pandas as pd



def get_encoding(filepath):
    """
        Detect the encoding of a file.
        pars:
            filepath: str. Path to the file.
        return: 
            dict. Dictionary with the encoding and confidence.
    """
    with open(filepath, 'rb') as file:
        data=file.read()
        res = cchardet.detect(data)
    return res


def format_codebook(code):
    """
        Format the codebook.
        pars:
            code: pd.DataFrame. The codebook data.
        return:
            tuple. The formatted content and variables.
    """
    content = code.iloc[8:33].reset_index(drop=True)
    content.columns = content.iloc[0]
    content = content.iloc[1:]
    content.set_index(content.columns[1], inplace=True)
    content = content.drop(columns="Consecutivo\nen la base")

    var = code.iloc[34:39, :1]
    var.columns = ['Variable']
    values = [v.split(":") for v in var['Variable']]
    code_index = [l[0] for l in values]
    col_vals = [l[1].strip("") for l in values]
    var.index = code_index
    var['Variable'] = col_vals
    return content, var


def encode_block(file_block: dict):
    """
        Detect the encoding of the files of a data block.
        pars:
            file_block: dict. The data block.
        return:
            dict. The data block with the encoding of the files.
    """
    encode = {"Codebook":None,
             "Data": {}}
    encode['Codebook'] = file_block['Codebook']
    encode['Data'] = {year:{"file": file,
                            "encoding": get_encoding(file.ubication)['encoding']} 
                            for year, file in file_block['Data'].items()}
    return encode


def format_block(format_block, block):
    """
        Format the files of a data block and generate the data and variable dictionaries.
        pars:
            format_block: dict. The data block.
            block: str. The name of the data block.
        return:
            dict. The formatted data block with the data and variable dictionaries.
    """
    
    formatted = {"Codebook": {}, "Data": {}}
    codebook = format_block['Codebook']
    file_code = pd.read_excel(codebook.filepath / codebook.file)
    catalog, variables = format_codebook(file_code)
    format_path = DATA_FOLDERS['interm'] / codebook.source
    catfile = File(format_path, f"Diccionario_Datos_{block}.xlsx", codebook.source)
    varfile = File(format_path, f"Tipo_Variables_{block}.xlsx", codebook.source)
    formatted['Codebook'] = {
        "Diccionario": catfile,
        "Variables": varfile}
    catalog.to_excel(catfile.get_local_ubication())
    variables.to_excel(varfile.get_local_ubication())
    data = format_block['Data']
    print(data)
    for y, enficode in data.items():
        file, encode = enficode.values()
        dfile = File(format_path, file.file, file.source)
        dset = pd.read_csv(file.ubication, encoding= encode, low_memory=False)
        dfile_ubication = f"{dfile.get_local_ubication(ext=0)}.xlsx"
        dset.to_excel(dfile_ubication, index=False)
        dfile.ubication = dfile_ubication
        formatted['Data'][y] = dfile
    return formatted