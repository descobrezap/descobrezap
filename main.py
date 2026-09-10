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
# Os valores reais devem ser configurados no Render
# em Environment Variables.
# ----------------------------------------------------
APIBRASIL_TOKEN = os.getenv("APIBRASIL_TOKEN", "")
PUSHIN_PAY_TOKEN = os.getenv("PUSHIN_PAY_TOKEN", "")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS", "")

# Cache em memória para controle dos pagamentos por TXID
PAGAMENTOS_CACHE = {}

# ----------------------------------------------------
# SERVIR O SITE (INDEX.HTML E ESTÁTICOS)
# ----------------------------------------------------
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("index.html")


# ----------------------------------------------------
# CONSULTA DE DADOS REAIS (APIBRASIL)
# ----------------------------------------------------
def buscar_dados_completos(telefone: str):
    phone_clean = "".join(filter(str.isdigit, telefone))

    if len(phone_clean) in [10, 11]:
        phone_clean = "55" + phone_clean

    url = "https://app.apibrasil.io/api/v2/dados/telefone"

    headers = {
        "Authorization": f"Bearer {APIBRASIL_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "phone": phone_clean
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

        return None

    except Exception:
        return None


# ----------------------------------------------------
# CONSULTAR TELEFONE
# ----------------------------------------------------
@app.post("/api/consultar-telefone")
@app.post("/consultar-telefone")
async def consultar_telefone(request: Request):
    try:
        body = await request.json()
        telefone = body.get("telefone", "")
    except Exception:
        telefone = ""

    if not telefone:
        raise HTTPException(
            status_code=400,
            detail="Telefone não informado."
        )

    dados_api = buscar_dados_completos(telefone)

    if not dados_api:
        raise HTTPException(
            status_code=404,
            detail="Número não encontrado na base de dados."
        )

    # A API Brasil pode retornar os dados dentro de
    # "dados", "resultado" ou diretamente como objeto.
    if isinstance(dados_api, dict):
        lista_dados = dados_api.get(
            "dados",
            dados_api.get("resultado", [dados_api])
        )
    else:
        lista_dados = []

    if not isinstance(lista_dados, list):
        lista_dados = [lista_dados]

    if len(lista_dados) == 0:
        raise HTTPException(
            status_code=404,
            detail="Número não encontrado na base de dados."
        )

    primeiro = lista_dados[0]

    if not isinstance(primeiro, dict):
        raise HTTPException(
            status_code=404,
            detail="Dados inválidos retornados pela API."
        )

    nome = primeiro.get("nome", "NÃO INFORMADO")
    cpf = primeiro.get("cpf", "***.***.***-**")
    operadora = primeiro.get("operadora", "NÃO INFORMADA")

    registros_formatados = []

    for item in lista_dados:
        if not isinstance(item, dict):
            continue

        registros_formatados.append({
            "nome": item.get("nome", "NÃO INFORMADO"),
            "cpf": item.get("cpf", "***.***.***-**"),
            "operadora": item.get("operadora", "NÃO INFORMADA"),
            "status": item.get("status", "Cadastro Ativo")
        })

    if len(registros_formatados) == 0:
        raise HTTPException(
            status_code=404,
            detail="Nenhum registro válido encontrado."
        )

    return {
        "status": "sucesso",
        "titular_parcial": nome,
        "cpf_parcial": cpf,
        "operadora": operadora,
        "registros": registros_formatados
    }


# ----------------------------------------------------
# GERAR PIX (PUSHIN PAY)
# ----------------------------------------------------
@app.post("/api/gerar-pix")
@app.post("/gerar-pix")
@app.post("/api/criar-pix")
@app.post("/criar-pix")
async def gerar_pix(request: Request):

    data = await request.json()

    telefone = data.get("telefone", "")
    tipo = data.get("tipo", "consulta")

    # Consulta completa: R$ 12,90
    # PDF: R$ 4,90
    valor_centavos = 490 if tipo == "pdf" else 1290

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
        response = requests.post(
            "https://api.pushinpay.com.br/api/pix/cashIn",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=400,
                detail="Erro ao gerar cobrança Pix."
            )

        res_data = response.json()

        txid = str(res_data.get("id", ""))
        qr_code = res_data.get("qr_code")
        qr_code_base64 = res_data.get("qr_code_base64")

        if not txid:
            raise HTTPException(
                status_code=500,
                detail="Gateway não retornou o identificador da cobrança."
            )

        PAGAMENTOS_CACHE[txid] = {
            "status": "pending",
            "telefone": telefone,
            "tipo": tipo
        }

        return {
            "status": "sucesso",
            "pix_copia_cola": qr_code,
            "qr_code": qr_code,
            "qr_code_base64": qr_code_base64,
            "txid": txid
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Falha na comunicação com gateway."
        )


# ----------------------------------------------------
# CHECAR STATUS DO PAGAMENTO POR TXID
# ----------------------------------------------------
@app.get("/api/checar-status/{txid}")
@app.get("/checar-status/{txid}")
async def checar_status(txid: str):

    headers = {
        "Authorization": f"Bearer {PUSHIN_PAY_TOKEN}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            f"https://api.pushinpay.com.br/api/pix/cashIn/{txid}",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:

            res_data = response.json()

            status_api = str(
                res_data.get("status", "")
            ).lower()

            if status_api in [
                "paid",
                "approved",
                "concluido"
            ]:
                PAGAMENTOS_CACHE[txid] = PAGAMENTOS_CACHE.get(
                    txid,
                    {}
                )

                PAGAMENTOS_CACHE[txid]["status"] = "paid"

    except Exception:
        pass

    info = PAGAMENTOS_CACHE.get(txid, {})

    if info.get("status") == "paid":

        telefone = info.get("telefone", "")

        dados_api = (
            buscar_dados_completos(telefone)
            if telefone
            else None
        )

        registros_formatados = []

        if dados_api and isinstance(dados_api, dict):

            lista_dados = dados_api.get(
                "dados",
                dados_api.get("resultado", [dados_api])
            )

            if not isinstance(lista_dados, list):
                lista_dados = [lista_dados]

            for item in lista_dados:

                if not isinstance(item, dict):
                    continue

                registros_formatados.append({
                    "nome": item.get(
                        "nome",
                        "NÃO INFORMADO"
                    ),
                    "cpf": item.get(
                        "cpf",
                        "***.***.***-**"
                    ),
                    "operadora": item.get(
                        "operadora",
                        "NÃO INFORMADA"
                    ),
                    "status": item.get(
                        "status",
                        "Liberado"
                    )
                })

        return {
            "status": "pago",
            "registros": registros_formatados
        }

    return {
        "status": "pendente"
    }


# ----------------------------------------------------
# WEBHOOK PIX
# ----------------------------------------------------
@app.post("/api/webhook-pix")
@app.post("/webhook-pix")
async def webhook_pix(request: Request):

    try:

        data = await request.json()

        status = str(
            data.get("status", "")
        ).lower()

        txid = str(
            data.get("id") or
            data.get("txid", "")
        )

        if status in [
            "paid",
            "approved",
            "concluido"
        ]:

            if txid in PAGAMENTOS_CACHE:

                PAGAMENTOS_CACHE[txid]["status"] = "paid"

            else:

                PAGAMENTOS_CACHE[txid] = {
                    "status": "paid",
                    "telefone": data.get(
                        "telefone",
                        ""
                    )
                }

        return {
            "status": "ok"
        }

    except Exception as e:

        return {
            "status": "erro",
            "detalhe": str(e)
        }


# ----------------------------------------------------
# FORMULÁRIO DE SAC
# ----------------------------------------------------
@app.post("/api/sac")
@app.post("/sac")
async def enviar_sac(request: Request):

    data = await request.json()

    nome = data.get("nome")
    email_cliente = data.get("email") or data.get("contato")
    mensagem = data.get("mensagem")

    if not nome or not email_cliente or not mensagem:
        raise HTTPException(
            status_code=400,
            detail="Preencha todos os campos."
        )

    if not GMAIL_USER or not GMAIL_APP_PASS:
        raise HTTPException(
            status_code=500,
            detail="E-mail de suporte não configurado."
        )

    try:

        msg = MIMEMultipart()

        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        msg["Subject"] = (
            f"Novo Contato SAC - DescobreZap ({nome})"
        )

        corpo = (
            f"Nome: {nome}\n"
            f"Contato: {email_cliente}\n"
            f"Número: "
            f"{data.get('numero_pesquisado', 'N/A')}"
            f"\n\n"
            f"Mensagem:\n"
            f"{mensagem}"
        )

        msg.attach(
            MIMEText(corpo, "plain")
        )

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587
        )

        server.starttls()

        server.login(
            GMAIL_USER,
            GMAIL_APP_PASS
        )

        server.sendmail(
            GMAIL_USER,
            GMAIL_USER,
            msg.as_string()
        )

        server.quit()

        return {
            "status": "sucesso",
            "mensagem": "Enviado com sucesso!"
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Erro ao enviar e-mail."
        )
