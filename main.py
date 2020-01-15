#!/usr/bin/env python3

from absl import logging
from dialogflow_v2.types import WebhookRequest, WebhookResponse, Intent
from google.protobuf import json_format
from typing import Sequence, Optional, TYPE_CHECKING
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import AlwaysOnSampler
import os

from dice_calculator import roll, UnfulfillableRequestError, describe_dice

if TYPE_CHECKING:
    import flask

IN_CLOUD = "GCP_PROJECT" in os.environ

if IN_CLOUD:
    from google.cloud import error_reporting
    from opencensus.ext.stackdriver import trace_exporter

if "LOG_LEVEL" in os.environ:
    logging.set_verbosity(os.environ["LOG_LEVEL"])


def initialize_tracer():
    if IN_CLOUD:
        exporter = trace_exporter.StackdriverExporter(transport=AsyncTransport)
        return Tracer(exporter=exporter, sampler=AlwaysOnSampler())
    else:
        return Tracer(sampler=AlwaysOnSampler())


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
    tracer = initialize_tracer()
    req = WebhookRequest()
    res = WebhookResponse()
    try:
        json_format.Parse(request.data, req, ignore_unknown_fields=True)
        if req.query_result.action == "roll":
            with tracer.span(name='roll'):
                handleRoll(req, res)
    except UnfulfillableRequestError as e:
        logging.exception(e)
        if IN_CLOUD:
            try:
                client = error_reporting.Client()
                client.report_exception(
                    http_context=error_reporting.build_flask_context(request))
            except Exception:
                logging.exception("Failed to send error report to Google")
        add_fulfillment_messages(res, str(e))
    return json_format.MessageToJson(res)
