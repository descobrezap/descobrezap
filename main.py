import os
import json
import urllib.parse
import urllib.request
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Descobre Zap API")

# Libera o acesso para o seu frontend interagir com a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token do Pushin Pay
PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "70634|7PHvOzg8JQAqCodw1Vh1XgEWx92KpSPG5TVvvQhi423c8a77")


# 1. ROTA PRINCIPAL DA PÁGINA INICIAL
@app.api_route("/", methods=["GET", "HEAD"])
async def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "online", "message": "API Descobre Zap rodando"}


# 2. ROTA DE CONSULTA SIMULADA DO TELEFONE
@app.post("/api/buscar-previa")
@app.post("/buscar-previa")
async def consultar():
    return {
        "status": "sucesso",
        "nome_parcial": "MARCOS A*** S****"
    }


# 3. ROTA DE GERAÇÃO DO PIX DE 12,90 REAIS (PUSHIN PAY)
@app.post("/api/gerar-pix")
@app.post("/gerar_pix")
async def gerar_pix():
    if not PUSHIN_PAY_TOKEN:
        return JSONResponse(
            status_code=400,
            content={
                "status": "erro",
                "mensagem": "Token do Pushin Pay não configurado."
            }
        )

    try:
        # Valor em centavos: R$ 12,90 -> 1290
        payload = json.dumps({
            "value": 1290,
            "webhook_url": "https://descobrezap.com.br/webhook/pushinpay"
        }).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        req = urllib.request.Request(
            "https://api.pushinpay.com.br/api/pix/cashIn",
            data=payload,
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            data = json.loads(res_body)

        # Pega o código Pix Copia e Cola e a imagem do QR Code
        raw_qr_code = data.get("qr_code_text") or data.get("pix_copia_e_cola") or data.get("qr_code", "")
        raw_base64 = data.get("qr_code_base64") or data.get("qr_code", "")

        # Formata a imagem em Base64 nativa para a tag <img> do HTML
        formatted_base64 = raw_base64
        if raw_base64 and not raw_base64.startswith("data:image") and not raw_base64.startswith("http"):
            formatted_base64 = f"data:image/png;base64,{raw_base64}"

        # Se não vier a imagem pronta, gera a imagem via API do QR Code usando o texto do Pix
        if not formatted_base64 or formatted_base64 == raw_qr_code:
            encoded_pix = urllib.parse.quote(raw_qr_code)
            formatted_base64 = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_pix}"

        return {
            "status": "sucesso",
            "qr_code_img": formatted_base64,
            "pix_copia_cola": raw_qr_code
        }

    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8") if e.fp else str(e)
        return JSONResponse(
            status_code=400,
            content={
                "status": "erro",
                "mensagem": f"Erro ao processar pagamento no Pushin Pay: {error_content}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "erro",
                "mensagem": str(e)
            }
        )


# 4. ROTA DE WEBHOOK (RECEBIMENTO DA CONFIRMAÇÃO DE PAGAMENTO)
@app.post("/webhook/pushinpay")
async def pushinpay_webhook(request: Request):
    try:
        data = await request.json()
        status = data.get("status")
        pix_id = data.get("id")

        if status in ["paid", "approved", "completed"]:
            print(f"Pagamento Pix {pix_id} aprovado com sucesso!")
            return {"status": "sucesso", "mensagem": "Pagamento confirmado"}

        return {"status": "ignorado"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "erro", "mensagem": str(e)})
