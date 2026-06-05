"""
teste_conflito_hotel.py
BookingHub — Parte 2: Controle de Concorrência
Demonstra prevenção de double booking de quartos de hotel
"""

import psycopg2
import threading

DSN = "dbname=bookinghub user=booking password=secret host=localhost port=5433"
ROOM_ID    = 1
CHECK_IN   = "2025-08-01"
CHECK_OUT  = "2025-08-05"
NUM_THREADS = 20

lock_print = threading.Lock()


def log(msg):
    with lock_print:
        print(msg)


def limpar_reservas_teste():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM hotel_reservations WHERE room_id = %s "
        "AND check_in = %s AND check_out = %s",
        (ROOM_ID, CHECK_IN, CHECK_OUT)
    )
    cur.close(); conn.close()


def contar_reservas():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM hotel_reservations "
        "WHERE room_id = %s AND check_in = %s AND check_out = %s AND status != 'cancelled'",
        (ROOM_ID, CHECK_IN, CHECK_OUT)
    )
    total = cur.fetchone()[0]
    cur.close(); conn.close()
    return total


def tentar_reservar(customer_id, resultados):
    try:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()

       
        cur.execute(
            "SELECT id, price_per_night FROM rooms WHERE id = %s FOR UPDATE",
            (ROOM_ID,)
        )
        quarto = cur.fetchone()
        if not quarto:
            conn.rollback()
            with lock_print: resultados.append("ERRO")
            return

      
        cur.execute(
            "SELECT id FROM hotel_reservations "
            "WHERE room_id = %s AND status != 'cancelled' "
            "AND check_in < %s AND check_out > %s",
            (ROOM_ID, CHECK_OUT, CHECK_IN)
        )
        conflito = cur.fetchone()

        if conflito:
            conn.rollback()
            with lock_print: resultados.append("NEGADO")
            log(f"  Thread {customer_id:02d}: NEGADO (conflito de datas)")
            return

        preco = float(quarto[1]) * 4 
        cur.execute(
            "INSERT INTO hotel_reservations "
            "(customer_id, room_id, check_in, check_out, status, total_price) "
            "VALUES (%s, %s, %s, %s, 'confirmed', %s)",
            (customer_id, ROOM_ID, CHECK_IN, CHECK_OUT, preco)
        )
        conn.commit()
        with lock_print: resultados.append("SUCESSO")
        log(f"  Thread {customer_id:02d}: SUCESSO (reserva criada)")

    except Exception as e:
        try: conn.rollback()
        except: pass
        with lock_print: resultados.append("ERRO")
        log(f"  Thread {customer_id:02d}: ERRO — {e}")
    finally:
        try: cur.close(); conn.close()
        except: pass


def main():
    print("=" * 60)
    print("TESTE DE CONFLITO DE DATAS — BookingHub Parte 2")
    print("=" * 60)
    print(f"\n  Quarto: {ROOM_ID} | Período: {CHECK_IN} a {CHECK_OUT}")
    print(f"  Disparando {NUM_THREADS} threads simultâneas...\n")

    limpar_reservas_teste()

    resultados = []
    threads = [
        threading.Thread(target=tentar_reservar, args=(i, resultados))
        for i in range(1, NUM_THREADS + 1)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    total_reservas = contar_reservas()

    print(f"\n  --- RESULTADO ---")
    print(f"  Reservas criadas (SUCESSO): {resultados.count('SUCESSO')}")
    print(f"  Conflitos (NEGADO):         {resultados.count('NEGADO')}")
    print(f"  Erros:                      {resultados.count('ERRO')}")
    print(f"  Reservas no banco:          {total_reservas}")

    if total_reservas == 1:
        print(f"  *** DOUBLE BOOKING PREVENIDO! Apenas 1 reserva para {NUM_THREADS} tentativas ***")
    else:
        print(f"  FALHA: {total_reservas} reservas para o mesmo período!")

    print("=" * 60)


if __name__ == "__main__":
    main()
