
import pyttsx3


class SpeechEngine:
    def __init__(self, rate=155, volume=1.0):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self.engine.setProperty("volume", volume)

    def list_voices(self):
        voices = self.engine.getProperty("voices")

        for index, voice in enumerate(voices):
            print(f"{index}: {voice.name}")

    def set_voice(self, index):
        voices = self.engine.getProperty("voices")

        if 0 <= index < len(voices):
            self.engine.setProperty(
                "voice", voices[index].id
            )
        else:
            print("Invalid voice selection.")

    def speak(self, text):
        if not text.strip():
            return

        self.engine.say(text)
        self.engine.runAndWait()

    def set_speed(self, speed):
        self.engine.setProperty("rate", speed)

    def stop(self):
        self.engine.stop()
