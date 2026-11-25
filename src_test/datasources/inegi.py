from config.paths import datapaths
import requests

def download_inegi(url):
    filename = url.split("/")[-1]
    savepath = datapaths['pure']['INEGI'] / filename
    if not savepath.exists():
        response = requests.get(url)
        with open(savepath, "wb") as file:
            file.write(response.content)



