#!/usr/bin/env python3
"""
This module contains a Snips app that answers questions about your Snips
assistant.
"""

import pathlib
import importlib
import random
import json
import time

from paho.mqtt.client import Client as pahoClient

from snipskit.apps import SnipsAppMixin
from snipskit.hermes.apps import HermesSnipsApp
from snipskit.mqtt.client import connect as mqtt_connect
from snipskit.hermes.decorators import intent
from snips_app_helpers.snips import Assistant

from services import vocal

assistant_path = "/usr/share/snips/assistant/assistant.json"

MQTT_TOPIC_INJECT = "hermes/injection/perform"

# Use the assistant's language.
i18n = importlib.import_module(
    "translations." + SnipsAppMixin().assistant["language"]
)


class OnBoardingApp(HermesSnipsApp):
    """
    This app answers questions about your Snips assistant.
    """

    def __init__(self, *args, **kwargs):
        self._assistant = Assistant.load(pathlib.Path(assistant_path))
        self._intent_prononciation_table = {
            vocal.tts_prononcable(_): _
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
        self._inject(
            i18n.INTENT_SAMPLE_SLOT_NAME, list(self._intent_prononciation_table)
        )
        print("Onboarding start")
        self._onboarding()
        self.hermes.loop_forever()

    def _inject(self, key, values):
        """
            perform intent name injection which favorize prononication
        """
        print("injection asked")
        self.mqtt.publish(
            MQTT_TOPIC_INJECT,
            payload=str(
                json.dumps({"operations": [["addFromVanilla", {key: values}]]})
            ),
        )

    def tts(self, text):
        self.hermes.publish_start_session_notification(
            site_id=None, custom_data=None, session_initiation_text=text
        )

    def _onboarding(self):
        # once app is up launch startup info
        self.tts(i18n.WELCOME)
        self.tell_hotword()
        self.tell_ask_help()
        # TODO tell Apps Statuses

    def tell_hotword(self):
        self.tts(i18n.CURRENT_HOTWORD_IS % self._assistant.hotword)

    def tell_ask_help(self):
        self.tts(i18n.ASK_FOR_HELP)

    def _chain_tts_response(self, hermes, intent_message, to_speak_list):
        for sitem in to_speak_list:
            hermes.publish_continue_session(intent_message.session_id, sitem)

    @intent(i18n.INTENT_SAMPLE)
    def handle_intent_sample(self, hermes, intent_message):
        """Handle the intent Sample presentation."""

        print("handle intent sample")
        asr_intent_name = intent_message.slots.intentName[0].raw_value
        try:
            intent_name = self._intent_prononciation_table[asr_intent_name]
            sampled_utterances = [
                utterance.text
                for utterance in random.sample(
                    self._assistant.dataset.intent_per_name[
                        intent_name
                    ].utterances,
                    3,
                )
            ]
            self._chain_tts_response(
                hermes, intent_message, [i18n.HERE_IS_EXAMPLES, intent_name]
            )
            for _ in sampled_utterances:
                hermes.publish_continue_session(intent_message.session_id, _)
                time.sleep(.4)
        except KeyError:
            self._chain_tts_response(
                hermes,
                intent_message,
                [
                    i18n.NO_CURRENT_INTENT_IS_NAMED,
                    asr_intent_name,
                    i18n.X_INTENTS,
                    i18n.DO_YOU_WANT_INTENT_LIST,
                ],
            )
            # TODO filter [yes/no] intent
            # TODO launch intent listing
        hermes.publish_end_session(intent_message.session_id, "")


if __name__ == "__main__":
    OnBoardingApp()
