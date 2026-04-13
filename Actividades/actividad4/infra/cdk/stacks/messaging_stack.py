from aws_cdk import (
    Stack,
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
)
from constructs import Construct


class MessagingStack(Stack):
    """
    Define la regla de EventBridge que dispara la Lambda de ingesta.

    NOTA sobre la frecuencia:
      EventBridge tiene un mínimo de 1 minuto para las reglas de tipo 'rate'.
      No soporta "cada 5 segundos". Para pruebas locales con LocalStack se
      invoca la Lambda directamente (make invoke).
      Esta regla está DESHABILITADA por defecto — activarla manualmente
      cuando se quiera scheduling real.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ingest_function: lambda_.IFunction,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.schedule_rule = events.Rule(
            self,
            "F1IngestScheduleRule",
            rule_name="f1-ingest-schedule",
            description="Dispara la ingesta F1 cada 5 minutos (deshabilitada por defecto)",
            # Minimum rate in EventBridge = 1 minute
            schedule=events.Schedule.rate(Duration.minutes(5)),
            enabled=False,  # Habilitar manualmente en prod o para testing
            targets=[
                targets.LambdaFunction(
                    ingest_function,
                    event=events.RuleTargetInput.from_object(
                        {
                            "source": "eventbridge-schedule",
                            "detail-type": "ScheduledIngest",
                        }
                    ),
                )
            ],
        )
