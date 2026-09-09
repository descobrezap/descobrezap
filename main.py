import os
import requests
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

APIBRASIL_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcC5hcGlicmFzaWwuaW8vYXBpL3YyL2F1dGgvbG9naW4iLCJpYXQiOjE3ODg5OTQ3MTUsImV4cCI6MTgyMDUzMDcxNSwibmJmIjoxNzg4OTk0NzE1LCJqdGkiOiIxMkhtMk9YR2Q4d3JDTjdzIiwic3ViIjoiNjAzMzMiLCJzZWFyY2giOiIwMThhNGRjOC1lMDQ5LTQ5MzQtOTlhOS1mYWUwMTFhZmQ2NDcifQ.QaLq6W3H-GfXtxgncytiM3sRRef2bJownImyqf3ZXDQ"

def buscar_dados_completos(telefone: str):
    """
    Função disparada somente após a confirmação de pagamento do Pix (R$ 12,90).
    Consulta a APIBrasil e retorna Nome, CPF, Endereço e Parentes.
    """
    # Remove caracteres não numéricos
    phone_clean = "".join(filter(str.isdigit, telefone))
    
    url = "https://app.apibrasil.io/api/v2/dados/telefone"
    headers = {
        "Authorization": f"Bearer {APIBRASIL_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "phone": phone_clean
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro APIBrasil: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exceção ao consultar APIBrasil: {str(e)}")
        return None
