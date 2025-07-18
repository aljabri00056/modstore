import os
from pyrogram import Client, filters
from pyrogram.types import Message
from loguru import logger
from .models import DecryptionResult


def ipadecryptbot(app_url: str, timeout=300) -> DecryptionResult:
    """
    Decrypts an IPA file using IPADecryptBot on Telegram.
    """

    session_string = os.getenv("SESSION_STRING")
    if not session_string:
        raise EnvironmentError(
            "SESSION_STRING environment variable is not set. Please set it to your Pyrogram session string.")

    def is_ipa(_, __, message: Message) -> bool:
        if message.document and message.document.file_name:
            return message.document.file_name.lower().endswith(".ipa")
        return False

    ipa_filter = filters.create(is_ipa, name="ipa_filter")

    bot_username = "@IPADecryptBot"

    with Client("decrypt_session", session_string=session_string) as app:

        app.send_message(bot_username, app_url)

        file = app.wait_for_message(
            chat_id=bot_username, timeout=timeout, filters=ipa_filter)

        file_path = app.download_media(file)
        version = os.path.basename(file_path).split('-')[1]

        logger.info(f"Downloaded to {file_path}")

        return DecryptionResult(
            file_path=file_path,
            version=version
        )


def decrypt_app(app_url: str, timeout=300) -> DecryptionResult:
    """
    Decrypts an app from App Store.
    """
    try:
        return ipadecryptbot(app_url, timeout)
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise
