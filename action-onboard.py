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
from snipskit.mqtt.client import publish_single
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
        publish_single(
            self.snips.mqtt,
            MQTT_TOPIC_INJECT,
            str(json.dumps({"operations": [["add", {key: values}]]})),
        )

    def tts(self, text):
        self.hermes.publish_start_session_notification(
            site_id=None, custom_data=None, session_initiation_text=text
        )

    def _onboarding(self):
        # once app is up launch startup info
        self.tts(i18n.WELCOME)
        self.tell_hotword()
        self.tell_action_code_list()
        self.tell_ask_help()

    def tell_hotword(self):
        self.tts(i18n.CURRENT_HOTWORD_IS % self._assistant.hotword)

    def tell_ask_help(self):
        self.tts(i18n.ASK_FOR_HELP)

    def tell_action_code_list(self):
        # taken from action code
        # https://github.com/koenvervloesem/snips-app-assistant-information
        apps = [
            str(app)
            for app in (
                pathlib.Path(self.assistant.filename).parent / "snippets"
            ).iterdir()
        ]
        apps = [vocal.tts_prononcable(app[app.find(".") + 1 :]) for app in apps]
        num_apps = len(apps)
        result_sentence = i18n.LIST_ASSISTANT_APPS % num_apps
        if num_apps < 10:
            result_sentence = result_sentence + " " + ", ".join(apps)
        self.tts(result_sentence)

    def _chain_tts_response(self, hermes, intent_message, to_speak_list):
        for sitem in to_speak_list:
            self.tts(sitem)

    @intent(i18n.INTENT_LIST)
    def handle_intent_list(self, hermes, intent_message):
        self._chain_tts_response(
            hermes,
            intent_message,
            [i18n.HERE_IS_INTENT_LIST]
            + list(self._intent_prononciation_table.keys()),
        )

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
                hermes,
                intent_message,
                [i18n.HERE_IS_EXAMPLES, intent_name] + sampled_utterances,
            )
        except KeyError:
            self._chain_tts_response(
                hermes,
                intent_message,
                [
                    i18n.NO_CURRENT_INTENT_IS_NAMED,
                    asr_intent_name,
                    i18n.X_INTENTS
                    % len(self._assistant.dataset.intent_per_name.keys()),
                ],
            )

        hermes.publish_end_session(intent_message.session_id, "")


if __name__ == "__main__":
    OnBoardingApp()
