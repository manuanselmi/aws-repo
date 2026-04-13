import json
import boto3
import os

dynamodb = boto3.resource('dynamodb', endpoint_url="http://host.docker.internal:4566")

# Obtengo el nombre real de la tabla desde las variables de entorno
TABLE_NAME = os.environ.get('TABLE_NAME', 'MiTablaUsuarios')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    body = json.loads(event['body'])
    user_id = body['id']
    nombre = body['nombre']

    # Guardar en DynamoDB
    table.put_item(Item={'id': user_id, 'nombre': nombre})

    return {
        "statusCode": 201,
        "body": json.dumps({"mensaje": "Usuario creado localmente!"})
    }