import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import mercadopago

app = FastAPI()

# Configuração de CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa o SDK do Mercado Pago
sdk = mercadopago.SDK(os.getenv("MERCADO_PAGO_TOKEN", ""))

# Aceita /gerar_pix e /api/gerar-pix
@app.post("/gerar_pix")
@app.post("/api/gerar-pix")
async def gerar_pix():
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
            error_msg = payment.get("message") or str(payment)
            raise HTTPException(
                status_code=400, 
                detail=f"Erro Mercado Pago: {error_msg}"
            )

        point_of_interaction = payment.get("point_of_interaction", {})
        transaction_data = point_of_interaction.get("transaction_data", {})

        return {
            "id": payment.get("id"),
            "qr_code": transaction_data.get("qr_code"),
            "qr_code_base64": transaction_data.get("qr_code_base64"),
            "status": payment.get("status")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Servir os arquivos estáticos da pasta frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
