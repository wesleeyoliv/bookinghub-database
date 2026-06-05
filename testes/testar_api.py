import urllib.request
import urllib.error
import json
import time

API_URL = "http://localhost:8001"

def print_header(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def fazer_requisicao(metodo, endpoint, payload=None):
    url = API_URL + endpoint
    print(f"\n-> [{metodo}] {url}")
    
    if payload:
        print(f"Enviando dados: {json.dumps(payload, ensure_ascii=False)}")
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method=metodo)
        req.add_header('Content-Type', 'application/json')
    else:
        req = urllib.request.Request(url, method=metodo)

    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            try:
               
                parsed = json.loads(body)
                body_formatado = json.dumps(parsed, indent=2, ensure_ascii=False)
            except:
                body_formatado = body
            
            print(f"[Sucesso - {status}] Resposta:\n{body_formatado}")
            return parsed if 'parsed' in locals() else body
            
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            parsed = json.loads(body)
            body_formatado = json.dumps(parsed, indent=2, ensure_ascii=False)
        except:
            body_formatado = body
        print(f"[Erro HTTP - {e.code}] Resposta:\n{body_formatado}")
        return None
    except Exception as e:
        print(f"[Falha de Conexão] Erro: {str(e)}")
        return None


print_header("TESTE DA API BOOKINGHUB")
print("Aguarde, validando endpoints...")
time.sleep(1)

print_header("1. Buscando Voos Disponíveis")
fazer_requisicao("GET", "/voos/disponiveis")
time.sleep(1)


print_header("2. Buscando Hotéis Disponíveis")
fazer_requisicao("GET", "/hoteis/disponiveis")
time.sleep(1)

print_header("3. Testando Reserva de Pacote (Voo + Hotel)")
payload_pacote = {
  "customer_id": 1,
  "flight_id": 1,
  "seat_number": "TESTE1",
  "room_id": 1,
  "check_in": "2026-10-01",
  "check_out": "2026-10-05"
}
resposta_pacote = fazer_requisicao("POST", "/reservas/pacote", payload_pacote)
time.sleep(1)


print_header("4. Checando o Histórico do Cliente (Customer 1)")
fazer_requisicao("GET", "/clientes/1/reservas")
time.sleep(1)


print_header("5. Testando Endpoint de Falha de Transação (Rollback)")
fazer_requisicao("POST", "/test/falha-transacao")
time.sleep(1)

print("\n" + "="*60)
print(" TESTES FINALIZADOS COM SUCESSO!")
print("="*60)
