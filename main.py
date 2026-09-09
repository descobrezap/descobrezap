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
# CREDENCIAIS E TOKENS
# ----------------------------------------------------
APIBRASIL_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcC5hcGlicmFzaWwuaW8vYXBpL3YyL2F1dGgvbG9naW4iLCJpYXQiOjE3ODg5OTQ3MTUsImV4cCI6MTgyMDUzMDcxNSwibmJmIjoxNzg4OTk0NzE1LCJqdGkiOiIxMkhtMk9YR2Q4d3JDTjdzIiwic3ViIjoiNjAzMzMiLCJzZWFyY2giOiIwMThhNGRjOC1lMDQ5LTQ5MzQtOTlhOS1mYWUwMTFhZmQ2NDcifQ.QaLq6W3H-GfXtxgncytiM3sRRef2bJownImyqf3ZXDQ"

# Token do Pushin Pay para geração do Pix
PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "SEU_TOKEN_PUSHIN_PAY_AQUI")

GMAIL_USER = "descobrezap@gmail.com"
GMAIL_APP_PASS = "pfzh sxln wgnm tkxj"

# ----------------------------------------------------
# SERVIR O SITE (INDEX.HTML E ESTÁTICOS)
# ----------------------------------------------------
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("index.html")

# ----------------------------------------------------
# CONSULTA DE DADOS (APIBRASIL)
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

# ----------------------------------------------------
# GERAR PIX (PUSHIN PAY)
# ----------------------------------------------------
@app.post("/api/criar-pix")
@app.post("/criar-pix")
async def criar_pix(request: Request):
    data = await request.json()
    telefone = data.get("telefone", "")
    
    # Valor fixo de 12,90 reais (convertido para 1290 centavos)
    valor_centavos = 1290

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
            return {
                "status": "sucesso",
                "qr_code": res_data.get("qr_code"),
                "qr_code_base64": res_data.get("qr_code_base64"),
                "txid": res_data.get("id")
            }
        else:
            print(f"Erro Pushin Pay ({response.status_code}): {response.text}")
            raise HTTPException(status_code=400, detail="Erro ao gerar cobrança Pix na intermediadora.")
    except Exception as e:
        print(f"Exceção Pix: {str(e)}")
        raise HTTPException(status_code=500, detail="Falha na comunicação com gateway de pagamento.")

# ----------------------------------------------------
# WEBHOOK PIX (CONFIRMAÇÃO DE PAGAMENTO)
# ----------------------------------------------------
@app.post("/api/webhook-pix")
@app.post("/webhook-pix")
async def webhook_pix(request: Request):
    data = await request.json()
    status = data.get("status")
    
    if status in ["paid", "PAID", "approved"]:
        telefone = data.get("telefone", "")
        if telefone:
            dados = buscar_dados_completos(telefone)
            # Lógica para entregar o relatório completo ao cliente
    return {"status": "ok"}

# ----------------------------------------------------
# FORMULÁRIO DE SAC (ENVIO DE E-MAIL VIA GMAIL)
# ----------------------------------------------------
@app.post("/api/sac")
async def enviar_sac(request: Request):
    data = await request.json()
    nome = data.get("nome")
    email_cliente = data.get("email")
    mensagem = data.get("mensagem")

    if not nome or not email_cliente or not mensagem:
        raise HTTPException(status_code=400, detail="Preencha todos os campos do formulário.")

    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = f"Novo Contato SAC - DescobreZap ({nome})"

        corpo = f"Nome: {nome}\nE-mail do Cliente: {email_cliente}\n\nMensagem:\n{mensagem}"
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
