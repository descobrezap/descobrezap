# ----------------------------------------------------
# CONSULTA DE DADOS (APIBRASIL)
# ----------------------------------------------------
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
        print(f"Resposta APIBrasil ({response.status_code}): {response.text}") # Log para ver o retorno no terminal
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Exceção APIBrasil: {str(e)}")
        return None

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
            # Tenta pegar a lista de registros de diferentes estruturas comuns de resposta
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

        # Fallback caso a API responda 200 mas sem registros específicos
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
