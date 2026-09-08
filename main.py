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

# Token do Mercado Pago vindo da variável de ambiente no Render
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
            content={
                "erro": "Token do Mercado Pago não configurado no Render.",
                "message": "Token do Mercado Pago não configurado no Render.",
                "detail": "Token do Mercado Pago não configurado no Render."
            }
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
                content={
                    "erro": f"Erro Mercado Pago: {msg_erro}",
                    "message": f"Erro Mercado Pago: {msg_erro}",
                    "detail": f"Erro Mercado Pago: {msg_erro}"
                }
            )

        point_of_interaction = payment.get("point_of_interaction", {})
        transaction_data = point_of_interaction.get("transaction_data", {})

        qr_code = transaction_data.get("qr_code")
        qr_code_base64 = transaction_data.get("qr_code_base64")
        ticket_url = transaction_data.get("ticket_url")

        return {
            "status": "sucesso",
            "id": payment.get("id"),
            "qr_code": qr_code,
            "pix_code": qr_code,
            "qr_code_base64": qr_code_base64,
            "ticket_url": ticket_url,
            "payment": payment
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "erro": str(e),
                "message": str(e),
                "detail": str(e)
            }
        )
