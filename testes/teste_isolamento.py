"""
teste_isolamento.py
BookingHub — Parte 2: Níveis de Isolamento
Demonstra READ COMMITTED, REPEATABLE READ e SERIALIZABLE
com duas sessões paralelas usando threading
"""

import psycopg2
import threading
import time

DSN = "dbname=bookinghub user=booking password=secret host=localhost port=5433"
FLIGHT_ID = 2


def sep(titulo):
    print("\n" + "=" * 60)
    print(f"  {titulo}")
    print("=" * 60)



def cenario1_read_committed():
    sep("CENÁRIO 1 — READ COMMITTED: Non-Repeatable Read")
    print("""
  Objetivo: mostrar que T2 vê valores DIFERENTES na mesma
  coluna em duas leituras dentro da mesma transação,
  porque T1 commitou entre as duas leituras de T2.
""")

    e_t1_atualizou  = threading.Event()
    e_t2_leu_1      = threading.Event()
    e_t1_commitou   = threading.Event()
    results = {}

    
    conn0 = psycopg2.connect(DSN)
    conn0.autocommit = True
    conn0.cursor().execute("UPDATE flights SET available_seats = 10 WHERE id = %s", (FLIGHT_ID,))
    conn0.close()

    def sessao_t1():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute("UPDATE flights SET available_seats = 99 WHERE id = %s", (FLIGHT_ID,))
        print("  [T1] UPDATE available_seats = 99 (ainda não commitou)")
        e_t1_atualizou.set()
        e_t2_leu_1.wait()
        conn.commit()
        print("  [T1] COMMIT")
        e_t1_commitou.set()
        cur.close(); conn.close()

    def sessao_t2():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("BEGIN")
        e_t1_atualizou.wait()
        cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
        leitura1 = cur.fetchone()[0]
        results['leitura1'] = leitura1
        print(f"  [T2] Leitura 1: available_seats = {leitura1}  (T1 ainda não commitou)")
        e_t2_leu_1.set()
        e_t1_commitou.wait()
        time.sleep(0.05)
        cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
        leitura2 = cur.fetchone()[0]
        results['leitura2'] = leitura2
        print(f"  [T2] Leitura 2: available_seats = {leitura2}  (T1 já commitou)")
        conn.commit()
        cur.close(); conn.close()

    t1 = threading.Thread(target=sessao_t1)
    t2 = threading.Thread(target=sessao_t2)
    t1.start(); t2.start()
    t1.join(); t2.join()

    print(f"""
  --- RESULTADO ---
  Leitura 1 (antes do commit de T1): {results.get('leitura1')}
  Leitura 2 (após  o commit de T1):  {results.get('leitura2')}
  Non-Repeatable Read: {"SIM ✓" if results.get('leitura1') != results.get('leitura2') else "NÃO (timing)"}

  Explicação MVCC: em READ COMMITTED, cada comando SQL
  enxerga o snapshot mais recente commitado no momento
  em que o comando começa — por isso T2 vê valores
  diferentes nas duas leituras.
""")
    return results



def cenario2_repeatable_read():
    sep("CENÁRIO 2 — REPEATABLE READ: Non-Repeatable Read eliminado")
    print("""
  Objetivo: mostrar que T2 vê o MESMO valor nas duas
  leituras, mesmo após o commit de T1, porque o snapshot
  é fixado no início da transação.
""")

    e_t1_atualizou  = threading.Event()
    e_t2_leu_1      = threading.Event()
    e_t1_commitou   = threading.Event()
    results = {}

    conn0 = psycopg2.connect(DSN)
    conn0.autocommit = True
    conn0.cursor().execute("UPDATE flights SET available_seats = 10 WHERE id = %s", (FLIGHT_ID,))
    conn0.close()

    def sessao_t1():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("BEGIN")
        cur.execute("UPDATE flights SET available_seats = 77 WHERE id = %s", (FLIGHT_ID,))
        print("  [T1] UPDATE available_seats = 77 (ainda não commitou)")
        e_t1_atualizou.set()
        e_t2_leu_1.wait()
        conn.commit()
        print("  [T1] COMMIT")
        e_t1_commitou.set()
        cur.close(); conn.close()

    def sessao_t2():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        e_t1_atualizou.wait()
        cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
        leitura1 = cur.fetchone()[0]
        results['leitura1'] = leitura1
        print(f"  [T2] Leitura 1: available_seats = {leitura1}  (snapshot fixado no início)")
        e_t2_leu_1.set()
        e_t1_commitou.wait()
        time.sleep(0.05)
        cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
        leitura2 = cur.fetchone()[0]
        results['leitura2'] = leitura2
        print(f"  [T2] Leitura 2: available_seats = {leitura2}  (mesmo snapshot — T1 invisível)")
        conn.commit()
        cur.close(); conn.close()

    t1 = threading.Thread(target=sessao_t1)
    t2 = threading.Thread(target=sessao_t2)
    t1.start(); t2.start()
    t1.join(); t2.join()

    print(f"""
  --- RESULTADO ---
  Leitura 1 (antes do commit de T1): {results.get('leitura1')}
  Leitura 2 (após  o commit de T1):  {results.get('leitura2')}
  Non-Repeatable Read eliminado: {"SIM ✓" if results.get('leitura1') == results.get('leitura2') else "NÃO"}

  Explicação MVCC: em REPEATABLE READ, o snapshot é
  fixado quando a transação começa. T2 continua vendo
  os dados como eram no início da sua transação,
  independente de commits de outras transações.
""")
    return results



def cenario3_serializable():
    sep("CENÁRIO 3 — SERIALIZABLE: Serialization Failure")
    print("""
  Objetivo: mostrar que o PostgreSQL aborta uma transação
  quando detecta dependência cíclica que violaria a
  execução serial. Erro: ERROR 40001 serialization_failure.
""")

    e_ambos_leram   = threading.Barrier(2)
    e_t1_insertou   = threading.Event()
    results = {'t1': None, 't2': None}

    def sessao_t1():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            cur.execute(
                "SELECT COUNT(*) FROM flight_reservations WHERE flight_id = %s",
                (FLIGHT_ID,)
            )
            contagem = cur.fetchone()[0]
            print(f"  [T1] SELECT COUNT(*) = {contagem}")
            e_ambos_leram.wait()  
            cur.execute(
                "INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) "
                "VALUES (1, %s, 'SER1', 'confirmed')",
                (FLIGHT_ID,)
            )
            print(f"  [T1] INSERT executado")
            e_t1_insertou.set()
            conn.commit()
            print(f"  [T1] COMMIT — sucesso")
            results['t1'] = "COMMIT OK"
        except psycopg2.errors.SerializationFailure as e:
            conn.rollback()
            print(f"  [T1] ROLLBACK — serialization_failure: {e}")
            results['t1'] = f"ROLLBACK: {e}"
        except Exception as e:
            conn.rollback()
            results['t1'] = f"ERRO: {e}"
        finally:
            cur.close(); conn.close()

    def sessao_t2():
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            cur.execute(
                "SELECT COUNT(*) FROM flight_reservations WHERE flight_id = %s",
                (FLIGHT_ID,)
            )
            contagem = cur.fetchone()[0]
            print(f"  [T2] SELECT COUNT(*) = {contagem}")
            e_ambos_leram.wait()  
            e_t1_insertou.wait()  
            time.sleep(0.1)
            cur.execute(
                "INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) "
                "VALUES (2, %s, 'SER2', 'confirmed')",
                (FLIGHT_ID,)
            )
            print(f"  [T2] INSERT executado")
            conn.commit()
            print(f"  [T2] COMMIT — sucesso")
            results['t2'] = "COMMIT OK"
        except psycopg2.errors.SerializationFailure as e:
            conn.rollback()
            msg = str(e).strip().split('\n')[0]
            print(f"  [T2] ROLLBACK — serialization_failure: {msg}")
            results['t2'] = f"ROLLBACK: {msg}"
        except Exception as e:
            conn.rollback()
            results['t2'] = f"ERRO: {e}"
        finally:
            cur.close(); conn.close()


    conn0 = psycopg2.connect(DSN)
    conn0.autocommit = True
    conn0.cursor().execute(
        "DELETE FROM flight_reservations WHERE seat_number IN ('SER1','SER2')"
    )
    conn0.close()

    t1 = threading.Thread(target=sessao_t1)
    t2 = threading.Thread(target=sessao_t2)
    t1.start(); t2.start()
    t1.join(); t2.join()

    print(f"""
  --- RESULTADO ---
  T1: {results.get('t1')}
  T2: {results.get('t2')}

  Explicação MVCC: em SERIALIZABLE, o PostgreSQL usa
  SSI (Serializable Snapshot Isolation). Detecta que
  T1 e T2 leram o mesmo conjunto de linhas e ambas
  tentaram inserir — dependência cíclica que tornaria
  a execução não-serializável. Uma delas é abortada
  com erro 40001 (serialization_failure).
""")
    return results



def cenario4_savepoint():
    sep("CENÁRIO 4 — SAVEPOINT: Rollback parcial de transação")
    print("""
  Objetivo: demonstrar que ROLLBACK TO SAVEPOINT desfaz
  apenas parte de uma transação, preservando o restante.
""")

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")
        print("  BEGIN")

        cur.execute("SAVEPOINT sp_voo")
        print("  SAVEPOINT sp_voo")

        cur.execute(
            "INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) "
            "VALUES (1, %s, 'SVPT1', 'confirmed') RETURNING id",
            (FLIGHT_ID,)
        )
        id_voo = cur.fetchone()[0]
        print(f"  INSERT reserva de voo → id={id_voo}")

        cur.execute("SAVEPOINT sp_hotel")
        print("  SAVEPOINT sp_hotel")

        
        try:
            cur.execute(
                "INSERT INTO hotel_reservations "
                "(customer_id, room_id, check_in, check_out, status, total_price) "
                "VALUES (1, 1, '2025-09-10', '2025-09-05', 'confirmed', 500.00)"
            )
            print("  INSERT reserva de hotel — simulando falha...")
            raise Exception("Falha simulada: datas inválidas (check_in > check_out)")
        except Exception as e:
            print(f"  ERRO: {e}")
            cur.execute("ROLLBACK TO SAVEPOINT sp_hotel")
            print("  ROLLBACK TO SAVEPOINT sp_hotel (desfaz só o hotel)")


        cur.execute(
            "SELECT id, seat_number, status FROM flight_reservations "
            "WHERE seat_number = 'SVPT1'"
        )
        row = cur.fetchone()
        print(f"  SELECT reserva de voo após rollback parcial: id={row[0]}, "
              f"seat={row[1]}, status={row[2]}  ← ainda existe!")


        conn.rollback()
        print("  ROLLBACK (desfaz a transação inteira)")

        cur.execute(
            "SELECT COUNT(*) FROM flight_reservations WHERE seat_number = 'SVPT1'"
        )
        count = cur.fetchone()[0]
        print(f"  SELECT após ROLLBACK total: {count} registros  ← nada persistido")

    finally:
        cur.close(); conn.close()

    print("""
  --- RESULTADO ---
  O ROLLBACK TO SAVEPOINT sp_hotel desfez apenas a
  reserva de hotel, mantendo a reserva de voo ativa
  dentro da transação. O ROLLBACK final desfez tudo,
  garantindo atomicidade completa quando necessário.
""")



if __name__ == "__main__":
    cenario1_read_committed()
    cenario2_repeatable_read()
    cenario3_serializable()
    cenario4_savepoint()
    print("=" * 60)
    print("  TODOS OS CENÁRIOS CONCLUÍDOS")
    print("=" * 60)
