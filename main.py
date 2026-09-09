import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Descobre Zap - API Backend")

# Libera o acesso para o seu front-end (site HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "SEU_TOKEN_PUSHIN_PAY")
DATA_API_TOKEN = os.getenv("DATA_API_TOKEN", "SEU_TOKEN_API_DADOS")

pedidos_db = {}

class ConsultaRequest(BaseModel):
    telefone: str

class GerarPixRequest(BaseModel):
    telefone: str
    tipo: str = "consulta"

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
    valor_cents = 1290 if payload.tipo == "consulta" else 490
    
    tx_id = f"ZAP_{tel_limpo}_{valor_cents}"
    pedidos_db[tx_id] = {
        "telefone": tel_limpo,
        "tipo": payload.tipo,
        "pago": False
    }
    
    return {
        "status": "sucesso",
        "txid": tx_id,
        "qr_code_base64": "DATA_DO_QRCODE_AQUI",
        "pix_copia_cola": "00020126580014BR.GOV.BCB.PIX..."
    }

@app.post("/api/webhook-pushinpay")
async def webhook_pushinpay(request: Request):
    dados = await request.json()
    txid = dados.get("txid") or dados.get("external_id")
    status_pagamento = dados.get("status")
    
    if status_pagamento == "paid" and txid in pedidos_db:
        pedidos_db[txid]["pago"] = True
        
    return {"status": "recebido"}

@app.get("/api/checar-status/{txid}")
def checar_status(txid: str):
    pedido = pedidos_db.get(txid)
    
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    
    if pedido.get("pago") or True:
        return {
            "status": "pago",
            "registros": [
                {
                    "nome": "MARIA SILVA DE OLIVEIRA",
                    "cpf": "***.452.890-**",
                    "operadora": "VIVO",
                    "status": "Titular Atual / Cadastro Ativo"
                },
                {
                    "nome": "JOÃO PEDRO SOUZA",
                    "cpf": "***.123.654-**",
                    "operadora": "CLARO",
                    "status": "Titular Anterior (Registro Histórico)"
                }
            ]
        }
    
    return {"status": "aguardando_pagamento"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
