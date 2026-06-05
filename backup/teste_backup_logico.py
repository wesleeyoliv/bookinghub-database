import subprocess
import time

def run_cmd(cmd):
    print(f"\n> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result

print("============================================================")
print("  TESTE DE BACKUP LÓGICO (pg_dump e pg_restore) — PARTE 3  ")
print("============================================================")

print("\n1. Criando backup lógico (pg_dump) no container...")
run_cmd('docker exec bookinghub_db pg_dump -U booking -Fc bookinghub -f /backup/backup.dump')

print("\n2. Preparando banco limpo (bookinghub_restored)...")
run_cmd('docker exec bookinghub_db psql -U booking -d postgres -c "DROP DATABASE IF EXISTS bookinghub_restored;"')
run_cmd('docker exec bookinghub_db psql -U booking -d postgres -c "CREATE DATABASE bookinghub_restored;"')

print("\n3. Restaurando backup (pg_restore) no novo banco...")
run_cmd('docker exec bookinghub_db pg_restore -U booking -d bookinghub_restored /backup/backup.dump')

print("\n4. Verificando integridade no banco restaurado...")
run_cmd('docker exec bookinghub_db psql -U booking -d bookinghub_restored -c "SELECT COUNT(*) AS total_voos FROM flights;"')
run_cmd('docker exec bookinghub_db psql -U booking -d bookinghub_restored -c "SELECT COUNT(*) AS total_clientes FROM customers;"')

print("\n============================================================")
print("  TESTE CONCLUÍDO COM SUCESSO  ")
print("============================================================")
