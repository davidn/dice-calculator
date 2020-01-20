#!/usr/bin/env python3

import os
import json
import logging as py_logging
from datetime import datetime, timezone

from absl import logging
from dialogflow_v2.types import WebhookRequest, WebhookResponse, Intent
from google.cloud import error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
from google.protobuf import json_format
from typing import Sequence, Optional, TYPE_CHECKING
from opencensus.common.transports.async_ import AsyncTransport
from opencensus.trace import (
    tracer, samplers, execution_context, print_exporter, logging_exporter)
from opencensus.trace.propagation import (
    google_cloud_format, trace_context_http_header_format)
from opencensus.ext.stackdriver import trace_exporter

from dice_calculator import roll, describe_dice
from exceptions import UnfulfillableRequestError

if TYPE_CHECKING:
    import flask


STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "")


if LOG_HANDLER == 'absl':
    logging.use_absl_handler()
elif LOG_HANDLER == "stackdriver":
    client = google.cloud.logging.Client()
    handler = google.cloud.logging.handlers.CloudLoggingHandler(client)
    google.cloud.logging.handlers.setup_logging(handler)
elif LOG_HANDLER == 'structured':
    class StructureLogFormater(py_logging.Formatter):
        def format(self, record):
            context = execution_context.get_opencensus_tracer().span_context
            structured = {
                "message": super().format(record),
                "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "severity": record.levelname,
                "logging.googleapis.com/trace": "projects/%s/traces/%s" % (
                    PROJECT_ID, context.trace_id),
                "logging.googleapis.com/sourceLocation": {
                    "file": record.filename,
                    "line": record.lineno,
                    "function": record.funcName
                }
            }
            if context.span_id:
                structured["logging.googleapis.com/spanId"] = context.span_id
            return json.dumps(structured)
    handler = py_logging.StreamHandler()
    handler.setFormatter(StructureLogFormater())
    py_logging.getLogger().addHandler(handler)
if "LOG_LEVEL" in os.environ:
    logging.set_verbosity(os.environ["LOG_LEVEL"])


def initialize_tracer(request: 'flask.Request') -> tracer.Tracer:
    if TRACE_PROPAGATE == "google":
        propagator = google_cloud_format.GoogleCloudFormatPropagator()
    else:
        propagator = trace_context_http_header_format.TraceContextPropagator()
    if TRACE_EXPORTER == "stackdriver":
        exporter = trace_exporter.StackdriverExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    elif TRACE_EXPORTER == "log":
        exporter = logging_exporter.LoggingExporter(
            handler=py_logging.NullHandler(), transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    elif TRACE_EXPORTER == "stdout":
        exporter = print_exporter.PrintExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    else:
        exporter = print_exporter.PrintExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOffSampler()
    span_context = propagator.from_headers(request.headers)
    return tracer.Tracer(exporter=exporter, sampler=sampler,
                         propagator=propagator, span_context=span_context)


def add_fulfillment_messages(
        res: WebhookResponse, display_text: str,
        ssml: Optional[str] = None, suggestions: Sequence[str] = None):
    res.fulfillment_messages.add().text.text.append(display_text)

    fulfillment_message = res.fulfillment_messages.add()
    fulfillment_message.platform = Intent.Message.ACTIONS_ON_GOOGLE
    sr = fulfillment_message.simple_responses.simple_responses.add()
    sr.display_text = display_text
    sr.ssml = ssml if ssml else f"<speak>{display_text}</speak>"

    if suggestions:
        fulfillment_message = res.fulfillment_messages.add()
        fulfillment_message.platform = Intent.Message.ACTIONS_ON_GOOGLE
        for suggestion in suggestions:
            fulfillment_message.suggestions.suggestions.add().title = "Re-roll"


def handleRoll(req: WebhookRequest, res: WebhookResponse):
    dice_spec = req.query_result.parameters["dice_spec"]
    logging.info("Requested roll: %s", dice_spec)
    roll_result, dice_results = roll(dice_spec)
    logging.info("Final result: %s", roll_result)
    dice_description = describe_dice(dice_results)
    add_fulfillment_messages(
        res,
        f"You rolled a total of {roll_result}{dice_description}",
        f"<speak><audio src=\"https://actions.google.com/sounds/v1/impacts/wo"
        f"od_rolling_short.ogg\"/>You rolled a total of {roll_result}</speak>",
        ["Re-roll"]
    )
    context = res.output_contexts.add()
    context.name = req.session + "/contexts/roll-followup"
    context.lifespan_count = 2
    context.parameters["roll_result"] = roll_result
    context.parameters["dice_results"] = dice_results


def handleHttp(request: 'flask.Request') -> str:
    tracer = initialize_tracer(request)
    req = WebhookRequest()
    res = WebhookResponse()
    try:
        json_format.Parse(request.data, req, ignore_unknown_fields=True)
        if req.query_result.action == "roll":
            with tracer.span(name='roll'):
                handleRoll(req, res)
    except UnfulfillableRequestError as e:
        logging.exception(e)
        if STACKDRIVER_ERROR_REPORTING:
            try:
                client = error_reporting.Client()
                client.report_exception(
                    http_context=error_reporting.build_flask_context(request))
            except Exception:
                logging.exception("Failed to send error report to Google")
        add_fulfillment_messages(res, str(e))
    return json_format.MessageToJson(res)
