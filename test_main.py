#!/usr/bin/env python3

from main import handleRoll
from dice_calculator import UnfulfillableRequestError

from dialogflow_v2.types import WebhookRequest, WebhookResponse
import unittest


class HandleRollTest(unittest.TestCase):
    def test_dispatches(self):
        req = WebhookRequest()
        req.query_result.parameters["dice_spec"] = "1+1"
        req.query_result.action = "roll"
        res = WebhookResponse()
        handleRoll(req, res)

    def test_graceful_error(self):
        req = WebhookRequest()
        req.query_result.parameters["dice_spec"] = "unparsable gibberish 1dd5"
        req.query_result.action = "roll"
        res = WebhookResponse()
        with self.assertRaisesRegex(UnfulfillableRequestError, '(?i)sorry'):
            handleRoll(req, res)
