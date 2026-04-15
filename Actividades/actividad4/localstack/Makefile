# ============================================================
#  Makefile — Actividad 4 LocalStack
#  Uso desde la carpeta actividad4/localstack/:
#    make start     → levanta LocalStack en Docker
#    make init      → crea los recursos AWS en LocalStack
#    make test      → smoke-test de los repositories
#    make invoke    → invoca la Lambda de ingesta localmente
#    make status    → muestra el estado de LocalStack
#    make stop      → detiene y elimina el container
#    make clean     → stop + borra el volumen de datos
# ============================================================

.PHONY: start stop clean init init-cdk test invoke status logs

# Endpoint de LocalStack
ENDPOINT ?= http://localhost:4566

# Directorio raíz de actividad4 (padre de localstack/)
ROOT := $(shell cd .. && pwd)

# ----------------------------------------------------------------
# start: levanta LocalStack y espera a que esté sano
# ----------------------------------------------------------------
start:
	@echo "▶ Iniciando LocalStack..."
	docker compose up -d
	@echo "⏳ Esperando a que LocalStack esté listo..."
	@until curl -sf $(ENDPOINT)/_localstack/health | grep -q '"s3": "available"'; do \
		printf '.'; sleep 2; \
	done
	@echo ""
	@echo "✓ LocalStack listo en $(ENDPOINT)"

# ----------------------------------------------------------------
# stop: detiene el container (sin borrar datos)
# ----------------------------------------------------------------
stop:
	docker compose down

# ----------------------------------------------------------------
# clean: stop + borra el volumen persistente
# ----------------------------------------------------------------
clean:
	docker compose down -v
	@echo "✓ Datos de LocalStack eliminados"

# ----------------------------------------------------------------
# init: crea recursos en LocalStack usando boto3 directamente
#       (no requiere Node.js ni aws-cdk-local)
# ----------------------------------------------------------------
init:
	@echo "▶ Inicializando recursos en LocalStack..."
	AWS_ENDPOINT_URL=$(ENDPOINT) python3 $(ROOT)/localstack/init.py

# ----------------------------------------------------------------
# init-cdk: alternativa usando cdklocal (requiere npm i -g aws-cdk-local)
# ----------------------------------------------------------------
init-cdk:
	@echo "▶ Desplegando CDK stacks en LocalStack via cdklocal..."
	cd $(ROOT)/infra/cdk && \
		AWS_ENDPOINT_URL=$(ENDPOINT) \
		AWS_DEFAULT_REGION=us-east-1 \
		AWS_ACCESS_KEY_ID=test \
		AWS_SECRET_ACCESS_KEY=test \
		cdklocal bootstrap && \
		cdklocal deploy --all --require-approval never

# ----------------------------------------------------------------
# test: smoke-test — importa repositories y hace operaciones básicas
# ----------------------------------------------------------------
test:
	@echo "▶ Smoke-test de repositories..."
	AWS_ENDPOINT_URL=$(ENDPOINT) python3 -c "\
import sys; sys.path.insert(0, '$(ROOT)'); \
from repositories.session_repo import SessionRepository; \
from repositories.driver_repo import DriverRepository; \
from repositories.s3_repo import S3Repository; \
print('✓ Imports OK'); \
\
sr = SessionRepository(); \
dr = DriverRepository(); \
s3 = S3Repository(); \
\
sr.save({'session_key': 9999, 'session_name': 'Test Race', 'year': 2024}); \
s = sr.get(9999); \
assert s is not None, 'SessionRepository.get falló'; \
print('✓ SessionRepository OK —', s['session_name']); \
\
dr.save({'session_key': 9999, 'driver_number': 1, 'full_name': 'Max Verstappen', 'team_name': 'Red Bull'}); \
d = dr.get(9999, 1); \
assert d is not None, 'DriverRepository.get falló'; \
print('✓ DriverRepository OK —', d['full_name']); \
\
s3.save_session_raw(9999, {'session_key': 9999, 'test': True}); \
raw = s3.get_session_raw(9999); \
assert raw is not None, 'S3Repository.get_session_raw falló'; \
print('✓ S3Repository OK'); \
\
print('\n✓ Todos los tests pasaron'); \
"

# ----------------------------------------------------------------
# invoke: ejecuta la Lambda de ingesta directamente (sin desplegar)
# ----------------------------------------------------------------
invoke:
	@echo "▶ Invocando Lambda de ingesta localmente (año 2024)..."
	AWS_ENDPOINT_URL=$(ENDPOINT) \
	SESSIONS_TABLE=f1_sessions \
	DRIVER_STATS_TABLE=f1_driver_stats \
	RAW_BUCKET=f1-raw-data \
	python3 -c "\
import sys; sys.path.insert(0, '$(ROOT)'); \
from lambdas.ingest.handler import lambda_handler; \
import json; \
result = lambda_handler({'year': 2024}, {}); \
print(json.dumps(json.loads(result['body']), indent=2)); \
"

# ----------------------------------------------------------------
# status: muestra los recursos actuales en LocalStack
# ----------------------------------------------------------------
status:
	@echo "=== LocalStack Health ==="
	@curl -sf $(ENDPOINT)/_localstack/health | python3 -m json.tool || echo "LocalStack no disponible"
	@echo ""
	@echo "=== Tablas DynamoDB ==="
	@AWS_ENDPOINT_URL=$(ENDPOINT) AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
		aws dynamodb list-tables --endpoint-url $(ENDPOINT) 2>/dev/null || echo "No hay tablas"
	@echo ""
	@echo "=== Buckets S3 ==="
	@AWS_ENDPOINT_URL=$(ENDPOINT) AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
		aws s3 ls --endpoint-url $(ENDPOINT) 2>/dev/null || echo "No hay buckets"

# ----------------------------------------------------------------
# logs: muestra logs del container LocalStack
# ----------------------------------------------------------------
logs:
	docker compose logs -f localstack
