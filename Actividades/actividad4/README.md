# Actividad 4 — S3, DynamoDB y EventBridge con CDK

## Objetivos

- Migrar de SAM a **CDK** (Python) para infraestructura como código
- Crear tablas DynamoDB para sesiones y pilotos de F1
- Guardar respuestas crudas en S3
- Configurar una regla de EventBridge para disparar la Lambda
- Implementar el **patrón Repository** para acceso a datos

---

## Estructura del proyecto

```
actividad4/
├── infra/cdk/                  ← CDK app (infraestructura como código)
│   ├── app.py                  ← Entrypoint: define los 3 stacks
│   ├── cdk.json
│   ├── requirements.txt
│   └── stacks/
│       ├── data_stack.py       ← DynamoDB tables + S3 bucket
│       ├── lambda_stack.py     ← Lambda de ingesta
│       └── messaging_stack.py  ← EventBridge rule (disabled por defecto)
│
├── lambdas/ingest/
│   ├── handler.py              ← Llama OpenF1 → guarda en S3 + DynamoDB
│   └── requirements.txt
│
├── repositories/
│   ├── session_repo.py         ← CRUD sobre tabla f1_sessions
│   ├── driver_repo.py          ← CRUD sobre tabla f1_driver_stats
│   └── s3_repo.py              ← Lectura/escritura en bucket f1-raw-data
│
└── localstack/
    ├── docker-compose.yml      ← Levanta LocalStack en Docker
    ├── Makefile                ← Comandos de desarrollo local
    └── init.py                 ← Crea los recursos AWS en LocalStack
```

---

## CDK: los 3 stacks

### `F1DataStack` — Almacenamiento

| Recurso | Tipo | Keys |
|---|---|---|
| `f1_sessions` | DynamoDB Table | PK: `session_key` (N) |
| `f1_driver_stats` | DynamoDB Table | PK: `session_key` (N), SK: `driver_number` (N) |
| `f1-raw-data` | S3 Bucket | — |

### `F1LambdaStack` — Lógica

- Lambda `f1-ingest`: llama OpenF1, guarda raw en S3, parsea y guarda en DynamoDB
- Tiene permisos IAM sobre las tablas y el bucket del DataStack

### `F1MessagingStack` — Scheduling

- EventBridge Rule `f1-ingest-schedule`: cada 5 minutos (deshabilitada por defecto)
- **Nota**: EventBridge mínimo = 1 minuto. Para testing local se invoca directamente.

---

## Patrón Repository

Cada repository encapsula toda la lógica de acceso a datos:

```python
# Todos usan AWS_ENDPOINT_URL automáticamente para LocalStack
from repositories.session_repo import SessionRepository
from repositories.driver_repo import DriverRepository
from repositories.s3_repo import S3Repository
```

El truco clave es esta línea en cada repo:
```python
endpoint_url = os.environ.get("AWS_ENDPOINT_URL")  # LocalStack o None (AWS real)
```

---

## Probar con LocalStack (sin cuenta AWS)

### Pre-requisitos

```bash
# Docker Desktop corriendo
docker --version

# Python 3.12+
python3 --version

# Dependencias
pip install boto3 requests
```

### 1. Levantar LocalStack

```bash
cd localstack
make start
```

Espera a que diga `✓ LocalStack listo`.

### 2. Crear los recursos

```bash
make init
```

Crea las tablas DynamoDB y el bucket S3 en LocalStack.

### 3. Verificar que los repositories funcionan

```bash
# Smoke-test rápido del activity
export AWS_ENDPOINT_URL=http://localhost:4566
python -c "from repositories.session_repo import SessionRepository; print('OK')"

# Test completo (inserta datos y los lee)
make test
```

### 4. Ejecutar la Lambda de ingesta

```bash
make invoke
```

Llama a OpenF1, guarda sesiones 2024 en S3 + DynamoDB.

### 5. Ver los datos guardados

```bash
# Estado de los recursos
make status

# Ver datos en DynamoDB
AWS_ENDPOINT_URL=http://localhost:4566 \
aws dynamodb scan --table-name f1_sessions \
  --endpoint-url http://localhost:4566

# Ver archivos en S3
AWS_ENDPOINT_URL=http://localhost:4566 \
aws s3 ls s3://f1-raw-data/sessions/ --recursive \
  --endpoint-url http://localhost:4566
```

### 6. Apagar LocalStack

```bash
make stop    # detiene (datos persistidos)
make clean   # detiene + borra datos
```

---

## Desplegar con CDK en AWS real

```bash
cd infra/cdk
pip install -r requirements.txt
cdk bootstrap
cdk deploy --all
```

## Desplegar en LocalStack con cdklocal (opcional)

```bash
npm install -g aws-cdk-local aws-cdk
cd localstack
make init-cdk
```

---

## Conceptos clave

| Concepto | CDK (esta actividad) | SAM (actividad 3) |
|---|---|---|
| Lenguaje | Python real | YAML |
| Lógica | if/for/clases | Condiciones/Refs limitadas |
| Reuso | Importar clases de Python | Nested stacks complicados |
| Testing | pytest + unit tests | sam local |
| Complejidad | Mayor setup inicial | Más simple para APIs básicas |

**Repository Pattern**: separa "cómo accedo a los datos" de "qué hago con los datos". La Lambda no sabe si está hablando con DynamoDB real o LocalStack — eso lo decide la variable de entorno `AWS_ENDPOINT_URL`.
