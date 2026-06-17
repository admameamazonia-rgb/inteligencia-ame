# Versão: v.4.8.0 (17062026-1725)
# Arquivo: coleta_noticias.py

import os
import json
import logging
from datetime import datetime, timedelta
import traceback
import textwrap

import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from fpdf import FPDF
import smtplib
from email.message import EmailMessage

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def limpar_texto(texto):
    """Garante que o texto não quebre a geração do PDF (Sanitização Agressiva e Quebra de Linha de Segurança)"""
    if not texto: return ""
    texto = str(texto)
    # 1. Converte aspas inteligentes e travessões da web para o padrão ASCII puro suportado pelo PDF
    texto = texto.replace('\u2013', '-').replace('\u2014', '-').replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    # 2. Converte para Latin-1 ignorando/substituindo caracteres não suportados (como emojis ou símbolos esquisitos)
    texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
    # 3. Força a quebra de blocos contínuos (como URLs longas escondidas) usando espaços para o FPDF poder quebrar a linha
    linhas = textwrap.wrap(texto_limpo, width=85, break_long_words=True)
    return " ".join(linhas)

def buscar_dados():
    logging.info("Iniciando coleta massiva estruturada de dados...")
    noticias = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 1. Fonte: Diário Oficial da União (Governo) via RSS
    try:
        logging.info("[1/10] Acessando Diário Oficial da União (RSS)...")
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
        logging.info("[2/10] Acessando Agência Brasil (RSS)...")
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

    # Limpeza rigorosa nas strings das URLs para evitar bugs de formatação do GitHub
    sites = [
        "https://www.fundoamazonia.gov.br/pt/home/",
        "https://www.fapeam.am.gov.br/",
        "https://gife.org.br/",
        "https://www.sejusc.am.gov.br/avisos-chamados-editais-e-outros/",
        "https://portal.ciee.org.br/",
        "https://www.manaus.am.gov.br/semtepi/a-semtepi/editais/qualifica/",
        "https://www.portalmarcossantos.com.br/2025/09/19/r-500-mil-para-a-sua-carreira-manaus-lanca-edital-qualifica/"
    ]

    # 3. Fonte: Fundo Amazônia / BNDES via Web Scraping
    try:
        logging.info("[3/10] Acessando Fundo Amazônia (Web Scraping)...")
        response = requests.get(sites[0], headers=headers, timeout=10)
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

    # 4. Fonte: FAPEAM (Fundação de Amparo à Pesquisa do Estado do Amazonas) via Web Scraping
    try:
        logging.info("[4/10] Acessando FAPEAM - Editais Regionais (Web Scraping)...")
        response = requests.get(sites[1], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h2', 'h3'])
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            link_tag = item.find('a')
            if titulo and link_tag and 'href' in link_tag.attrs:
                link_final = link_tag['href'] if link_tag['href'].startswith("http") else f"https://www.fapeam.am.gov.br{link_tag['href']}"
                noticias.append({
                    "fonte": "FAPEAM",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping de chamadas e editais da FAPEAM.",
                    "link": link_final
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar FAPEAM: {e}")

    # 5. Fonte: GIFE (Terceiro Setor e Filantropia Privada) via Web Scraping
    try:
        logging.info("[5/10] Acessando Rede GIFE - Terceiro Setor (Web Scraping)...")
        response = requests.get(sites[2], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h2', 'h3'])
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            link_tag = item.find('a')
            if titulo and link_tag and 'href' in link_tag.attrs:
                link_final = link_tag['href'] if link_tag['href'].startswith("http") else f"https://gife.org.br{link_tag['href']}"
                noticias.append({
                    "fonte": "GIFE",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping de editais e publicações GIFE.",
                    "link": link_final
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar GIFE: {e}")

    # 6. Fonte: MDS (Ministério do Desenvolvimento e Assistência Social) via RSS
    try:
        logging.info("[6/10] Acessando MDS (RSS)...")
        mds_feed = feedparser.parse("https://www.gov.br/mds/pt-br/noticias/feed")
        for entry in mds_feed.entries[:4]:
             noticias.append({
                "fonte": "MDS - Gov.br",
                "titulo": entry.title,
                "resumo": entry.summary,
                "link": entry.link
            })
    except Exception as e:
        logging.error(f"Erro ao processar feed do MDS: {e}")

    # 7. Fonte: SEJUSC (Avisos e Editais) via Web Scraping
    try:
        logging.info("[7/10] Acessando SEJUSC (Web Scraping)...")
        response = requests.get(sites[3], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h2', 'h3', 'h4'])
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            link_tag = item.find('a')
            if titulo and link_tag and 'href' in link_tag.attrs:
                link_final = link_tag['href'] if link_tag['href'].startswith("http") else f"https://www.sejusc.am.gov.br{link_tag['href']}"
                noticias.append({
                    "fonte": "SEJUSC",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping de editais e avisos da SEJUSC.",
                    "link": link_final
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar SEJUSC: {e}")

    # 8. Fonte: CIEE (Oportunidades e Programas) via Web Scraping
    try:
        logging.info("[8/10] Acessando CIEE (Web Scraping)...")
        response = requests.get(sites[4], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h2', 'h3'])
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            link_tag = item.find('a')
            if titulo and link_tag and 'href' in link_tag.attrs:
                link_final = link_tag['href'] if link_tag['href'].startswith("http") else f"https://portal.ciee.org.br{link_tag['href']}"
                noticias.append({
                    "fonte": "CIEE",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping do portal CIEE.",
                    "link": link_final
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar CIEE: {e}")

    # 9. Fonte: SEMTEPI (Editais Qualifica) via Web Scraping
    try:
        logging.info("[9/10] Acessando SEMTEPI (Web Scraping)...")
        response = requests.get(sites[5], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h2', 'h3', 'h4'])
        count = 0
        for item in destaques:
            if count >= 3: break
            titulo = item.get_text(strip=True)
            link_tag = item.find('a')
            if titulo and link_tag and 'href' in link_tag.attrs:
                link_final = link_tag['href'] if link_tag['href'].startswith("http") else f"https://www.manaus.am.gov.br{link_tag['href']}"
                noticias.append({
                    "fonte": "SEMTEPI",
                    "titulo": titulo,
                    "resumo": "Processado via Web Scraping de editais da SEMTEPI.",
                    "link": link_final
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar SEMTEPI: {e}")

    # 10. Fonte: Portal Marcos Santos (Notícia Específica Qualifica) via Web Scraping
    try:
        logging.info("[10/10] Acessando Portal Marcos Santos (Web Scraping)...")
        response = requests.get(sites[6], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        destaques = soup.find_all(['h1', 'h2'])
        count = 0
        for item in destaques:
            if count >= 1: break
            titulo = item.get_text(strip=True)
            if titulo:
                noticias.append({
                    "fonte": "Portal Marcos Santos",
                    "titulo": titulo,
                    "resumo": "Matéria específica sobre o edital Qualifica em Manaus.",
                    "link": sites[6]
                })
                count += 1
    except Exception as e:
        logging.error(f"Erro ao processar Portal Marcos Santos: {e}")

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

Analise os dados brutos de todas as fontes coletadas (Gov, Fundo Amazônia, FAPEAM, GIFE, etc) e extraia SOMENTE as oportunidades de alto valor cruzadas com nosso foco.
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

def gerar_pdf(dados_json):
    logging.info("Gerando PDF estruturado completo...")
    pdf = FPDF()
    # Ativa quebra de página automática para garantir que não ultrapasse o limite inferior da folha
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Cabeçalho - Usando sempre set_x(10) para resetar a âncora lateral do FPDF2
    pdf.set_font("helvetica", 'B', 16)
    pdf.set_x(10)
    pdf.cell(0, 10, text=limpar_texto("RELATORIO DE INTELIGENCIA - AME-AMAZONIA"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font("helvetica", '', 10)
    pdf.set_x(10)
    pdf.cell(0, 10, text=limpar_texto(f"Data de Processamento: {dados_json.get('data', '')}"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)

    # Seção 1: Oportunidades (Cards completos)
    pdf.set_font("helvetica", 'B', 14)
    pdf.set_x(10)
    pdf.cell(0, 10, text=limpar_texto("1. OPORTUNIDADES E EDITAIS"), new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.ln(2)
    
    for card in dados_json.get("cards", []):
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_x(10)
        pdf.multi_cell(0, 8, text=limpar_texto(f"[{card.get('categoria', 'Geral')}] Orgao: {card.get('orgao', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", 'B', 10)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, text=limpar_texto(f"Titulo: {card.get('titulo', '')}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", '', 10)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, text=limpar_texto(f"Resumo: {card.get('resumo', '')}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", 'I', 10)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, text=limpar_texto(f"Aplicabilidade: {card.get('aplicabilidade', '')}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", 'U', 10)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, text=limpar_texto(f"Link Oficial: {card.get('link', '')}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(5)

    # Seção 2: Gestão Estatutária
    gestao = dados_json.get("gestao", {})
    if gestao:
        pdf.add_page()
        pdf.set_font("helvetica", 'B', 14)
        pdf.set_x(10)
        pdf.cell(0, 10, text=limpar_texto("2. PLANO DE GESTAO E PRIORIDADES"), new_x="LMARGIN", new_y="NEXT", align='L')
        pdf.ln(5)
        
        # Prioridades
        prioridades = gestao.get("prioridades", {})
        pdf.set_font("helvetica", 'B', 12)
        pdf.set_x(10)
        pdf.cell(0, 8, text=limpar_texto("Matriz de Prioridades:"), new_x="LMARGIN", new_y="NEXT", align='L')
        pdf.set_font("helvetica", '', 10)
        
        for p_alta in prioridades.get("alta", []):
            pdf.set_x(10)
            pdf.multi_cell(0, 6, text=limpar_texto(f"- ALTA: {p_alta}"), new_x="LMARGIN", new_y="NEXT")
        for p_media in prioridades.get("media", []):
            pdf.set_x(10)
            pdf.multi_cell(0, 6, text=limpar_texto(f"- MEDIA: {p_media}"), new_x="LMARGIN", new_y="NEXT")
        for p_baixa in prioridades.get("baixa", []):
            pdf.set_x(10)
            pdf.multi_cell(0, 6, text=limpar_texto(f"- BAIXA: {p_baixa}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(5)
        
        # Ações Práticas
        pdf.set_font("helvetica", 'B', 12)
        pdf.set_x(10)
        pdf.cell(0, 8, text=limpar_texto("Acoes Estrategicas Requeridas:"), new_x="LMARGIN", new_y="NEXT", align='L')
        pdf.set_font("helvetica", '', 10)
        
        for acao in gestao.get("acoes", []):
            pdf.set_x(10)
            pdf.multi_cell(0, 6, text=limpar_texto(f"-> Acao: {acao.get('acao', '')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(10)
            pdf.multi_cell(0, 6, text=limpar_texto(f"   Responsavel: {acao.get('responsavel', '')} | Prazo: {acao.get('prazo', '')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    nome_arquivo = f"Relatorio_{datetime.now().strftime('%d%m%Y-%H%M')}.pdf"
    pdf.output(nome_arquivo)
    logging.info(f"PDF gerado com sucesso: {nome_arquivo}")
    return nome_arquivo

def enviar_email(caminho_pdf):
    logging.info("Iniciando rotina de envio de e-mail (Hostinger SMTP)...")
    smtp_user = os.environ.get("EMAIL_USER")
    smtp_pass = os.environ.get("EMAIL_PASS")
    destinatarios = os.environ.get("EMAIL_TO")
    
    if not smtp_user or not smtp_pass or not destinatarios:
        logging.warning("Credenciais de e-mail não configuradas. Pulando envio de e-mail.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"Relatório Estratégico AME-AMAZÔNIA - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = smtp_user
    msg['To'] = destinatarios
    msg.set_content(
        "Prezados Diretores e Membros do Conselho,\n\n"
        "Segue em anexo o Relatório de Inteligência consolidado de hoje.\n"
        "O documento contém a raspagem completa de editais e oportunidades cruzadas com nosso "
        "Estatuto Social, além da matriz de ações para a Diretoria Executiva.\n\n"
        "Atenciosamente,\nCérebro de IA - AME-AMAZÔNIA"
    )

    with open(caminho_pdf, 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(caminho_pdf))

    try:
        with smtplib.SMTP_SSL('smtp.hostinger.com', 465) as smtp:
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        logging.info("E-mail disparado com sucesso para a diretoria.")
    except Exception as e:
        logging.error(f"Erro ao tentar enviar e-mail: {e}")

def main():
    try:
        dados = buscar_dados()
        if not dados:
            logging.warning("Fim: Nenhuma notícia capturada no momento.")
            return

        resultado_ia = processar_com_gemini(dados)
        
        # Limpeza robusta e cega para o GitHub: usando código do caractere em vez de digitá-lo
        marcador = chr(96) * 3
        texto_limpo = resultado_ia.replace(f"{marcador}json", "").replace(marcador, "").strip()
        
        boletim_obj = json.loads(texto_limpo)
        
        # Correção do horário de Manaus (UTC-4)
        boletim_obj["data"] = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y - %H:%M")
        
        # Salvamento na raiz
        caminho_arquivo = os.path.join(os.getcwd(), 'boletim.json')
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(boletim_obj, f, ensure_ascii=False, indent=2)
            
        logging.info(f"Processo concluído com êxito! 'boletim.json' atualizado em: {caminho_arquivo}")
        
        # Nova Rotina de Governança
        caminho_pdf = gerar_pdf(boletim_obj)
        enviar_email(caminho_pdf)

    except Exception as e:
        logging.error(f"Erro fatal não tratado: {e}")
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()
