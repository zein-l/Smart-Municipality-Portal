from google.cloud import translate_v2 as translate
import os



def translate_text(text, target_language):
    """Translates text into the target language using Google Cloud Translate API."""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-translate-key.json"

    translate_client = translate.Client()

    if isinstance(text, bytes):
        text = text.decode("utf-8")

    result = translate_client.translate(text, target_language=target_language)
    return result["translatedText"]
