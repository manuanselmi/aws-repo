from aws_cdk import (
    Stack,
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
)
from constructs import Construct


class MessagingStack(Stack):

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
            description="Dispara la ingesta F1 cada 5 minutos",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            enabled=False,
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
