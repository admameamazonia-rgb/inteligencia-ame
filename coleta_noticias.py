# Versão: v.3.5.0 (17062026-0025)
import os, json, logging
from datetime import datetime, timedelta
import feedparser
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def buscar_dados():
    noticias = []
    urls = ["https://www.in.gov.br/rss/api/feed", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"]
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                noticias.append({"titulo": entry.title, "link": entry.link})
        except: continue
    return noticias

def main():
    dados = buscar_dados()
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Analise estes dados e gere um JSON estrito com campos 'data' e 'cards': {json.dumps(dados)}"
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
    
    # Processamento seguro
    boletim_obj = json.loads(response.text)
    
    # Se a IA retornar uma lista, criamos o dicionário padrão
    if isinstance(boletim_obj, list):
        boletim_obj = {"data": "", "cards": boletim_obj}
        
    manaus_time = datetime.now() - timedelta(hours=4)
    boletim_obj["data"] = manaus_time.strftime("%d/%m/%Y - %H:%M")
    
    with open('boletim.json', 'w', encoding='utf-8') as f:
        json.dump(boletim_obj, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
