# Versão: v.3.3.0 (17062026-0015)
# Arquivo: coleta_noticias.py

import os
import json
import logging
from datetime import datetime, timedelta
import traceback
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def buscar_dados():
    noticias = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    urls = {
        "DOU": "https://www.in.gov.br/rss/api/feed",
        "AgenciaBrasil": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
        "MDS": "https://www.gov.br/mds/pt-br/noticias/feed"
    }
    
    for nome, url in urls.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                noticias.append({"fonte": nome, "titulo": entry.title, "resumo": entry.summary, "link": entry.link})
        except Exception as e:
            logging.error(f"Erro em {nome}: {e}")
    return noticias

def processar_com_gemini(dados_brutos):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Analise estes dados para a AME-AMAZÔNIA e gere um JSON estrito: {json.dumps(dados_brutos, ensure_ascii=False)}"
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
    return response.text

def main():
    try:
        dados = buscar_dados()
        resultado_ia = processar_com_gemini(dados)
        boletim_obj = json.loads(resultado_ia)
        manaus_time = datetime.now() - timedelta(hours=4)
        boletim_obj["data"] = manaus_time.strftime("%d/%m/%Y - %H:%M")
        
        # Salva exatamente na pasta de trabalho do GitHub Actions
        caminho_arquivo = os.path.join(os.getcwd(), 'boletim.json')
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(boletim_obj, f, ensure_ascii=False, indent=2)
        logging.info(f"Boletim salvo em {caminho_arquivo}")
    except Exception as e:
        logging.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    main()
