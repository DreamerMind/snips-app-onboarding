#!/usr/bin/env python3
"""
This module contains a Snips app that answers questions about your Snips
assistant.
"""

import pathlib
import importlib
import random
import json

from paho.mqtt.client import Client as pahoClient

from snipskit.apps import SnipsAppMixin
from snipskit.hermes.apps import HermesSnipsApp
from snipskit.mqtt.client import connect as mqtt_connect
from snipskit.hermes.decorators import intent
from snips_app_helpers.snips import Assistant

assistant_path = "/usr/share/snips/assistant/assistant.json"

MQTT_TOPIC_INJECT = "hermes/injection/perform"

# Use the assistant's language.
i18n = importlib.import_module(
    "translations." + SnipsAppMixin().assistant["language"]
)


def prononcable(text):
    for _ in "_-,.:/!<>*#[]()=":
        text = text.replace(_, " ")
    text = text.replace("@", "at")
    text = text.replace("&", "and")
    return text.lower()


class OnBoardingApp(HermesSnipsApp):
    """
    This app answers questions about your Snips assistant.
    """

    def __init__(self, *args, **kwargs):
        self._assistant = Assistant.load(pathlib.Path(assistant_path))
        self._intent_prononciation_table = {
            prononcable(_): _
            for _ in self._assistant.dataset.intent_per_name.keys()
        }
        self.mqtt = None

        super(OnBoardingApp, self).__init__(*args, **kwargs)

    def _start(self):
        """Start the event loop to the Hermes object so the component
        starts listening to events and the callback methods are called.
        """
        self.mqtt = pahoClient()
        mqtt_connect(self.mqtt, self.snips.mqtt)
        self._inject()
        print("Onboarding start")
        self.hermes.loop_forever()

    def _inject(self):
        """
            perform intent name injection which favorize prononication
        """
        # TODO analyse If I should keep track of already added or if system
        # is smart enought to discard recompute if there is no  change
        print("injection asked")
        self.mqtt.publish(
            MQTT_TOPIC_INJECT,
            payload=str(
                json.dumps(
                    {
                        "operations": [
                            [
                                "addFromVanilla",
                                {
                                    i18n.INTENT_SAMPLE_SLOT_NAME: list(
                                        self._intent_prononciation_table
                                    )
                                },
                            ]
                        ]
                    }
                )
            ),
        )

    @intent(i18n.INTENT_SAMPLE)
    def handle_intent_sample(self, hermes, intent_message):
        """Handle the intent Sample presentation."""
        print("handle intent sample")
        asr_intent_name = intent_message.slots.intentName[0].raw_value
        intent_name = self._intent_prononciation_table[asr_intent_name]
        sampled_utterances = [
            utterance.text
            for utterance in random.sample(
                self._assistant.dataset.intent_per_name[intent_name].utterances,
                3,
            )
        ]
        result_sentence = i18n.HERE_IS_EXAMPLES % (
            intent_name,
            ". ".join(sampled_utterances),
        )
        hermes.publish_end_session(intent_message.session_id, result_sentence)

    # TODO once app is up launch startup info


if __name__ == "__main__":
    OnBoardingApp()
