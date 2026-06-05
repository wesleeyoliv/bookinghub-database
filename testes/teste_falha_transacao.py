import urllib.request
import urllib.error
import psycopg2

print("============================================================")
print("  TESTE DE FALHA DE TRANSAÇÃO (ROLLBACK) — PARTE 3  ")
print("============================================================")

print("\n1. Contando reservas no banco ANTES da chamada...")
conn = psycopg2.connect("postgresql://booking:secret@localhost:5433/bookinghub")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM flight_reservations WHERE seat_number = 'FAIL'")
antes = cur.fetchone()[0]
print(f"Reservas com seat_number='FAIL': {antes}")

print("\n2. Chamando endpoint POST /test/falha-transacao (simula erro)...")
req = urllib.request.Request("http://localhost:8001/test/falha-transacao", method="POST")
try:
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.getcode())
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print("Status Code:", e.code)
    print("Response:", e.read().decode())

print("\n3. Contando reservas no banco APÓS a chamada...")
cur.execute("SELECT COUNT(*) FROM flight_reservations WHERE seat_number = 'FAIL'")
depois = cur.fetchone()[0]
print(f"Reservas com seat_number='FAIL': {depois}")

if antes == 0 and depois == 0:
    print("\n[SUCESSO] O ROLLBACK automático funcionou! O registro não foi persistido.")
else:
    print("\n[FALHA] O registro vazou para o banco de dados!")

cur.close()
conn.close()
