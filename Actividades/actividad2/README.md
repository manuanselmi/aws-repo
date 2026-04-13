# Actividad 2 — API Gateway and Event Sources

REST API que expone datos de sesiones de F1 (temporada 2024) usando AWS Lambda + API Gateway + SAM, consumiendo la API de [OpenF1](https://openf1.org).

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/sessions` | Lista todas las sesiones de carrera 2024 |
| GET | `/sessions/{session_key}` | Detalle de una sesión específica |
| POST | `/sessions/{session_key}/ingest` | Ingesta de sesión + drivers desde OpenF1 |

## Estructura

```
actividad2/
├── f1_api/
│   ├── handler.py          # Handlers Lambda
│   ├── requirements.txt    # Dependencias Python
│   └── __init__.py
├── events/                 # Eventos de prueba
│   ├── event_list_sessions.json
│   ├── event_get_session.json
│   └── event_ingest_session.json
├── template.yaml           # SAM template
├── samconfig.toml          # Configuración de deploy
└── README.md
```

## Uso local

```bash
# Construir
sam build

# Levantar API local (requiere Docker)
sam local start-api

# En otra terminal:
curl http://localhost:3000/sessions
curl http://localhost:3000/sessions/9158
curl -X POST http://localhost:3000/sessions/9158/ingest
```

## Deploy

```bash
sam build
sam deploy --guided
```
