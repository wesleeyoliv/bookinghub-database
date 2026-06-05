CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    cpf VARCHAR(11) UNIQUE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hotels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    stars INT CHECK (stars >= 1 AND stars <= 5),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE airports (
    id SERIAL PRIMARY KEY,
    code VARCHAR(3) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL
);


CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    hotel_id INT REFERENCES hotels(id),
    room_number VARCHAR(10) NOT NULL,
    type VARCHAR(20) CHECK (type IN ('single', 'double', 'suite')),
    capacity INT NOT NULL,
    price_per_night DECIMAL(10, 2) NOT NULL
);

CREATE TABLE flights (
    id SERIAL PRIMARY KEY,
    flight_number VARCHAR(10) UNIQUE NOT NULL,
    origin_airport_id INT REFERENCES airports(id),
    destination_airport_id INT REFERENCES airports(id),
    departure_time TIMESTAMP NOT NULL,
    arrival_time TIMESTAMP NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);


CREATE TABLE flight_reservations (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    flight_id INT REFERENCES flights(id),
    seat_number VARCHAR(10),
    status VARCHAR(20) CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hotel_reservations (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    room_id INT REFERENCES rooms(id),
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    status VARCHAR(20) CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    total_price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    reservation_type VARCHAR(10) CHECK (reservation_type IN ('flight', 'hotel')),
    reservation_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20),
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_airports_city ON airports(city);
CREATE INDEX IF NOT EXISTS idx_flights_departure_seats
    ON flights(departure_time, available_seats)
    WHERE available_seats > 0;
CREATE INDEX IF NOT EXISTS idx_flights_origin      ON flights(origin_airport_id);
CREATE INDEX IF NOT EXISTS idx_flights_destination ON flights(destination_airport_id);
CREATE INDEX IF NOT EXISTS idx_fr_flight_status ON flight_reservations(flight_id, status);
CREATE INDEX IF NOT EXISTS idx_flights_departure ON flights(departure_time);
CREATE INDEX IF NOT EXISTS idx_hr_room_dates
    ON hotel_reservations(room_id, status, check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_rooms_hotel ON rooms(hotel_id);
CREATE INDEX IF NOT EXISTS idx_fr_customer ON flight_reservations(customer_id);
CREATE INDEX IF NOT EXISTS idx_hr_customer ON hotel_reservations(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_res ON payments(reservation_id, reservation_type);

