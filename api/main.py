"""
api/main.py
BookingHub — API REST
FastAPI + psycopg2 (sem ORM — SQL puro)
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import date
from typing import Optional


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://booking:secret@localhost:5432/bookinghub"
)

app = FastAPI(
    title="BookingHub API",
    description="Plataforma de reservas de hotéis e passagens aéreas",
    version="1.0.0"
)


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


import time, random

def executar_com_retry(fn, max_tentativas=3):
    """
    Executa fn() com retry automático em caso de serialization_failure (40001).
    Backoff: 0.1s, 0.2s, 0.4s + jitter aleatório de até 50ms.
    """
    for tentativa in range(max_tentativas):
        try:
            return fn()
        except psycopg2.errors.SerializationFailure:
            if tentativa == max_tentativas - 1:
                raise
            espera = (2 ** tentativa) * 0.1 + random.uniform(0, 0.05)
            time.sleep(espera)



class ReservaVooRequest(BaseModel):
    customer_id: int
    flight_id: int
    seat_number: Optional[str] = None

class ReservaHotelRequest(BaseModel):
    customer_id: int
    room_id: int
    check_in: date
    check_out: date

class PagamentoRequest(BaseModel):
    reservation_type: str   
    reservation_id: int
    amount: float
    payment_method: str

class PacoteRequest(BaseModel):
    customer_id: int
    flight_id: int
    seat_number: Optional[str] = None
    room_id: int
    check_in: date
    check_out: date



@app.get("/voos/disponiveis", summary="Lista voos disponíveis com filtro")
def voos_disponiveis(
    origem:      Optional[str]  = Query(None, description="Cidade de origem (ex: São Paulo)"),
    destino:     Optional[str]  = Query(None, description="Cidade de destino (ex: Rio de Janeiro)"),
    data_inicio: Optional[date] = Query(None, description="Data de partida mínima (YYYY-MM-DD)"),
    data_fim:    Optional[date] = Query(None, description="Data de partida máxima (YYYY-MM-DD)"),
):
    """
    Consulta C1 — usa índices:
      - idx_flights_departure_seats (departure_time + available_seats)
      - idx_airports_city (city)
      - idx_flights_origin / idx_flights_destination (FKs para airports)
    """
    filtros = ["f.available_seats > 0"]
    params  = []

    if origem:
        filtros.append("a1.city = %s")
        params.append(origem)
    if destino:
        filtros.append("a2.city = %s")
        params.append(destino)
    if data_inicio:
        filtros.append("f.departure_time >= %s")
        params.append(data_inicio)
    if data_fim:
        filtros.append("f.departure_time <= %s")
        params.append(data_fim)

    where = "WHERE " + " AND ".join(filtros) if filtros else ""

    sql = f"""
        SELECT f.id, f.flight_number, f.departure_time, f.arrival_time,
               f.available_seats, f.price,
               a1.code AS origin_code, a1.city AS origin_city,
               a2.code AS destination_code, a2.city AS destination_city
        FROM flights f
        JOIN airports a1 ON a1.id = f.origin_airport_id
        JOIN airports a2 ON a2.id = f.destination_airport_id
        {where}
        ORDER BY f.departure_time
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()



@app.get("/hoteis/disponiveis", summary="Lista hotéis com quartos disponíveis")
def hoteis_disponiveis(
    hotel_id:  Optional[int]  = Query(None, description="ID do hotel (opcional)"),
    check_in:  Optional[date] = Query(None, description="Data de entrada (YYYY-MM-DD)"),
    check_out: Optional[date] = Query(None, description="Data de saída (YYYY-MM-DD)"),
):
    """
    Consulta C3 — usa índices:
      - idx_rooms_hotel (hotel_id)
      - idx_hr_room_dates (room_id, status, check_in, check_out) → Index Only Scan
    """
    filtros_room = []
    params       = []

    if hotel_id:
        filtros_room.append("r.hotel_id = %s")
        params.append(hotel_id)

    where_room = "WHERE " + " AND ".join(filtros_room) if filtros_room else ""

    
    subquery_conflito = ""
    if check_in and check_out:
        subquery_conflito = """
            AND r.id NOT IN (
                SELECT hr.room_id FROM hotel_reservations hr
                WHERE hr.status != 'cancelled'
                  AND hr.check_in  < %s
                  AND hr.check_out > %s
            )
        """
        params.extend([check_out, check_in])

    sql = f"""
        SELECT r.id, r.room_number, r.type, r.capacity,
               r.price_per_night, h.name AS hotel_name,
               h.city, h.stars
        FROM rooms r
        JOIN hotels h ON h.id = r.hotel_id
        {where_room}
        {subquery_conflito}
        ORDER BY r.price_per_night
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()



@app.get("/clientes/{customer_id}/reservas", summary="Histórico completo do cliente")
def reservas_cliente(customer_id: int):
    """
    Consulta C4 — usa índices:
      - idx_fr_customer (flight_reservations.customer_id) → Bitmap Index Scan
      - idx_hr_customer (hotel_reservations.customer_id)  → Bitmap Index Scan
      - idx_payments_res (reservation_id, reservation_type) → Index Scan
    """
    sql = """
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
        WHERE fr.customer_id = %s
        UNION ALL
        SELECT 'hotel', hr.id, h.name, hr.check_in::timestamp,
               hr.status, p.amount
        FROM hotel_reservations hr
        JOIN rooms r ON r.id = hr.room_id
        JOIN hotels h ON h.id = r.hotel_id
        LEFT JOIN payments p ON p.reservation_id = hr.id
          AND p.reservation_type = 'hotel'
        WHERE hr.customer_id = %s
        ORDER BY data DESC
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (customer_id, customer_id))
            resultado = cur.fetchall()

    if not resultado:
        raise HTTPException(status_code=404, detail="Cliente não encontrado ou sem reservas")
    return resultado



@app.get("/relatorios/ocupacao", summary="Taxa de ocupação por voo e por hotel")
def relatorio_ocupacao(
    dias: int = Query(30, description="Janela de tempo em dias (padrão: 30)")
):
    """
    Consulta C2 — usa índices:
      - idx_fr_flight_status (flight_id, status)
      - idx_flights_departure (departure_time)
    """
    sql = """
        SELECT f.flight_number,
               COUNT(fr.id) AS total_reservas,
               f.total_seats,
               ROUND(COUNT(fr.id)::numeric / f.total_seats * 100, 2) AS ocupacao_pct
        FROM flights f
        LEFT JOIN flight_reservations fr ON fr.flight_id = f.id
          AND fr.status = 'confirmed'
        WHERE f.departure_time >= NOW() - INTERVAL '1 day' * %s
        GROUP BY f.id, f.flight_number, f.total_seats
        ORDER BY ocupacao_pct DESC
        LIMIT 20
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (dias,))
            return cur.fetchall()



@app.post("/reservas/voo", status_code=201, summary="Cria reserva de voo")
def criar_reserva_voo(body: ReservaVooRequest):
    """
    Usa SELECT FOR UPDATE para garantir atomicidade entre verificação de
    assentos e decremento — evita overbooking em requisições concorrentes.
    """
    def _executar():
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                
                cur.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                
                cur.execute(
                    "SELECT id, available_seats FROM flights WHERE id = %s FOR UPDATE",
                    (body.flight_id,)
                )
                voo = cur.fetchone()

                if not voo:
                    raise HTTPException(status_code=404, detail="Voo não encontrado")
                if voo["available_seats"] <= 0:
                    raise HTTPException(status_code=409, detail="Voo sem assentos disponíveis")

                
                cur.execute(
                    """INSERT INTO flight_reservations
                       (customer_id, flight_id, seat_number, status)
                       VALUES (%s, %s, %s, 'confirmed')
                       RETURNING id""",
                    (body.customer_id, body.flight_id, body.seat_number)
                )
                reserva_id = cur.fetchone()["id"]

                
                cur.execute(
                    "UPDATE flights SET available_seats = available_seats - 1 WHERE id = %s",
                    (body.flight_id,)
                )

            conn.commit()
        return {"reserva_id": reserva_id, "status": "confirmed"}

    try:
        return executar_com_retry(_executar)
    except psycopg2.errors.SerializationFailure:
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível. Tente novamente.")



@app.post("/reservas/hotel", status_code=201, summary="Cria reserva de hotel")
def criar_reserva_hotel(body: ReservaHotelRequest):
    """
    Verifica conflito de datas com SELECT FOR UPDATE no quarto solicitado,
    evitando double booking em requisições concorrentes.
    """
    if body.check_out <= body.check_in:
        raise HTTPException(status_code=400, detail="check_out deve ser posterior a check_in")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            
            cur.execute(
                "SELECT id, price_per_night FROM rooms WHERE id = %s FOR UPDATE",
                (body.room_id,)
            )
            quarto = cur.fetchone()

            if not quarto:
                raise HTTPException(status_code=404, detail="Quarto não encontrado")

            
            cur.execute(
                """SELECT id FROM hotel_reservations
                   WHERE room_id = %s
                     AND status != 'cancelled'
                     AND check_in  < %s
                     AND check_out > %s""",
                (body.room_id, body.check_out, body.check_in)
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Quarto já reservado para este período")

            noites = (body.check_out - body.check_in).days
            total = float(quarto["price_per_night"]) * noites

            cur.execute(
                """INSERT INTO hotel_reservations
                   (customer_id, room_id, check_in, check_out, status, total_price)
                   VALUES (%s, %s, %s, %s, 'confirmed', %s)
                   RETURNING id""",
                (body.customer_id, body.room_id, body.check_in, body.check_out, total)
            )
            reserva_id = cur.fetchone()["id"]

        conn.commit()

    return {"reserva_id": reserva_id, "status": "confirmed", "total_price": total}



@app.post("/reservas/pacote", status_code=201, summary="Cria reserva de pacote (voo e hotel)")
def reservar_pacote(body: PacoteRequest):
    """
    Utiliza savepoints. Se a reserva de hotel falhar, a reserva de voo é desfeita
    de forma controlada, mantendo o controle da transação.
    """
    if body.check_out <= body.check_in:
        raise HTTPException(status_code=400, detail="check_out deve ser posterior a check_in")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            
            cur.execute("SAVEPOINT sp_voo")
            try:
                cur.execute(
                    "SELECT id, available_seats FROM flights WHERE id = %s FOR UPDATE",
                    (body.flight_id,)
                )
                voo = cur.fetchone()
                if not voo:
                    raise Exception("Voo não encontrado")
                if voo["available_seats"] <= 0:
                    raise Exception("Voo sem assentos disponíveis")

                cur.execute(
                    """INSERT INTO flight_reservations
                       (customer_id, flight_id, seat_number, status)
                       VALUES (%s, %s, %s, 'confirmed')
                       RETURNING id""",
                    (body.customer_id, body.flight_id, body.seat_number)
                )
                flight_res_id = cur.fetchone()["id"]

                cur.execute(
                    "UPDATE flights SET available_seats = available_seats - 1 WHERE id = %s",
                    (body.flight_id,)
                )
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT sp_voo")
                conn.rollback()
                raise HTTPException(status_code=409, detail=f"Falha na reserva do voo: {str(e)}")

          
            cur.execute("SAVEPOINT sp_hotel")
            try:
                cur.execute(
                    "SELECT id, price_per_night FROM rooms WHERE id = %s FOR UPDATE",
                    (body.room_id,)
                )
                quarto = cur.fetchone()
                if not quarto:
                    raise Exception("Quarto não encontrado")

                cur.execute(
                    """SELECT id FROM hotel_reservations
                       WHERE room_id = %s
                         AND status != 'cancelled'
                         AND check_in  < %s
                         AND check_out > %s""",
                    (body.room_id, body.check_out, body.check_in)
                )
                if cur.fetchone():
                    raise Exception("Quarto já reservado para este período")

                noites = (body.check_out - body.check_in).days
                total = float(quarto["price_per_night"]) * noites

                cur.execute(
                    """INSERT INTO hotel_reservations
                       (customer_id, room_id, check_in, check_out, status, total_price)
                       VALUES (%s, %s, %s, %s, 'confirmed', %s)
                       RETURNING id""",
                    (body.customer_id, body.room_id, body.check_in, body.check_out, total)
                )
                hotel_res_id = cur.fetchone()["id"]
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT sp_hotel")
                cur.execute("ROLLBACK TO SAVEPOINT sp_voo")
                conn.rollback()
                raise HTTPException(status_code=409, detail=f"Falha na reserva do hotel: {str(e)}")

        conn.commit()

    return {
        "status": "confirmed",
        "flight_reservation_id": flight_res_id,
        "hotel_reservation_id": hotel_res_id,
        "total_hotel_price": total
    }



@app.post("/pagamentos", status_code=201, summary="Registra pagamento")
def registrar_pagamento(body: PagamentoRequest):
    if body.reservation_type not in ("flight", "hotel"):
        raise HTTPException(status_code=400, detail="reservation_type deve ser 'flight' ou 'hotel'")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            tabela = "flight_reservations" if body.reservation_type == "flight" else "hotel_reservations"
            cur.execute(f"SELECT id FROM {tabela} WHERE id = %s", (body.reservation_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Reserva não encontrada")

            cur.execute(
                """INSERT INTO payments
                   (reservation_type, reservation_id, amount, status, payment_method)
                   VALUES (%s, %s, %s, 'paid', %s)
                   RETURNING id""",
                (body.reservation_type, body.reservation_id, body.amount, body.payment_method)
            )
            payment_id = cur.fetchone()["id"]

        conn.commit()

    return {"payment_id": payment_id, "status": "paid"}



@app.delete("/reservas/{reserva_id}", summary="Cancela reserva")
def cancelar_reserva(
    reserva_id: int,
    tipo: str = Query(..., description="Tipo da reserva: 'flight' ou 'hotel'")
):
    if tipo not in ("flight", "hotel"):
        raise HTTPException(status_code=400, detail="tipo deve ser 'flight' ou 'hotel'")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if tipo == "flight":
                cur.execute(
                    "SELECT id, flight_id, status FROM flight_reservations WHERE id = %s FOR UPDATE",
                    (reserva_id,)
                )
                reserva = cur.fetchone()
                if not reserva:
                    raise HTTPException(status_code=404, detail="Reserva não encontrada")
                if reserva["status"] == "cancelled":
                    raise HTTPException(status_code=409, detail="Reserva já cancelada")

                cur.execute(
                    "UPDATE flight_reservations SET status = 'cancelled' WHERE id = %s",
                    (reserva_id,)
                )
                
                cur.execute(
                    "UPDATE flights SET available_seats = available_seats + 1 WHERE id = %s",
                    (reserva["flight_id"],)
                )

            else:  
                cur.execute(
                    "SELECT id, status FROM hotel_reservations WHERE id = %s FOR UPDATE",
                    (reserva_id,)
                )
                reserva = cur.fetchone()
                if not reserva:
                    raise HTTPException(status_code=404, detail="Reserva não encontrada")
                if reserva["status"] == "cancelled":
                    raise HTTPException(status_code=409, detail="Reserva já cancelada")

                cur.execute(
                    "UPDATE hotel_reservations SET status = 'cancelled' WHERE id = %s",
                    (reserva_id,)
                )

        conn.commit()

    return {"reserva_id": reserva_id, "status": "cancelled"}


@app.post("/test/falha-transacao", summary="Simula falha em transação e rollback")
def teste_falha_transacao():
    """
    1. Inicia uma transação
    2. Insere um registro de reserva
    3. Lança uma exceção antes do COMMIT
    O gerenciador de contexto `get_conn` fará o ROLLBACK automático.
    """
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
               
                cur.execute(
                    """INSERT INTO flight_reservations
                       (customer_id, flight_id, seat_number, status)
                       VALUES (1, 1, 'FAIL', 'confirmed')
                       RETURNING id"""
                )
                reserva_id = cur.fetchone()["id"]
                
               
                raise RuntimeError(f"Erro intencional! A reserva {reserva_id} NÃO deve ser salva no banco.")
           
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
