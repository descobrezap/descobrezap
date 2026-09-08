import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import mercadopago

app = FastAPI(title="Descobre Zap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MP_TOKEN = os.getenv("MERCADO_PAGO_TOKEN", "")
sdk = mercadopago.SDK(MP_TOKEN) if MP_TOKEN else None


# 1. ROTA PRINCIPAL
@app.api_route("/", methods=["GET", "HEAD"])
async def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "online"}


# 2. ROTA DE CONSULTA
@app.post("/api/buscar-previa")
@app.post("/buscar-previa")
@app.post("/consultar")
@app.post("/api/consultar")
async def consultar():
    return {
        "status": "sucesso",
        "sucesso": True,
        "encontrado": True,
        "titular": "Identificado",
        "nome": "Identificado",
        "dados": {"encontrado": True}
    }


# 3. ROTA DE GERAÇÃO DO PIX (12,90 REAIS)
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

        # Formata a string Base64 para ser usada diretamente em tags <img>
        formatted_base64 = raw_base64
        if raw_base64 and not raw_base64.startswith("data:image"):
            formatted_base64 = f"data:image/png;base64,{raw_base64}"

        # Se o frontend preferir buscar via API externa de QR Code usando o texto do Pix
        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={raw_qr_code}" if raw_qr_code else ""

        # Dicionário completo com todas as variações conhecidas de chaves
        dados_pix = {
            "status": "sucesso",
            "sucesso": True,
            "id": payment.get("id"),
            # Textos para Copia e Cola
            "pix_code": raw_qr_code,
            "qr_code": raw_qr_code,
            "copia_e_cola": raw_qr_code,
            "pix_copia_e_cola": raw_qr_code,
            "code": raw_qr_code,
            "payload": raw_qr_code,
            "point_of_interaction": point_of_interaction,
            # URLs e Imagens do QR Code
            "qr_code_base64": formatted_base64,
            "imagem": formatted_base64,
            "imagem_qrcode": formatted_base64,
            "qrcode": formatted_base64,
            "qr_code_url": qr_api_url,
            "image_url": qr_api_url,
            "url_qrcode": qr_api_url,
            "ticket_url": ticket_url,
            # Estruturas aninhadas para frontends que procuram em "data" ou "dados"
            "dados": {
                "pix_code": raw_qr_code,
                "qr_code": raw_qr_code,
                "copia_e_cola": raw_qr_code,
                "qr_code_base64": formatted_base64,
                "imagem": formatted_base64,
                "qr_code_url": qr_api_url,
                "image_url": qr_api_url
            },
            "data": {
                "pix_code": raw_qr_code,
                "qr_code": raw_qr_code,
                "copia_e_cola": raw_qr_code,
                "qr_code_base64": formatted_base64,
                "imagem": formatted_base64,
                "qr_code_url": qr_api_url,
                "image_url": qr_api_url
            }
        }

        return dados_pix

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"erro": str(e)}
        )
