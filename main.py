import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Descobre Zap - API Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUSHIN_PAY_TOKEN = "70634|7PHvOzg8JQAqCodw1Vh1XgEWx92KpSPG5TVvvQhi423c8a77"

# Configuração de E-mail nativo (Gmail SMTP)
GMAIL_USER = "descobrezap@gmail.com"
GMAIL_APP_PASS = "pfzh sxln wgnm tkxj"

pedidos_db = {}

class ConsultaRequest(BaseModel):
    telefone: str

class GerarPixRequest(BaseModel):
    telefone: str
    tipo: str = "consulta"

class SacRequest(BaseModel):
    nome: str
    contato: str
    numero_pesquisado: str = ""
    motivo: str = ""
    mensagem: str

@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "API rodando."}

@app.post("/api/previa")
def obter_previa(payload: ConsultaRequest):
    tel_limpo = "".join(filter(str.isdigit, payload.telefone))
    
    if len(tel_limpo) < 10 or len(tel_limpo) > 11:
        raise HTTPException(status_code=400, detail="Número de telefone inválido.")
    
    ddd = tel_limpo[:2]
    
    return {
        "status": "sucesso",
        "localizado": True,
        "ddd": ddd,
        "operadora_estimada": "VIVO / CLARO / TIM",
        "mensagem": "Registro localizado no banco de dados regional."
    }

@app.post("/api/gerar-pix")
def gerar_pix(payload: GerarPixRequest):
    tel_limpo = "".join(filter(str.isdigit, payload.telefone))
    valor_centavos = 1290 if payload.tipo == "consulta" else 490
    
    headers = {
        "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    body = {
        "value": valor_centavos,
        "webhook_url": "https://descobrezap.onrender.com/api/webhook-pushinpay"
    }
    
    try:
        response = requests.post("https://api.pushinpay.com.br/api/pix/cashIn", json=body, headers=headers)
        res_data = response.json()
        
        if response.status_code in [200, 201]:
            tx_id = res_data.get("id") or f"ZAP_{tel_limpo}"
            pedidos_db[tx_id] = {
                "telefone": tel_limpo,
                "tipo": payload.tipo,
                "pago": False
            }
            return {
                "status": "sucesso",
                "txid": tx_id,
                "qr_code_base64": res_data.get("qr_code_base64") or res_data.get("qr_code"),
                "pix_copia_cola": res_data.get("qr_code") or res_data.get("pix_copy_paste")
            }
        else:
            raise HTTPException(status_code=400, detail="Erro ao gerar Pix na Pushin Pay.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/webhook-pushinpay")
async def webhook_pushinpay(request: Request):
    dados = await request.json()
    txid = dados.get("id") or dados.get("txid")
    status_pagamento = dados.get("status")
    
    if status_pagamento in ["paid", "approved"] and txid in pedidos_db:
        pedidos_db[txid]["pago"] = True
        
    return {"status": "recebido"}

@app.get("/api/checar-status/{txid}")
def checar_status(txid: str):
    pedido = pedidos_db.get(txid)
    
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    
    if pedido.get("pago"):
        return {
            "status": "pago",
            "registros": [
                {
                    "nome": "MARIA SILVA DE OLIVEIRA",
                    "cpf": "***.452.890-**",
                    "operadora": "VIVO",
                    "status": "Titular Atual / Cadastro Ativo"
                }
            ]
        }
    
    return {"status": "aguardando_pagamento"}

# Rota para receber formulário de SAC e enviar por e-mail para descobrezap@gmail.com
@app.post("/api/enviar-sac")
def enviar_sac(payload: SacRequest):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = f"[SAC Descobre Zap] Nova mensagem de {payload.nome}"

        corpo_email = f"""
        NOVA MENSAGEM RECEBIDA PELO SAC DO SITE

        Nome: {payload.nome}
        Contato (WhatsApp/E-mail): {payload.contato}
        Número Pesquisado: {payload.numero_pesquisado if payload.numero_pesquisado else 'Não informado'}
        Motivo Selecionado: {payload.motivo if payload.motivo else 'Geral'}

        Mensagem do Cliente:
        -----------------------------------------
        {payload.mensagem}
        -----------------------------------------
        """
        
        msg.attach(MIMEText(corpo_email, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.send_message(msg)
        server.quit()

        return {"status": "sucesso", "mensagem": "E-mail enviado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar e-mail: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
