import subprocess
import time
import psycopg2
from datetime import datetime, timezone

def run_cmd(cmd):
    print(f"> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result

print("============================================================")
print("  TESTE DE BACKUP FÍSICO E PITR (Point-In-Time Recovery)    ")
print("============================================================")


run_cmd('docker exec bookinghub_db rm -rf /backup/basebackup')

print("\n1. Executando pg_basebackup...")
run_cmd('docker exec bookinghub_db pg_basebackup -U booking -D /backup/basebackup -Fp -Xs -P')

print("\n2. Inserindo registro (A) APÓS o base backup...")
conn = psycopg2.connect("postgresql://booking:secret@localhost:5433/bookinghub")
cur = conn.cursor()
cur.execute("INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) VALUES (1, 1, 'PITR-A', 'confirmed') RETURNING id")
conn.commit()

time.sleep(2)
cur.execute("SELECT current_timestamp;")
target_time = cur.fetchone()[0]
target_time_str = target_time.strftime('%Y-%m-%d %H:%M:%S.%f%z')
print(f"   [PONTO DE RESTAURAÇÃO] target_time definido para: {target_time_str}")

print("\n3. Inserindo registro (B) APÓS o ponto de restauração (será perdido)...")
cur.execute("INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) VALUES (1, 1, 'PITR-B', 'confirmed') RETURNING id")
conn.commit()
cur.close()
conn.close()

print("\n4. Simulando falha abrupta (docker stop --time=0)...")
run_cmd('docker stop --time=0 bookinghub_db')

print("\n5. Restaurando basebackup...")

vol_name = "projetofinalbd_pgdata"


run_cmd(f'docker run --rm -v {vol_name}:/var/lib/postgresql/data -v "%cd%\\backup:/backup" alpine sh -c "rm -rf /var/lib/postgresql/data/* && cp -a /backup/basebackup/* /var/lib/postgresql/data/ && chown -R 999:999 /var/lib/postgresql/data"')

print("\n6. Configurando arquivos de recuperação (postgresql.auto.conf e touch recovery.signal)...")

cmd_config = f"echo restore_command = 'cp /wal_archive/%f %p' >> /var/lib/postgresql/data/postgresql.auto.conf && echo recovery_target_time = '{target_time_str}' >> /var/lib/postgresql/data/postgresql.auto.conf && echo recovery_target_action = 'promote' >> /var/lib/postgresql/data/postgresql.auto.conf && touch /var/lib/postgresql/data/recovery.signal && chown 999:999 /var/lib/postgresql/data/recovery.signal /var/lib/postgresql/data/postgresql.auto.conf"
run_cmd(f'docker run --rm -v {vol_name}:/var/lib/postgresql/data alpine sh -c "{cmd_config}"')

print("\n7. Reiniciando o container...")
run_cmd('docker start bookinghub_db')


print("   Aguardando o PostgreSQL subir e realizar o recovery (10s)...")
time.sleep(10)
run_cmd('docker compose logs db --tail 15')

print("\n8. Comprovando que o registro A foi recuperado e B não (PITR funcionou)...")
try:
    conn = psycopg2.connect("postgresql://booking:secret@localhost:5433/bookinghub")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM flight_reservations WHERE seat_number = 'PITR-A'")
    count_a = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM flight_reservations WHERE seat_number = 'PITR-B'")
    count_b = cur.fetchone()[0]

    print(f"   Registro PITR-A (Antes do target_time): {count_a} encontrado(s)")
    print(f"   Registro PITR-B (Depois do target_time): {count_b} encontrado(s)")
    
    if count_a == 1 and count_b == 0:
        print("\n[SUCESSO] Point-In-Time Recovery executado com sucesso!")
    else:
        print("\n[FALHA] Os dados não estão no estado esperado.")
    
except Exception as e:
    print(f"Erro ao conectar no banco restaurado: {e}")

print("============================================================")
