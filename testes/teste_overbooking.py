"""
teste_overbooking.py
BookingHub — Parte 2: Controle de Concorrência
Demonstra o problema do overbooking SEM e COM SELECT FOR UPDATE
"""

import psycopg2
import threading
import time

DSN = "dbname=bookinghub user=booking password=secret host=localhost port=5433"
FLIGHT_ID = 1
VAGAS_INICIAIS = 5
NUM_THREADS = 20

lock_print = threading.Lock()



def log(msg):
    with lock_print:
        print(msg)


def resetar_voo():
    """Reseta o voo para VAGAS_INICIAIS assentos e remove reservas de teste."""
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("UPDATE flights SET available_seats = %s WHERE id = %s",
                (VAGAS_INICIAIS, FLIGHT_ID))
    cur.execute("DELETE FROM flight_reservations WHERE flight_id = %s AND seat_number LIKE %s",
                (FLIGHT_ID, 'TEST%'))
    cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
    vagas = cur.fetchone()[0]
    cur.close()
    conn.close()
    return vagas


def contar_reservas():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM flight_reservations WHERE flight_id = %s AND seat_number LIKE %s",
        (FLIGHT_ID, 'TEST%')
    )
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return total




def reservar_sem_lock(customer_id, resultados):
    try:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()

       
        cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
        vagas = cur.fetchone()[0]

        if vagas <= 0:
            conn.rollback()
            with lock_print:
                resultados.append("NEGADO")
            log(f"  Thread {customer_id:02d}: NEGADO (sem vagas)")
            return

        
        cur.execute(
            "INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) "
            "VALUES (%s, %s, %s, 'confirmed')",
            (customer_id, FLIGHT_ID, f"TEST{customer_id}")
        )
        cur.execute(
            "UPDATE flights SET available_seats = available_seats - 1 WHERE id = %s",
            (FLIGHT_ID,)
        )
        conn.commit()
        with lock_print:
            resultados.append("SUCESSO")
        log(f"  Thread {customer_id:02d}: SUCESSO (viu {vagas} vagas)")

    except Exception as e:
        try: conn.rollback()
        except: pass
        with lock_print:
            resultados.append("ERRO")
        log(f"  Thread {customer_id:02d}: ERRO — {e}")
    finally:
        try: cur.close(); conn.close()
        except: pass




def reservar_com_lock(customer_id, resultados):
    try:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        cur = conn.cursor()

       
        cur.execute(
            "SELECT available_seats FROM flights WHERE id = %s FOR UPDATE",
            (FLIGHT_ID,)
        )
        vagas = cur.fetchone()[0]

        if vagas <= 0:
            conn.rollback()
            with lock_print:
                resultados.append("NEGADO")
            log(f"  Thread {customer_id:02d}: NEGADO (sem vagas)")
            return

        cur.execute(
            "INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) "
            "VALUES (%s, %s, %s, 'confirmed')",
            (customer_id, FLIGHT_ID, f"TEST{customer_id}")
        )
        cur.execute(
            "UPDATE flights SET available_seats = available_seats - 1 WHERE id = %s",
            (FLIGHT_ID,)
        )
        conn.commit()
        with lock_print:
            resultados.append("SUCESSO")
        log(f"  Thread {customer_id:02d}: SUCESSO (viu {vagas} vagas)")

    except Exception as e:
        try: conn.rollback()
        except: pass
        with lock_print:
            resultados.append("ERRO")
        log(f"  Thread {customer_id:02d}: ERRO — {e}")
    finally:
        try: cur.close(); conn.close()
        except: pass




def main():
    print("=" * 60)
    print("TESTE DE OVERBOOKING — BookingHub Parte 2")
    print("=" * 60)

  
    print(f"\n[CENÁRIO A] SEM SELECT FOR UPDATE")
    vagas = resetar_voo()
    print(f"  Voo {FLIGHT_ID} resetado: {vagas} assentos disponíveis")
    print(f"  Disparando {NUM_THREADS} threads simultâneas...\n")

    resultados_a = []
    threads = [
        threading.Thread(target=reservar_sem_lock, args=(i, resultados_a))
        for i in range(1, NUM_THREADS + 1)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    reservas_a = contar_reservas()
    vagas_final_a = resetar_voo.__wrapped__(FLIGHT_ID) if hasattr(resetar_voo, '__wrapped__') else None

   
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
    vagas_pos_a = cur.fetchone()[0]
    cur.close(); conn.close()

    print(f"\n  --- RESULTADO CENÁRIO A ---")
    print(f"  Vagas iniciais:            {VAGAS_INICIAIS}")
    print(f"  Reservas criadas:          {resultados_a.count('SUCESSO')}")
    print(f"  Negadas:                   {resultados_a.count('NEGADO')}")
    print(f"  Reservas na tabela (TEST): {reservas_a}")
    print(f"  Vagas restantes no banco:  {vagas_pos_a}")
    if reservas_a > VAGAS_INICIAIS:
        print(f"  *** OVERBOOKING DETECTADO! {reservas_a} reservas para {VAGAS_INICIAIS} vagas ***")
    else:
        print(f"  Sem overbooking (possível por timing — aumente NUM_THREADS se necessário)")

   
    print(f"\n[CENÁRIO B] COM SELECT FOR UPDATE")
    vagas = resetar_voo()
    print(f"  Voo {FLIGHT_ID} resetado: {vagas} assentos disponíveis")
    print(f"  Disparando {NUM_THREADS} threads simultâneas...\n")

    resultados_b = []
    threads = [
        threading.Thread(target=reservar_com_lock, args=(i, resultados_b))
        for i in range(1, NUM_THREADS + 1)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    reservas_b = contar_reservas()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT available_seats FROM flights WHERE id = %s", (FLIGHT_ID,))
    vagas_pos_b = cur.fetchone()[0]
    cur.close(); conn.close()

    print(f"\n  --- RESULTADO CENÁRIO B ---")
    print(f"  Vagas iniciais:            {VAGAS_INICIAIS}")
    print(f"  Reservas criadas:          {resultados_b.count('SUCESSO')}")
    print(f"  Negadas:                   {resultados_b.count('NEGADO')}")
    print(f"  Reservas na tabela (TEST): {reservas_b}")
    print(f"  Vagas restantes no banco:  {vagas_pos_b}")
    if reservas_b <= VAGAS_INICIAIS:
        print(f"  *** OVERBOOKING PREVENIDO! Exatamente {reservas_b} reservas para {VAGAS_INICIAIS} vagas ***")
    else:
        print(f"  FALHA: overbooking ainda ocorreu!")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()