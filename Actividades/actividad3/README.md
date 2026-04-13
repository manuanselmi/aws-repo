# Actividad 3 — SAM Deep Dive: Deployment and Configuration

Evolución de la Actividad 2. Misma API de OpenF1 pero con template parametrizado para deploy multi-ambiente (dev/prod).

## Qué cambió respecto a la Actividad 2

| Concepto | Actividad 2 | Actividad 3 |
|----------|-------------|-------------|
| Nombres de funciones | Generados por SAM | Explícitos con `!Sub` incluyendo el environment |
| Parámetros | Ninguno | `Environment` (dev/prod) |
| Conditions | Ninguna | `IsProd` para configurar memoria y concurrencia |
| Globals | Básicos | Incluyen variable de entorno `ENV` |
| samconfig.toml | Un solo perfil | Perfiles `dev` y `prod` separados |
| Concurrencia | Sin límite | `ReservedConcurrentExecutions` (2 dev / 10 prod) |
| Memoria Ingest | 512 MB fija | 512 MB dev / 1024 MB prod |

## Estructura

```
actividad3/
├── f1_api/
│   ├── handler.py          # Handlers Lambda (igual que actividad2)
│   ├── requirements.txt
│   └── __init__.py
├── events/
│   ├── event_list_sessions.json
│   ├── event_get_session.json
│   └── event_ingest_session.json
├── template.yaml           # SAM template parametrizado
├── samconfig.toml          # Perfiles dev y prod
└── README.md
```

## Uso local

```bash
sam build

# Invocar una función individual
sam local invoke ListSessionsFunction --event events/event_list_sessions.json

# Levantar toda la API
sam local start-api

# Probar
curl http://localhost:3000/sessions
curl http://localhost:3000/sessions/9158
curl -X POST http://localhost:3000/sessions/9158/ingest
```

## Deploy multi-ambiente

```bash
sam build

# Deploy a dev (sin confirmación de changeset)
sam deploy --config-env dev

# Deploy a prod (con confirmación de changeset)
sam deploy --config-env prod
```

## Key Concepts

- **Parameters**: `Environment` permite reutilizar el mismo template para dev y prod
- **`!Sub`**: Interpola variables en strings — `openf1-list-sessions-${Environment}`
- **Conditions**: `IsProd` evalúa si estamos en producción para cambiar configuración
- **`!If`**: Usa la condición para elegir valores — más memoria y concurrencia en prod
- **Globals**: Configuración compartida entre todas las funciones (runtime, timeout, env vars)
- **samconfig.toml profiles**: `[dev.deploy.parameters]` y `[prod.deploy.parameters]` evitan pasar flags manualmente
