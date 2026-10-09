"""Demo data created automatically the first time the database is empty.

Includes all the catalogs, three rural routes around El Encano (Pasto, Nariño),
ten students and about three weeks of finished trips, so the AI models have
history to learn from. A fixed random seed makes the data the same every time.
"""

import random
from datetime import date, datetime, time, timedelta

from . import models as m
from .auth import client_digest, hash_password
from .services import haversine_km

DEMO_PASSWORDS = {
    "coordinator": "Admin123*",
    "driver": "Conductor123*",
    "monitor": "Monitor123*",
    "guardian": "Acudiente123*",
}

CATALOGS = {
    m.Role: [
        ("coordinator", "Coordinador", {"description": "Administra rutas, estudiantes, usuarios y catálogos"}),
        ("driver", "Conductor", {"description": "Opera los recorridos y registra abordajes"}),
        ("monitor", "Monitor de ruta", {"description": "Acompaña a los estudiantes y registra abordajes"}),
        ("guardian", "Acudiente", {"description": "Consulta dónde está su hijo y su historial"}),
    ],
    m.DocumentType: [
        ("cc", "Cédula de ciudadanía", {}),
        ("ti", "Tarjeta de identidad", {}),
        ("rc", "Registro civil", {}),
        ("ce", "Cédula de extranjería", {}),
    ],
    m.Relationship: [
        ("mother", "Madre", {}),
        ("father", "Padre", {}),
        ("grandparent", "Abuelo o abuela", {}),
        ("uncle", "Tío o tía", {}),
        ("sibling", "Hermano o hermana", {}),
        ("tutor", "Tutor legal", {}),
    ],
    m.Grade: [
        (code, name, {"sort_order": order})
        for order, (code, name) in enumerate(
            [
                ("transition", "Transición"), ("first", "Primero"), ("second", "Segundo"), ("third", "Tercero"),
                ("fourth", "Cuarto"), ("fifth", "Quinto"), ("sixth", "Sexto"), ("seventh", "Séptimo"),
                ("eighth", "Octavo"), ("ninth", "Noveno"), ("tenth", "Décimo"), ("eleventh", "Undécimo"),
            ]
        )
    ],
    m.TripStatus: [
        ("scheduled", "Programado", {}),
        ("in_progress", "En recorrido", {}),
        ("finished", "Finalizado", {}),
    ],
    m.EventType: [("boarding", "Subió al bus", {}), ("drop_off", "Bajó del bus", {})],
    m.CheckInMethod: [("qr", "Código QR", {}), ("manual", "Manual", {})],
    m.WeatherCondition: [
        ("clear", "Despejado", {"delay_minutes": 0, "weather_codes": "0,1"}),
        ("cloudy", "Nublado", {"delay_minutes": 2, "weather_codes": "2,3"}),
        ("fog", "Neblina", {"delay_minutes": 6, "weather_codes": "45,48"}),
        ("drizzle", "Llovizna", {"delay_minutes": 4, "weather_codes": "51,53,55,56,57"}),
        ("rain", "Lluvia", {"delay_minutes": 8, "weather_codes": "61,63,65,66,67,80,81"}),
        ("storm", "Tormenta", {"delay_minutes": 15, "weather_codes": "82,95,96,99"}),
    ],
    m.RoadCondition: [
        ("good", "Buena", {"delay_minutes": 0}),
        ("fair", "Regular", {"delay_minutes": 4}),
        ("bad", "Mala (huecos o barro)", {"delay_minutes": 10}),
        ("landslide", "Derrumbe parcial", {"delay_minutes": 20}),
        ("closed", "Cerrada", {"delay_minutes": 45}),
    ],
    m.IncidentType: [
        ("mechanical", "Falla mecánica", {"severity": 2}),
        ("accident", "Accidente", {"severity": 3}),
        ("road_blocked", "Vía bloqueada", {"severity": 2}),
        ("student_health", "Estudiante enfermo", {"severity": 2}),
        ("delay", "Retraso", {"severity": 1}),
        ("other", "Otro", {"severity": 1}),
    ],
}

USERS = [
    # role, first, last, document, email, phone
    ("coordinator", "Andrea", "Rosero", "1085250101", "admin@rutasegura.com", "3104567801"),
    ("driver", "Carlos", "Benavides", "1085250102", "conductor@rutasegura.com", "3104567802"),
    ("guardian", "Laura", "Pérez", "1085250103", "acudiente@rutasegura.com", "3104567803"),
    ("driver", "Pedro", "Ramírez", "1085250104", "conductor2@rutasegura.com", "3104567804"),
    ("monitor", "Marta", "Gómez", "1085250105", "monitor@rutasegura.com", "3104567805"),
    ("guardian", "Rosa", "Delgado", "1085250106", "acudiente2@rutasegura.com", "3104567806"),
    ("guardian", "José", "Benavides", "1085250107", "acudiente3@rutasegura.com", "3104567807"),
    ("monitor", "Diego", "Chamorro", "1085250108", "monitor2@rutasegura.com", "3104567808"),
    ("driver", "Jairo", "Muñoz", "1085250109", "conductor3@rutasegura.com", "3104567809"),
    ("guardian", "Sandra", "Jojoa", "1085250110", "acudiente4@rutasegura.com", "3104567810"),
]

ROUTES = [
    # name, description, campus index, vehicle index, stops [(name, lat, lng)]
    (
        "Ruta Rural 01", "Veredas del sector sur de la laguna", 0, 0,
        [
            ("Vereda Santa Teresita", 1.1180, -77.1735),
            ("Vereda El Puerto", 1.1325, -77.1690),
            ("Vereda Romerillo", 1.1440, -77.1655),
            ("Vereda Naranjal", 1.1530, -77.1610),
            ("Institución Educativa", 1.1617, -77.1598),
        ],
    ),
    (
        "Ruta Rural 02", "Veredas del sector norte", 0, 1,
        [
            ("Vereda Casapamba", 1.2010, -77.1720),
            ("Vereda Mojondinoy", 1.1765, -77.1580),
            ("Vereda El Motilón", 1.1890, -77.1655),
            ("Institución Educativa", 1.1617, -77.1598),
        ],
    ),
    (
        "Ruta Rural 03", "Veredas cercanas a la sede Santa Lucía", 1, 2,
        [
            ("Vereda Ramos", 1.0950, -77.1450),
            ("Vereda Bellavista", 1.1080, -77.1495),
            ("Sede Santa Lucía", 1.1250, -77.1530),
        ],
    ),
]

# Extra road segments (besides consecutive stops) so the graph has alternative paths.
EXTRA_SEGMENTS = [(0, 1, 3), (0, 0, 2), (1, 0, 2), (1, 1, 3)]  # (route index, stop a, stop b)

STUDENTS = [
    # first, last, document, birth, grade, route idx, stop idx, guardian user idx, relationship, qr
    ("Juan", "Pérez", "1085300001", date(2013, 3, 14), "eighth", 0, 0, 2, "mother", "RS-DEMO-0001"),
    ("Valentina", "Pérez", "1085300002", date(2016, 8, 2), "fifth", 0, 1, 2, "mother", "RS-DEMO-0002"),
    ("Santiago", "Delgado", "1085300003", date(2014, 1, 21), "seventh", 0, 0, 5, "mother", "RS-DEMO-0003"),
    ("Camila", "Delgado", "1085300004", date(2018, 5, 9), "third", 1, 0, 5, "mother", "RS-DEMO-0004"),
    ("Mateo", "Benavides", "1085300005", date(2012, 11, 30), "ninth", 1, 2, 6, "father", "RS-DEMO-0005"),
    ("Isabella", "Benavides", "1085300006", date(2015, 6, 18), "sixth", 1, 1, 6, "father", "RS-DEMO-0006"),
    ("Samuel", "Jojoa", "1085300007", date(2017, 2, 25), "fourth", 0, 2, 9, "mother", "RS-DEMO-0007"),
    ("Sofía", "Jojoa", "1085300008", date(2020, 9, 12), "first", 0, 3, 9, "mother", "RS-DEMO-0008"),
    ("Daniel", "Muñoz", "1085300009", date(2011, 4, 7), "tenth", 2, 0, 9, "uncle", "RS-DEMO-0009"),
    ("Luciana", "Muñoz", "1085300010", date(2016, 12, 1), "fifth", 2, 1, 9, "uncle", "RS-DEMO-0010"),
]

WEATHER_WEIGHTS = {"clear": 40, "cloudy": 25, "fog": 5, "drizzle": 10, "rain": 15, "storm": 5}
ROAD_WEIGHTS = {"good": 55, "fair": 25, "bad": 15, "landslide": 5}
HISTORY_SCHOOL_DAYS = 15
AVERAGE_SPEED_KMH = 25.0


def to_utc(day: date, local_clock: time) -> datetime:
    """Colombia is UTC-5 all year."""
    return datetime.combine(day, local_clock) + timedelta(hours=5)


def seed_demo(db) -> None:
    if db.query(m.Role).first():
        return
    rng = random.Random(2026)

    # Catalogs ---------------------------------------------------------------
    catalog = {}
    for model, rows in CATALOGS.items():
        for code, name, extra in rows:
            item = model(code=code, name=name, **extra)
            db.add(item)
            catalog[(model, code)] = item
    db.flush()

    def cat(model, code):
        return catalog[(model, code)]

    # Organization -----------------------------------------------------------
    school = m.School(name="Institución Educativa Rural El Encano", dane_code="152001000123",
                      municipality="Pasto", phone="3001234567")
    db.add(school)
    db.flush()
    campuses = [
        m.Campus(school_id=school.id, name="Sede Principal", address="Corregimiento El Encano",
                 latitude=1.1617, longitude=-77.1598),
        m.Campus(school_id=school.id, name="Sede Santa Lucía", address="Vereda Santa Lucía",
                 latitude=1.1250, longitude=-77.1530),
    ]
    vehicles = [
        m.Vehicle(plate="ABC123", brand="Chevrolet NPR", model_year=2019, capacity=30),
        m.Vehicle(plate="XYZ789", brand="Hyundai County", model_year=2021, capacity=28),
        m.Vehicle(plate="KLM456", brand="Toyota Coaster", model_year=2018, capacity=25),
    ]
    db.add_all(campuses + vehicles)
    db.flush()

    # Users ------------------------------------------------------------------
    users = []
    for role, first, last, document, email, phone in USERS:
        user = m.User(
            role_id=cat(m.Role, role).id,
            document_type_id=cat(m.DocumentType, "cc").id,
            document_number=document,
            first_name=first,
            last_name=last,
            email=email,
            phone=phone,
            password_hash=hash_password(client_digest(email, DEMO_PASSWORDS[role])),
        )
        users.append(user)
    db.add_all(users)
    db.flush()
    drivers = [users[1], users[3], users[8]]
    monitors = [users[4], users[7]]
    for index, (driver, license_number) in enumerate(zip(drivers, ["10852501", "10852502", "10852503"])):
        db.add(m.Driver(user_id=driver.id, license_number=license_number, license_category="C2",
                        license_expires_on=date(2028, 6, 30) if index != 2 else date(2027, 3, 15),
                        vehicle_id=vehicles[index].id))

    # Routes, stops, segments --------------------------------------------------
    routes, route_stop_lists = [], []
    for name, description, campus_index, vehicle_index, stops in ROUTES:
        route = m.Route(name=name, description=description, campus_id=campuses[campus_index].id,
                        vehicle_id=vehicles[vehicle_index].id)
        db.add(route)
        db.flush()
        stop_rows = []
        for order, (stop_name, lat, lng) in enumerate(stops, start=1):
            stop = m.Stop(route_id=route.id, name=stop_name, order=order, latitude=lat, longitude=lng)
            db.add(stop)
            stop_rows.append(stop)
        db.flush()
        routes.append(route)
        route_stop_lists.append(stop_rows)

    def add_segment(route, a, b, detour=1.25):
        km = round(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * detour, 2)
        db.add(m.RouteSegment(route_id=route.id, from_stop_id=a.id, to_stop_id=b.id, distance_km=km,
                              travel_minutes=max(1, round(km / AVERAGE_SPEED_KMH * 60))))

    for route, stops in zip(routes, route_stop_lists):
        for a, b in zip(stops, stops[1:]):
            add_segment(route, a, b)
    for route_index, a, b in EXTRA_SEGMENTS:
        stops = route_stop_lists[route_index]
        add_segment(routes[route_index], stops[a], stops[b], detour=1.6)
    db.flush()

    # Students and guardians ---------------------------------------------------
    students = []
    for first, last, document, birth, grade, route_i, stop_i, guardian_i, kinship, qr in STUDENTS:
        student = m.Student(
            document_type_id=cat(m.DocumentType, "ti").id, document_number=document, first_name=first,
            last_name=last, birth_date=birth, grade_id=cat(m.Grade, grade).id,
            campus_id=routes[route_i].campus_id, route_id=routes[route_i].id,
            stop_id=route_stop_lists[route_i][stop_i].id, qr_code=qr,
        )
        db.add(student)
        db.flush()
        db.add(m.StudentGuardian(student_id=student.id, guardian_id=users[guardian_i].id,
                                 relationship_id=cat(m.Relationship, kinship).id, is_primary=True))
        students.append(student)
    db.flush()

    # History of finished trips (training data for the AI) ---------------------
    finished = cat(m.TripStatus, "finished").id
    boarding = cat(m.EventType, "boarding").id
    drop_off = cat(m.EventType, "drop_off").id
    methods = [cat(m.CheckInMethod, "qr").id] * 9 + [cat(m.CheckInMethod, "manual").id]

    school_days, day = [], date.today() - timedelta(days=1)
    while len(school_days) < HISTORY_SCHOOL_DAYS:
        if day.weekday() < 5:
            school_days.append(day)
        day -= timedelta(days=1)

    for day in reversed(school_days):
        for route_index, route in enumerate(routes):
            stops = route_stop_lists[route_index]
            weather_code = rng.choices(list(WEATHER_WEIGHTS), weights=list(WEATHER_WEIGHTS.values()))[0]
            road_code = rng.choices(list(ROAD_WEIGHTS), weights=list(ROAD_WEIGHTS.values()))[0]
            if weather_code in ("rain", "storm") and road_code == "good":
                road_code = "fair"
            weather, road = cat(m.WeatherCondition, weather_code), cat(m.RoadCondition, road_code)

            planned = sum(
                round(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * 1.25 / AVERAGE_SPEED_KMH * 60)
                for a, b in zip(stops, stops[1:])
            )
            delay = 0.9 * weather.delay_minutes + 1.1 * road.delay_minutes + 0.6 * len(stops) + rng.gauss(0, 1.5)
            duration = max(planned + 1, planned + delay)
            start = to_utc(day, time(6, rng.randint(0, 12)))
            end = start + timedelta(minutes=duration)
            trip = m.Trip(
                route_id=route.id, driver_id=drivers[route_index].id,
                monitor_id=monitors[route_index].id if route_index < 2 else None,
                vehicle_id=route.vehicle_id, status_id=finished, weather_id=weather.id,
                road_condition_id=road.id, direction="outbound", scheduled_date=day,
                started_at=start, finished_at=end,
            )
            db.add(trip)
            db.flush()

            absence_probability = 0.25 if weather_code in ("rain", "storm") else 0.06
            for student in (s for s in students if s.route_id == route.id):
                if rng.random() < absence_probability:
                    continue
                stop_position = next(i for i, s in enumerate(stops) if s.id == student.stop_id)
                board_at = start + timedelta(minutes=duration * stop_position / len(stops) + rng.uniform(0, 1))
                db.add(m.Attendance(student_id=student.id, trip_id=trip.id, stop_id=student.stop_id,
                                    event_type_id=boarding, method_id=rng.choice(methods),
                                    recorded_by=drivers[route_index].id, timestamp=board_at))
                db.add(m.Attendance(student_id=student.id, trip_id=trip.id, stop_id=stops[-1].id,
                                    event_type_id=drop_off, method_id=rng.choice(methods),
                                    recorded_by=drivers[route_index].id,
                                    timestamp=end - timedelta(minutes=rng.uniform(0, 1))))

    # Today's trips, ready to start --------------------------------------------
    scheduled = cat(m.TripStatus, "scheduled").id
    for route_index, route in enumerate(routes):
        db.add(m.Trip(route_id=route.id, driver_id=drivers[route_index].id,
                      monitor_id=monitors[route_index].id if route_index < 2 else None,
                      vehicle_id=route.vehicle_id, status_id=scheduled, direction="outbound",
                      scheduled_date=date.today()))

    # Incidents, notifications and audit samples ------------------------------
    last_day = school_days[0]
    db.add(m.Incident(incident_type_id=cat(m.IncidentType, "road_blocked").id, reported_by=drivers[1].id,
                      description="Derrumbe parcial en la vía a Casapamba. Se pasa con precaución por un solo carril.",
                      latitude=1.1955, longitude=-77.1690, created_at=to_utc(last_day, time(6, 20))))
    db.add(m.Incident(incident_type_id=cat(m.IncidentType, "mechanical").id, reported_by=drivers[0].id,
                      description="Llanta pinchada en la Vereda El Puerto. Se cambió en quince minutos.",
                      latitude=1.1325, longitude=-77.1690, created_at=to_utc(school_days[3], time(6, 25)),
                      resolved_at=to_utc(school_days[3], time(6, 45))))
    for student in students[:2]:
        db.add(m.Notification(user_id=users[2].id, kind="drop_off",
                              title=f"{student.first_name} bajó del bus",
                              message=f"{student.full_name} llegó a la Institución Educativa.",
                              created_at=to_utc(last_day, time(6, 50))))
    db.add(m.AuditLog(user_id=None, action="seed", entity="database", detail="Datos de demostración cargados"))
    db.commit()
