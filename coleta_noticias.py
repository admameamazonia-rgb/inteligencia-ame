# Versão: v.3.1.0 (16062026-2300)
# Arquivo: coleta_noticias.py
import os
import json
import logging
from datetime import datetime
import traceback

import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def buscar_dados():
    logging.info("Iniciando coleta estruturada de dados...")
    noticias = []
    
    # 1. Fonte: Diário Oficial da União (Governo) via RSS
    try:
        logging.info("[1/3] Acessando Diário Oficial da União (RSS)...")
        dou_feed = feedparser.parse("https://www.in.gov.br/rss/api/feed")
        for entry in dou_feed.entries[:5]:
            noticias.append({
                "fonte": "Diário Oficial da União",
                "titulo": entry.title,
                "resumo": entry.summary,
                "link": entry.link
            })
    except Exception as e:
        logging.error(f"Erro ao processar feed do DOU: {e}")

    # 2. Fonte: Agência Brasil (Contexto Nacional e Cidadania) via RSS
    try:
        logging.info("[2/3] Acessando Agência Brasil (RSS)...")
        agencia_brasil = feedparser.parse("https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml")
        for entry in agencia_brasil.entries[:5]:
             noticias.append({
                "fonte": "Agência Brasil",
                "titulo": entry.title,
                "resumo": entry.summary,
                "link": entry.link
            })
    except Exception as e:
        logging.error(f"Erro ao processar feed da Agência Brasil: {e}")

    # 3. Fonte: Fundo Amazônia / BNDES via Web Scraping
    try:
        logging.info("[3/3] Acessando Fundo Amazônia (Web Scraping)...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get("https://www.fundoamazonia.gov.br/pt/home/", headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all('h3')
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            if titulo:
                link_tag = item.find('a')
                link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else "https://www.fundoamazonia.gov.br"
                noticias.append({
                    "fonte": "Fundo Amazônia",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping da página inicial do Fundo Amazônia.",
                    "link": link if link.startswith("http") else f"https://www.fundoamazonia.gov.br{link}"
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar Fundo Amazônia (Scraping): {e}")

    return noticias

def processar_com_gemini(dados_brutos):
    logging.info("Iniciando Inteligência Artificial (Gemini 2.5 Flash)...")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não localizada. Abortando IA.")
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
Você é o Cérebro de IA do Portal de Inteligência.
Contexto Institucional da AME-AMAZÔNIA:
- Foco: Multiempreendedorismo, Inclusão Produtiva, Meio Ambiente, Empreendedorismo Verde, Educação (Jovem Aprendiz), Assistência Social e Tecnologia.
- Público-Alvo: Indivíduos em vulnerabilidade, comunidades ribeirinhas, jovens e empreendedores rurais.
- Local: Manaus/AM e Região Norte.
- Estrutura: Diretor(a) Presidente, Diretor(a) Executivo(a), Diretor(a) Financeiro(a), Diretor(a) de Comunicação, Diretor(a) de RIG e Conselho Fiscal.

Analise os dados brutos e extraia SOMENTE as oportunidades cruzadas com nosso foco social e ambiental.
Gere a resposta estritamente no formato JSON abaixo, sem blocos de código "markdown" encapsulando e sem textos auxiliares.

Formato do Output JSON Exigido:
{{
  "data": "DD/MM/AAAA - HH:MM",
  "cards": [
    {{
      "categoria": "[Editais, Legislação, Parcerias, Tecnologia]",
      "icone": "[Emoji]",
      "cor": "[Código Hex como #2E7D22 ou #68BB8A]",
      "orgao": "[Órgão Emissor]",
      "titulo": "[Título adaptado para clareza]",
      "resumo": "[Resumo prático com até 250 caracteres]",
      "aplicabilidade": "[Como a AME-AMAZÔNIA pode se beneficiar desta notícia]",
      "link": "[Link Oficial]"
    }}
  ],
  "gestao": {{
    "prioridades": {{
      "alta": ["Ação imediata 1", "Ação imediata 2"],
      "media": ["Ação de médio prazo 1"],
      "baixa": ["Ação futura 1"]
    }},
    "acoes": [
      {{
        "acao": "[Ação objetiva a realizar]",
        "responsavel": "[Cargo base da estrutura (ex: Diretor(a) de RIG)]",
        "prazo": "[Ex: 5 dias]"
      }}
    ]
  }}
}}

Dados Brutos Coletados Hoje:
{json.dumps(dados_brutos, ensure_ascii=False)}
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
             response_mime_type="application/json",
             temperature=0.2
        ),
    )
    return response.text

def main():
    try:
        dados = buscar_dados()
        if not dados:
            logging.warning("Fim: Nenhuma notícia capturada no momento.")
            return

        resultado_ia = processar_com_gemini(dados)
        boletim_obj = json.loads(resultado_ia)
        boletim_obj["data"] = datetime.now().strftime("%d/%m/%Y - %H:%M")
        
        with open('boletim.json', 'w', encoding='utf-8') as f:
            json.dump(boletim_obj, f, ensure_ascii=False, indent=2)
            
        logging.info("Processo concluído com êxito! 'boletim.json' atualizado na raiz.")
    except Exception as e:
        logging.error(f"Erro fatal não tratado: {e}")
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()