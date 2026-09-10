import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# ----------------------------------------------------
# CREDENCIAIS E TOKENS OFICIAIS
# ----------------------------------------------------
APIBRASIL_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcC5hcGlicmFzaWwuaW8vYXBpL3YyL2F1dGgvbG9naW4iLCJpYXQiOjE3ODg5OTQ3MTUsImV4cCI6MTgyMDUzMDcxNSwibmJmIjoxNzg4OTk0NzE1LCJqdGkiOiIxMkhtMk9YR2Q4d3JDTjdzIiwic3ViIjoiNjAzMzMiLCJzZWFyY2giOiIwMThhNGRjOC1lMDQ5LTQ5MzQtOTlhOS1mYWUwMTFhZmQ2NDcifQ.QaLq6W3H-GfXtxgncytiM3sRRef2bJownImyqf3ZXDQ"

PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "70634|7PHvOzg8JQAqCodw1Vh1XgEWx92KpSPG5TVvvQhi423c8a77")

GMAIL_USER = "descobrezap@gmail.com"
GMAIL_APP_PASS = "pfzh sxln wgnm tkxj"

# Cache em memória para simulação/checagem de pagamentos por TXID
PAGAMENTOS_CACHE = {}

# ----------------------------------------------------
# SERVIR O SITE (INDEX.HTML E ESTÁTICOS)
# ----------------------------------------------------
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("index.html")

# ----------------------------------------------------
# CONSULTA DE DADOS REAIS (APIBRASIL)
# ----------------------------------------------------
def buscar_dados_completos(telefone: str):
    phone_clean = "".join(filter(str.isdigit, telefone))
    url = "https://app.apibrasil.io/api/v2/dados/telefone"
    headers = {
        "Authorization": f"Bearer {APIBRASIL_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"phone": phone_clean}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"Erro APIBrasil: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Exceção APIBrasil: {str(e)}")
        return None

@app.post("/api/consultar-telefone")
@app.post("/consultar-telefone")
async def consultar_telefone(request: Request):
    data = await request.json()
    telefone = data.get("telefone", "")
    
    dados_api = buscar_dados_completos(telefone)
    
    if dados_api and ("dados" in dados_api or "resultado" in dados_api or isinstance(dados_api, dict)):
        # Extrai o primeiro registro para a prévia mascarada
        lista_dados = dados_api.get("dados", dados_api.get("resultado", [dados_api]))
        if isinstance(lista_dados, list) and len(lista_dados) > 0:
            primeiro = lista_dados[0]
        else:
            primeiro = dados_api

        nome = primeiro.get("nome", "NÃO INFORMADO")
        cpf = primeiro.get("cpf", "***.***.***-**")
        operadora = primeiro.get("operadora", "VIVO / CLARO")

        # Formata registros para o pós-pagamento
        registros_formatados = []
        for item in (lista_dados if isinstance(lista_dados, list) else [primeiro]):
            registros_formatados.append({
                "nome": item.get("nome", "NÃO INFORMADO"),
                "cpf": item.get("cpf", "***.***.***-**"),
                "operadora": item.get("operadora", "NÃO INFORMADA"),
                "status": item.get("status", "Cadastro Ativo")
            })

        return {
            "status": "sucesso",
            "titular_parcial": nome,
            "cpf_parcial": cpf,
            "operadora": operadora,
            "registros": registros_formatados
        }
    else:
        raise HTTPException(status_code=404, detail="Número não encontrado na base de dados.")

# ----------------------------------------------------
# GERAR PIX (PUSHIN PAY)
# ----------------------------------------------------
@app.post("/api/gerar-pix")
@app.post("/gerar-pix")
@app.post("/api/criar-pix")
@app.post("/criar-pix")
async def gerar_pix(request: Request):
    data = await request.json()
    telefone = data.get("telefone", "")
    tipo = data.get("tipo", "consulta")
    
    valor_centavos = 490 if tipo == "pdf" else 1290

    headers = {
        "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "value": valor_centavos,
        "webhook_url": "https://descobrezap.com.br/api/webhook-pix"
    }

    try:
        response = requests.post("https://api.pushinpay.com.br/api/pix/cashIn", json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            res_data = response.json()
            txid = str(res_data.get("id"))
            qr_code = res_data.get("qr_code")
            qr_code_base64 = res_data.get("qr_code_base64")

            PAGAMENTOS_CACHE[txid] = {
                "status": "pending",
                "telefone": telefone,
                "tipo": tipo
            }

            return {
                "status": "sucesso",
                "pix_copia_cola": qr_code,
                "qr_code": qr_code,
                "qr_code_base64": qr_code_base64,
                "txid": txid
            }
        else:
            print(f"Erro Pushin Pay ({response.status_code}): {response.text}")
            raise HTTPException(status_code=400, detail="Erro ao gerar cobrança Pix na intermediadora.")
    except Exception as e:
        print(f"Exceção Pix: {str(e)}")
        raise HTTPException(status_code=500, detail="Falha na comunicação com gateway de pagamento.")

# ----------------------------------------------------
# CHECAR STATUS DO PAGAMENTO POR TXID
# ----------------------------------------------------
@app.get("/api/checar-status/{txid}")
@app.get("/checar-status/{txid}")
async def checar_status(txid: str):
    headers = {
        "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
        "Accept": "application/json"
    }
    try:
        response = requests.get(f"https://api.pushinpay.com.br/api/pix/cashIn/{txid}", headers=headers, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            status_api = res_data.get("status", "").lower()
            if status_api in ["paid", "approved", "concluido"]:
                PAGAMENTOS_CACHE[txid] = PAGAMENTOS_CACHE.get(txid, {})
                PAGAMENTOS_CACHE[txid]["status"] = "paid"
    except Exception as e:
        print(f"Erro ao checar status do TXID na Pushin Pay: {str(e)}")

    info = PAGAMENTOS_CACHE.get(txid, {})
    if info.get("status") == "paid":
        telefone = info.get("telefone", "")
        dados_api = buscar_dados_completos(telefone) if telefone else None
        
        registros_formatados = []
        if dados_api:
            lista_dados = dados_api.get("dados", dados_api.get("resultado", [dados_api]))
            for item in (lista_dados if isinstance(lista_dados, list) else [dados_api]):
                registros_formatados.append({
                    "nome": item.get("nome", "NÃO INFORMADO"),
                    "cpf": item.get("cpf", "***.***.***-**"),
                    "operadora": item.get("operadora", "NÃO INFORMADA"),
                    "status": item.get("status", "Liberado")
                })
        
        return {
            "status": "pago",
            "registros": registros_formatados
        }
    
    return {"status": "pendente"}

# ----------------------------------------------------
# WEBHOOK PIX
# ----------------------------------------------------
@app.post("/api/webhook-pix")
@app.post("/webhook-pix")
async def webhook_pix(request: Request):
    try:
        data = await request.json()
        status = str(data.get("status", "")).lower()
        txid = str(data.get("id") or data.get("txid", ""))

        if status in ["paid", "approved", "concluido"]:
            if txid in PAGAMENTOS_CACHE:
                PAGAMENTOS_CACHE[txid]["status"] = "paid"
            else:
                PAGAMENTOS_CACHE[txid] = {"status": "paid", "telefone": data.get("telefone", "")}

        return {"status": "ok"}
    except Exception as e:
        print(f"Erro no Webhook: {str(e)}")
        return {"status": "erro", "detalhe": str(e)}

# ----------------------------------------------------
# FORMULÁRIO DE SAC
# ----------------------------------------------------
@app.post("/api/sac")
@app.post("/sac")
async def enviar_sac(request: Request):
    data = await request.json()
    nome = data.get("nome")
    email_cliente = data.get("email") or data.get("contato")
    mensagem = data.get("mensagem")

    if not nome or not email_cliente or not mensagem:
        raise HTTPException(status_code=400, detail="Preencha todos os campos do formulário.")

    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = f"Novo Contato SAC - DescobreZap ({nome})"

        corpo = f"Nome: {nome}\nContato do Cliente: {email_cliente}\nNúmero Pesquisado: {data.get('numero_pesquisado', 'N/A')}\n\nMensagem:\n{mensagem}"
        msg.attach(MIMEText(corpo, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()

        return {"status": "sucesso", "mensagem": "Mensagem enviada com sucesso!"}
    except Exception as e:
        print(f"Erro ao enviar e-mail: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao enviar e-mail.")
