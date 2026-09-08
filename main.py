import os
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import mercadopago

app = FastAPI(title="Descobre Zap API")

# Libera o acesso para o seu frontend interagir com a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa o Mercado Pago via variável de ambiente do Render
MP_TOKEN = os.getenv("MERCADO_PAGO_TOKEN", "")
sdk = mercadopago.SDK(MP_TOKEN) if MP_TOKEN else None


# 1. ROTA PRINCIPAL DA PÁGINA INICIAL
@app.api_route("/", methods=["GET", "HEAD"])
async def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "online", "message": "API Descobre Zap rodando"}


# 2. ROTA DE CONSULTA SIMULADA DO TELEFONE
@app.post("/api/buscar-previa")
@app.post("/buscar-previa")
@app.post("/consultar")
@app.post("/api/consultar")
async def consultar():
    return {
        "status": "sucesso",
        "sucesso": True,
        "encontrado": True,
        "nome": "Titular Identificado",
        "titular": "Titular Identificado",
        "status_whatsapp": "Ativo",
        "mensagem": "Consulta realizada com sucesso",
        "dados": {
            "encontrado": True,
            "titular": "Titular Identificado",
            "nome": "Titular Identificado",
            "status_whatsapp": "Ativo"
        }
    }


# 3. ROTA DE GERAÇÃO DO PIX DE 12,90 REAIS
@app.post("/gerar_pix")
@app.post("/api/gerar-pix")
async def gerar_pix():
    if not MP_TOKEN:
        return JSONResponse(
            status_code=400,
            content={"erro": "Token do Mercado Pago não configurado no Render."}
        )

    try:
        payment_data = {
            "transaction_amount": 12.90,
            "description": "Consulta Descobre Zap",
            "payment_method_id": "pix",
            "payer": {
                "email": "cliente@descobrezap.com.br",
                "first_name": "Cliente",
                "last_name": "Zap"
            }
        }

        payment_response = sdk.payment().create(payment_data)
        payment = payment_response.get("response", {})

        if payment_response.get("status") not in [200, 201]:
            msg_erro = payment.get("message") or str(payment)
            return JSONResponse(
                status_code=400,
                content={"erro": f"Erro Mercado Pago: {msg_erro}"}
            )

        point_of_interaction = payment.get("point_of_interaction", {})
        transaction_data = point_of_interaction.get("transaction_data", {})

        raw_qr_code = transaction_data.get("qr_code", "")
        raw_base64 = transaction_data.get("qr_code_base64", "")
        ticket_url = transaction_data.get("ticket_url", "")

        # Formata a string Base64 para a tag <img>
        formatted_base64 = raw_base64
        if raw_base64 and not raw_base64.startswith("data:image"):
            formatted_base64 = f"data:image/png;base64,{raw_base64}"

        # Gera uma URL real e válida de imagem para o QR Code a partir do código do Pix
        encoded_pix = urllib.parse.quote(raw_qr_code)
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_pix}"

        return {
            "status": "sucesso",
            "sucesso": True,
            "id": payment.get("id"),
            
            # URLs reais da imagem do QR Code
            "qr_code_url": qr_code_url,
            "image_url": qr_code_url,
            "url_qrcode": qr_code_url,
            "imagem_url": qr_code_url,
            "qr_code_image": qr_code_url,
            "qrcode_url": qr_code_url,
            "ticket_url": ticket_url,
            
            # Imagem em formato Base64
            "qr_code_base64": formatted_base64,
            "imagem_qrcode": formatted_base64,
            "imagem": formatted_base64,
            "qrcode": formatted_base64,

            # Chaves do código Copia e Cola (Pix)
            "pix_code": raw_qr_code,
            "qr_code": raw_qr_code,
            "copia_e_cola": raw_qr_code,
            "pix_copia_e_cola": raw_qr_code,
            "payload": raw_qr_code,
            "code": raw_qr_code,

            # Estrutura dentro do objeto 'dados' para frontends aninhados
            "dados": {
                "pix_code": raw_qr_code,
                "qr_code": raw_qr_code,
                "copia_e_cola": raw_qr_code,
                "qr_code_url": qr_code_url,
                "image_url": qr_code_url,
                "imagem_url": qr_code_url,
                "qr_code_base64": formatted_base64,
                "imagem_qrcode": formatted_base64
            }
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"erro": str(e)}
        )
