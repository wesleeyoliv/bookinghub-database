import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta

conn = psycopg2.connect("dbname=bookinghub user=booking password=secret host=db port=5432")
cur = conn.cursor()
fake = Faker('pt_BR')

def seed():
    print("Iniciando carga de dados massiva...")

  
    airports = [('GRU', 'Guarulhos', 'São Paulo', 'Brasil'), ('CGH', 'Congonhas', 'São Paulo', 'Brasil'), ('SDU', 'Santos Dumont', 'Rio de Janeiro', 'Brasil')]
    for a in airports:
        cur.execute("INSERT INTO airports (code, name, city, country) VALUES (%s, %s, %s, %s) ON CONFLICT (code) DO NOTHING", a)

  
    print("Populando clientes")
    for _ in range(20000):
        cur.execute("INSERT INTO customers (name, email, cpf, phone) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", 
                    (fake.name(), fake.unique.email(), fake.cpf().replace('.', '').replace('-', ''), fake.phone_number()))


    print("Populando hotéis e quartos")
    for i in range(200):
        cur.execute("INSERT INTO hotels (name, city, country, stars, address) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (fake.company(), fake.city(), 'Brasil', random.randint(1, 5), fake.address()))
        h_id = cur.fetchone()[0]
        for j in range(5):
            cur.execute("INSERT INTO rooms (hotel_id, room_number, type, capacity, price_per_night) VALUES (%s, %s, %s, %s, %s)",
                        (h_id, f"{i}{j}", random.choice(['single', 'double', 'suite']), random.randint(1, 4), random.uniform(100, 1000)))


    print("Populando voos")
    cur.execute("SELECT id FROM airports")
    air_ids = [r[0] for r in cur.fetchall()]
    for i in range(2000):
        cur.execute("INSERT INTO flights (flight_number, origin_airport_id, destination_airport_id, departure_time, arrival_time, total_seats, available_seats, price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (f"VOO{i+1000}", random.choice(air_ids), random.choice(air_ids), datetime.now(), datetime.now()+timedelta(hours=2), 100, 100, 500.0))

    
    print("Populando 20.000 reservas de hotel e 20.000 de voo")
    cur.execute("SELECT id FROM customers")
    cust_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM rooms")
    room_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM flights")
    fl_ids = [r[0] for r in cur.fetchall()]

    for _ in range(20000):
        cur.execute("INSERT INTO hotel_reservations (customer_id, room_id, check_in, check_out, status, total_price) VALUES (%s, %s, %s, %s, %s, %s)",
                    (random.choice(cust_ids), random.choice(room_ids), datetime.now().date(), datetime.now().date()+timedelta(days=2), 'confirmed', 500.0))
        cur.execute("INSERT INTO flight_reservations (customer_id, flight_id, seat_number, status) VALUES (%s, %s, %s, %s)",
                    (random.choice(cust_ids), random.choice(fl_ids), f"{random.randint(1,99)}B", 'confirmed'))

    conn.commit()
    print("Carga concluída! O banco está com volume para testes reais.")

seed()