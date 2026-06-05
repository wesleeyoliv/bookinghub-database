"""
benchmark_consultas.py
BookingHub -- Parte 1: Processamento de Consultas

Script de benchmark que:
1. Dropa todos os índices criados
2. Mede o tempo médio de cada consulta SEM índices (5 execuções)
3. Captura EXPLAIN (ANALYZE, BUFFERS) SEM índices e salva em arquivo
4. Cria todos os índices
5. Mede o tempo médio de cada consulta COM índices (5 execuções)
6. Captura EXPLAIN (ANALYZE, BUFFERS) COM índices e salva em arquivo
7. Imprime tabela comparativa final
"""

import psycopg2
import time
import os


DSN = "dbname=bookinghub user=booking password=secret host=localhost port=5432"
REPETICOES = 5         
PLANOS_DIR = os.path.join(os.path.dirname(__file__), "planos")
os.makedirs(PLANOS_DIR, exist_ok=True)


CONSULTAS = {
    "C1": {
        "nome": "Voos disponíveis com filtro",
        "sql": """
            SELECT f.id, f.flight_number, f.departure_time, f.arrival_time,
                   f.available_seats, f.price,
                   a1.code AS origin, a2.code AS destination
            FROM flights f
            JOIN airports a1 ON a1.id = f.origin_airport_id
            JOIN airports a2 ON a2.id = f.destination_airport_id
            WHERE a1.city = 'São Paulo'
              AND a2.city = 'Rio de Janeiro'
              AND f.departure_time BETWEEN '2024-12-20' AND '2024-12-31'
              AND f.available_seats > 0
            ORDER BY f.departure_time
        """
    },
    "C2": {
        "nome": "Taxa de ocupação por voo",
        "sql": """
            SELECT f.flight_number,
                   COUNT(fr.id) AS total_reservas,
                   f.total_seats,
                   ROUND(COUNT(fr.id)::numeric / f.total_seats * 100, 2) AS ocupacao_pct
            FROM flights f
            LEFT JOIN flight_reservations fr ON fr.flight_id = f.id
              AND fr.status = 'confirmed'
            WHERE f.departure_time >= NOW() - INTERVAL '30 days'
            GROUP BY f.id, f.flight_number, f.total_seats
            ORDER BY ocupacao_pct DESC
            LIMIT 20
        """
    },
    "C3": {
        "nome": "Quartos disponíveis (sem conflito de datas)",
        "sql": """
            SELECT r.id, r.room_number, r.type, r.price_per_night
            FROM rooms r
            WHERE r.hotel_id = 1
              AND r.id NOT IN (
                SELECT hr.room_id FROM hotel_reservations hr
                WHERE hr.status != 'cancelled'
                  AND hr.check_in  < '2025-01-10'
                  AND hr.check_out > '2025-01-05'
              )
        """
    },
    "C4": {
        "nome": "Histórico completo do cliente",
        "sql": """
            SELECT 'voo' AS tipo,
                   fr.id AS reserva_id,
                   f.flight_number AS descricao,
                   f.departure_time AS data,
                   fr.status,
                   p.amount
            FROM flight_reservations fr
            JOIN flights f ON f.id = fr.flight_id
            LEFT JOIN payments p ON p.reservation_id = fr.id
              AND p.reservation_type = 'flight'
            WHERE fr.customer_id = 1
            UNION ALL
            SELECT 'hotel', hr.id, h.name, hr.check_in::timestamp,
                   hr.status, p.amount
            FROM hotel_reservations hr
            JOIN rooms r ON r.id = hr.room_id
            JOIN hotels h ON h.id = r.hotel_id
            LEFT JOIN payments p ON p.reservation_id = hr.id
              AND p.reservation_type = 'hotel'
            WHERE hr.customer_id = 1
            ORDER BY data DESC
        """
    }
}


INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_airports_city             ON airports(city)",
    """CREATE INDEX IF NOT EXISTS idx_flights_departure_seats
        ON flights(departure_time, available_seats)
        WHERE available_seats > 0""",
    "CREATE INDEX IF NOT EXISTS idx_flights_origin            ON flights(origin_airport_id)",
    "CREATE INDEX IF NOT EXISTS idx_flights_destination       ON flights(destination_airport_id)",
    "CREATE INDEX IF NOT EXISTS idx_fr_flight_status          ON flight_reservations(flight_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_flights_departure         ON flights(departure_time)",
    "CREATE INDEX IF NOT EXISTS idx_hr_room_dates             ON hotel_reservations(room_id, status, check_in, check_out)",
    "CREATE INDEX IF NOT EXISTS idx_rooms_hotel               ON rooms(hotel_id)",
    "CREATE INDEX IF NOT EXISTS idx_fr_customer               ON flight_reservations(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_hr_customer               ON hotel_reservations(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_res              ON payments(reservation_id, reservation_type)",
]

NOMES_INDICES = [
    "idx_airports_city",
    "idx_flights_departure_seats",
    "idx_flights_origin",
    "idx_flights_destination",
    "idx_fr_flight_status",
    "idx_flights_departure",
    "idx_hr_room_dates",
    "idx_rooms_hotel",
    "idx_fr_customer",
    "idx_hr_customer",
    "idx_payments_res",
]



def dropar_indices(cur):
    print("\n[→] Removendo índices...")
    for nome in NOMES_INDICES:
        cur.execute(f"DROP INDEX IF EXISTS {nome}")
    print("    Índices removidos.")


def criar_indices(cur):
    print("\n[→] Criando índices...")
    for ddl in INDICES:
        cur.execute(ddl)
    print("    Índices criados.")


def medir_tempo_medio(cur, sql, repeticoes=REPETICOES):
    """Executa a consulta N vezes e retorna o tempo médio em ms."""
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        fim = time.perf_counter()
        tempos.append((fim - inicio) * 1000)
    return sum(tempos) / len(tempos)


def capturar_plano(cur, sql):
    """Retorna o EXPLAIN (ANALYZE, BUFFERS) como string."""
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)\n{sql}"
    cur.execute(explain_sql)
    linhas = cur.fetchall()
    return "\n".join(row[0] for row in linhas)


def salvar_plano(nome_consulta, fase, plano):
    """Salva o plano de execução em arquivo texto."""
    nome_arquivo = os.path.join(PLANOS_DIR, f"{nome_consulta}_{fase}.txt")
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write(plano)
    print(f"    Plano salvo em: {nome_arquivo}")


def imprimir_tabela(resultados):
    """Imprime a tabela comparativa final."""
    print("\n" + "=" * 80)
    print("TABELA COMPARATIVA — Parte 1: Processamento de Consultas")
    print("=" * 80)
    cabecalho = f"{'Consulta':<6} {'Descrição':<40} {'Sem Índice':>12} {'Com Índice':>12} {'Speedup':>10}"
    print(cabecalho)
    print("-" * 80)
    for consulta, dados in resultados.items():
        sem  = dados["sem_indice"]
        com  = dados["com_indice"]
        speedup = sem / com if com > 0 else float("inf")
        desc = CONSULTAS[consulta]["nome"]
        print(f"{consulta:<6} {desc:<40} {sem:>11.3f}ms {com:>11.3f}ms {speedup:>9.1f}x")
    print("=" * 80)
    print(f"* Média de {REPETICOES} execuções por consulta")
    print()




def main():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()

    resultados = {}

   
    dropar_indices(cur)
    print("\n[FASE 1] Medindo tempos SEM índices...")

    for codigo, dados in CONSULTAS.items():
        print(f"\n  → {codigo}: {dados['nome']}")

       
        plano = capturar_plano(cur, dados["sql"])
        salvar_plano(codigo, "sem_indice", plano)

      
        tempo = medir_tempo_medio(cur, dados["sql"])
        print(f"     Tempo médio ({REPETICOES} execuções): {tempo:.3f} ms")
        resultados[codigo] = {"sem_indice": tempo}

   
    criar_indices(cur)
    
    print("\n[→] Executando ANALYZE para atualizar estatísticas...")
    cur.execute("ANALYZE")

    print("\n[FASE 2] Medindo tempos COM índices...")

    for codigo, dados in CONSULTAS.items():
        print(f"\n  → {codigo}: {dados['nome']}")

       
        plano = capturar_plano(cur, dados["sql"])
        salvar_plano(codigo, "com_indice", plano)

   
        tempo = medir_tempo_medio(cur, dados["sql"])
        print(f"     Tempo médio ({REPETICOES} execuções): {tempo:.3f} ms")
        resultados[codigo]["com_indice"] = tempo

   
    imprimir_tabela(resultados)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
