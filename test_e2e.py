#!/usr/bin/env python3

from flask import Flask, request
import unittest
import json

from main import handleHttp


class E2ETest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        @self.app.route('/', methods=['GET', 'POST'])
        def index():
            return handleHttp(request)
        self.app.testing = True
        self.client = self.app.test_client()

    def test_basic(self):
        resp = self.client.post(
            json={"query_result": {"action": "roll", "parameters": {"dice_spec": "3"}}}
        )
        resp_json = json.loads(resp.data)
        text = resp_json["fulfillmentMessages"][0]["text"]["text"][0]
        self.assertIn("3", text)

        aog1 = resp_json["fulfillmentMessages"][1]
        self.assertEqual("ACTIONS_ON_GOOGLE", aog1["platform"])
        self.assertIn("3", aog1["simpleResponses"]["simpleResponses"][0]["ssml"])
        self.assertIn("3", aog1["simpleResponses"]["simpleResponses"][0]["displayText"])

        aog2 = resp_json["fulfillmentMessages"][2]
        self.assertEqual("ACTIONS_ON_GOOGLE", aog2["platform"])
        self.assertEqual("Re-roll", aog2["suggestions"]["suggestions"][0]["title"])


if __name__ == '__main__':
    unittest.main()
