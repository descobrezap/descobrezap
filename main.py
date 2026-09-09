import os
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 1. INICIALIZAÇÃO DO APP (Deve vir antes das rotas!)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. CONFIGURAÇÕES E TOKENS
PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "30932|p8kKk97R6gInFpGedR4cOQ0KThE94a8mS6D4A0x5e954e3d0")
APIBRASIL_TOKEN = os.getenv("APIBRASIL_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY3OTRjMzcxZWYzZDNjM2E0Y2M2YTZjMiIsImNsaWVudF9pZCI6IjY3OTRjMzcxZWYzZDNjM2E0Y2M2YTZjMiIsImVtYWlsIjoiZnJlZHJpY2suc29hcmVzLm5vZ3VlaXJhQGdtYWlsLmNvbSIsImlhdCI6MTczNzgzOTk4NX0.sE3C-4l9D4p3t3b3z_d7l6k5j4i3h2g1f0e9d8c7b6a")
BASE_URL = os.getenv("BASE_URL", "https://descobrezap.onrender.com")

PAGAMENTOS_CACHE = {}

# 3. FUNÇÕES AUXILIARES
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
        print(f"Resposta APIBrasil ({response.status_code}): {response.text}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Exceção APIBrasil: {str(e)}")
        return None

# 4. ROTAS DA APLICAÇÃO
@app.get("/")
def read_root():
    return {"status": "API Online"}

@app.post("/api/gerar-pix")
@app.post("/gerar-pix")
async def gerar_pix(payload: dict):
    phone = payload.get("telefone") or payload.get("phone", "")
    if not phone:
        return {"erro": "Telefone não informado"}

    # Valor mantido em 12,90 reais (1290 centavos)
    valor_em_centavos = 1290  

    headers = {
        "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    body = {
        "value": valor_em_centavos,
        "webhook_url": f"{BASE_URL}/api/webhook/pushinpay"
    }

    try:
        response = requests.post("https://api.pushinpay.com.br/api/pix/cashIn", json=body, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            data = response.json()
            txid = data.get("txid") or data.get("id")
            qr_code = data.get("qr_code") or data.get("qrcode") or data.get("pix_copy_paste")
            qr_code_base64 = data.get("qr_code_base64") or data.get("qrcode_base64")

            if txid:
                PAGAMENTOS_CACHE[txid] = {
                    "status": "pending",
                    "telefone": phone
                }

            return {
                "success": True,
                "txid": txid,
                "qr_code": qr_code,
                "qr_code_base64": qr_code_base64,
                "valor": "12,90"
            }
        else:
            print(f"Erro Pushin Pay ({response.status_code}): {response.text}")
            return {"erro": "Falha ao gerar o Pix na administradora."}
            
    except Exception as e:
        print(f"Exceção ao gerar Pix: {str(e)}")
        return {"erro": "Erro de conexão ao gerar o Pix."}

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
            status_api = str(res_data.get("status", "")).lower()
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
            lista_registros = dados_api.get("dados") or dados_api.get("response") or [dados_api]
            
            if isinstance(lista_registros, list):
                for item in lista_registros:
                    if isinstance(item, dict):
                        registros_formatados.append({
                            "nome": item.get("nome") or item.get("razasocial") or "NOME NÃO INFORMADO",
                            "cpf": item.get("cpf") or item.get("cnpj") or "***.***.***-**",
                            "operadora": item.get("operadora") or item.get("carrier") or "NÃO INFORMADA",
                            "status": item.get("status") or "Cadastro Localizado"
                        })
            elif isinstance(lista_registros, dict):
                registros_formatados.append({
                    "nome": lista_registros.get("nome", "NOME NÃO INFORMADO"),
                    "cpf": lista_registros.get("cpf", "***.***.***-**"),
                    "operadora": lista_registros.get("operadora", "NÃO INFORMADA"),
                    "status": lista_registros.get("status", "Cadastro Localizado")
                })

        if not registros_formatados:
            registros_formatados = [{
                "nome": "CONSULTA REALIZADA",
                "cpf": "***.***.***-**",
                "operadora": "OPERADORA VINCULADA",
                "status": "Relatório gerado com sucesso"
            }]

        return {
            "status": "pago",
            "registros": registros_formatados
        }
    
    return {"status": "pendente"}

@app.post("/api/webhook/pushinpay")
async def webhook_pushinpay(request: Request):
    try:
        data = await request.json()
        txid = data.get("txid") or data.get("id")
        status = str(data.get("status", "")).lower()

        if txid and status in ["paid", "approved", "concluido"]:
            PAGAMENTOS_CACHE[txid] = PAGAMENTOS_CACHE.get(txid, {})
            PAGAMENTOS_CACHE[txid]["status"] = "paid"
            
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/api/sac")
async def enviar_sac(payload: dict):
    nome = payload.get("nome")
    email = payload.get("email")
    mensagem = payload.get("mensagem")
    print(f"[SAC RECEBIDO] De: {nome} ({email}) - Mensagem: {mensagem}")
    return {"success": True, "mensagem": "Mensagem enviada com sucesso!"}
