#!/usr/bin/env python3

import os

from locust import HttpLocust, TaskSet, constant, task


URL_PATH = os.env('URL_PATH','/v1')


class Dice(TaskSet):
    def roll(self, dice_spec):
        self.locust.client.post(URL_PATH, json={
            "queryResult": {
                "action": "roll",
                "queryText": f"Roll {dice_spec}",
                "parameters": {
                    "dice_spec": dice_spec
                }
            }
        })


    @task
    def roll_complex(self):
        self.roll("3d20 + fireball at level 11 + 3d(longsword)")

class WebsiteUser(HttpLocust):
    task_set = Dice
    wait_time = constant(0)

