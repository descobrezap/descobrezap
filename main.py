import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests

app = FastAPI(title="Descobre Zap - Sistema de Identificação")

MERCADO_PAGO_TOKEN = os.getenv("MERCADO_PAGO_TOKEN", "SUA_ACCESS_TOKEN_AQUI")

class ConsultaRequest(BaseModel):
    telefone: str

class PixRequest(BaseModel):
    telefone: str

def mascarar_nome(nome_completo: str) -> str:
    partes = nome_completo.strip().split()
    if len(partes) == 1:
        return partes[0][0] + "***"
    
    primeiro = partes[0]
    ultimo = partes[-1]
    
    meio_mascarado = []
    for p in partes[1:-1]:
        if len(p) <= 3:
            meio_mascarado.append(p)
        else:
            meio_mascarado.append(p[0] + ".")
            
    ultimo_mascarado = ultimo[0] + "*" * (len(ultimo) - 1)
    
    return f"{primeiro} {' '.join(meio_mascarado)} {ultimo_mascarado}".strip()

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/buscar-previa")
def buscar_previa(req: ConsultaRequest):
    numero_limpo = re.sub(r'\D', '', req.telefone)
    
    if len(numero_limpo) < 10 or len(numero_limpo) > 11:
        raise HTTPException(status_code=400, detail="Número de telefone inválido.")

    nome_exemplo = "Carlos Eduardo da Silva"
    nome_parcial = mascarar_nome(nome_exemplo)

    return {
        "status": "sucesso",
        "telefone_formatado": req.telefone,
        "nome_parcial": nome_parcial,
        "dados_bloqueados": {
            "cpf": "🔒 ***." + numero_limpo[3:6] + ".***-**",
            "operadora": "🔒 Bloqueado (Disponível no relatório)",
            "regiao": "🔒 Bloqueado (Disponível no relatório)",
            "whatsapp_status": "🔒 Foto e Status Ativos"
        }
    }

@app.post("/api/gerar-pix")
def gerar_pix(req: PixRequest):
    headers = {
        "Authorization": f"Bearer {MERCADO_PAGO_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "transaction_amount": 12.90,
    "description": "Consulta Descobre Zap",
    "payment_method_id": "pix",
    "payer": {
        "email": "cliente@descobrezap.com.br",
        "first_name": "Cliente",
        "last_name": "Zap"
        }
    }

    try:
        res = requests.post("https://api.mercadopago.com/v1/payments", json=payload, headers=headers)
        data = res.json()
        
        if res.status_code in [200, 201]:
            qr_code = data["point_of_interaction"]["transaction_data"]["qr_code"]
            qr_code_base64 = data["point_of_interaction"]["transaction_data"]["qr_code_base64"]
            payment_id = data["id"]
            
            return {
                "status": "sucesso",
                "payment_id": payment_id,
                "pix_copia_cola": qr_code,
                "qr_code_img": f"data:image/png;base64,{qr_code_base64}",
                "valor": "9 reais e 90 centavos"
            }
        else:
            return {"status": "erro", "mensagem": "Erro ao gerar cobrança no Mercado Pago."}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}
