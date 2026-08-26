
import os
import uuid
import shutil
import logging
import asyncio
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from PIL import Image


# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", "8000"))

MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "20"))

BASE_DIR = Path("/tmp/tg_converter")
BASE_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("TGConverter")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not PUBLIC_URL:
    raise RuntimeError("PUBLIC_URL environment variable is missing.")


# =========================
# TELEGRAM APPLICATION
# =========================

application = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

app = FastAPI(title="TG Converter Bot")


# =========================
# UTILITIES
# =========================

def safe_name(name: str) -> str:
    name = Path(name or "file").name

    return "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in name
    )


def run_ffmpeg(args):
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-1500:] or
            "FFmpeg conversion failed."
        )


# =========================
# DOWNLOAD TELEGRAM FILE
# =========================

async def download_telegram_file(message, context, workdir):

    telegram_file = None
    original_name = "file"

    if message.document:

        telegram_file = await context.bot.get_file(
            message.document.file_id
        )

        original_name = (
            message.document.file_name
            or "document"
        )

    elif message.photo:

        telegram_file = await context.bot.get_file(
            message.photo[-1].file_id
        )

        original_name = "image.jpg"

    elif message.video:

        telegram_file = await context.bot.get_file(
            message.video.file_id
        )

        original_name = (
            message.video.file_name
            or "video.mp4"
        )

    elif message.audio:

        telegram_file = await context.bot.get_file(
            message.audio.file_id
        )

        original_name = (
            message.audio.file_name
            or "audio"
        )

    elif message.voice:

        telegram_file = await context.bot.get_file(
            message.voice.file_id
        )

        original_name = "voice.ogg"

    elif message.animation:

        telegram_file = await context.bot.get_file(
            message.animation.file_id
        )

        original_name = (
            message.animation.file_name
            or "animation.mp4"
        )

    else:
        return None, None

    local_name = safe_name(original_name)

    local_path = workdir / local_name

    await telegram_file.download_to_drive(
        custom_path=str(local_path)
    )

    return local_path, original_name


# =========================
# FORMAT BUTTONS
# =========================

def get_buttons(path):

    ext = path.suffix.lower()

    # IMAGE
    if ext in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
    }:

        return [

            [
                InlineKeyboardButton(
                    "JPG",
                    callback_data=f"img|jpg|{path.name}"
                ),

                InlineKeyboardButton(
                    "PNG",
                    callback_data=f"img|png|{path.name}"
                ),

                InlineKeyboardButton(
                    "WEBP",
                    callback_data=f"img|webp|{path.name}"
                ),
            ],

            [
                InlineKeyboardButton(
                    "PDF",
                    callback_data=f"img|pdf|{path.name}"
                )
            ],

        ]

    # VIDEO
    if ext in {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm",
    }:

        return [

            [
                InlineKeyboardButton(
                    "MP3",
                    callback_data=f"vid|mp3|{path.name}"
                ),

                InlineKeyboardButton(
                    "M4A",
                    callback_data=f"vid|m4a|{path.name}"
                ),

                InlineKeyboardButton(
                    "WAV",
                    callback_data=f"vid|wav|{path.name}"
                ),
            ],

            [
                InlineKeyboardButton(
                    "MP4",
                    callback_data=f"vid|mp4|{path.name}"
                )
            ],

        ]

    # AUDIO
    if ext in {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".flac",
        ".opus",
    }:

        return [

            [
                InlineKeyboardButton(
                    "MP3",
                    callback_data=f"aud|mp3|{path.name}"
                ),

                InlineKeyboardButton(
                    "WAV",
                    callback_data=f"aud|wav|{path.name}"
                ),

                InlineKeyboardButton(
                    "M4A",
                    callback_data=f"aud|m4a|{path.name}"
                ),
            ],

            [
                InlineKeyboardButton(
                    "OGG",
                    callback_data=f"aud|ogg|{path.name}"
                )
            ],

        ]

    return []


# =========================
# START
# =========================

async def start(update, context):

    await update.message.reply_text(

        "TG Converter Bot\n\n"

        "Image, video ya audio file bhejein.\n"
        "Main available conversion formats ke buttons show karunga.\n\n"

        "/start - Start\n"
        "/help - Help"

    )


# =========================
# HELP
# =========================

async def help_command(update, context):

    await update.message.reply_text(

        "Supported formats:\n\n"

        "IMAGE\n"
        "JPG / PNG / WEBP / BMP / GIF\n"
        "→ JPG / PNG / WEBP / PDF\n\n"

        "VIDEO\n"
        "MP4 / MKV / AVI / MOV / WEBM\n"
        "→ MP3 / M4A / WAV / MP4\n\n"

        "AUDIO\n"
        "MP3 / WAV / M4A / AAC / OGG / FLAC / OPUS\n"
        "→ MP3 / WAV / M4A / OGG\n\n"

        f"Current file limit: {MAX_FILE_MB} MB"

    )


# =========================
# RECEIVE FILE
# =========================

async def handle_file(update, context):

    message = update.message

    workdir = (
        BASE_DIR /
        uuid.uuid4().hex
    )

    workdir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        path, original_name = (
            await download_telegram_file(
                message,
                context,
                workdir
            )
        )

        if not path:
            return

        size_mb = (
            path.stat().st_size /
            (1024 * 1024)
        )

        if size_mb > MAX_FILE_MB:

            await message.reply_text(
                f"File {size_mb:.1f} MB hai.\n"
                f"Current limit {MAX_FILE_MB} MB hai."
            )

            shutil.rmtree(
                workdir,
                ignore_errors=True
            )

            return

        buttons = get_buttons(path)

        if not buttons:

            await message.reply_text(
                "File receive ho gayi, "
                "lekin is format ka converter "
                "abhi enabled nahi hai."
            )

            shutil.rmtree(
                workdir,
                ignore_errors=True
            )

            return

        context.user_data.setdefault(
            "files",
            {}
        )

        context.user_data["files"][
            path.name
        ] = str(path)

        await message.reply_text(

            f"File: {original_name}\n"
            f"Size: {size_mb:.2f} MB\n\n"
            "Conversion format select karein:",

            reply_markup=InlineKeyboardMarkup(
                buttons
            )

        )

    except Exception as e:

        logger.exception(
            "File handling failed"
        )

        await message.reply_text(
            f"Error: {e}"
        )

        shutil.rmtree(
            workdir,
            ignore_errors=True
        )


# =========================
# IMAGE CONVERTER
# =========================

def image_convert(
    source,
    destination,
    output_format
):

    with Image.open(source) as image:

        if output_format == "pdf":

            if image.mode != "RGB":
                image = image.convert("RGB")

            image.save(
                destination,
                "PDF",
                resolution=100
            )

            return

        if output_format in {
            "jpg",
            "jpeg"
        }:

            if image.mode in {
                "RGBA",
                "LA",
                "P"
            }:

                background = Image.new(
                    "RGB",
                    image.size,
                    "white"
                )

                if "A" in image.getbands():

                    background.paste(
                        image,
                        mask=image.getchannel("A")
                    )

                else:

                    background.paste(
                        image.convert("RGBA")
                    )

                image = background

            else:

                image = image.convert("RGB")

        formats = {
            "jpg": "JPEG",
            "png": "PNG",
            "webp": "WEBP",
        }

        image.save(
            destination,
            formats[output_format],
            quality=90,
            optimize=True
        )


# =========================
# AUDIO / VIDEO CONVERTER
# =========================

def media_convert(
    source,
    destination,
    kind,
    output_format
):

    if kind == "vid":

        if output_format == "mp3":

            args = [
                "-i",
                str(source),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(destination),
            ]

        elif output_format == "m4a":

            args = [
                "-i",
                str(source),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(destination),
            ]

        elif output_format == "wav":

            args = [
                "-i",
                str(source),
                "-vn",
                "-c:a",
                "pcm_s16le",
                str(destination),
            ]

        elif output_format == "mp4":

            args = [
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination),
            ]

        else:

            raise ValueError(
                "Unsupported video output."
            )

    else:

        if output_format == "mp3":

            args = [
                "-i",
                str(source),
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(destination),
            ]

        elif output_format == "wav":

            args = [
                "-i",
                str(source),
                "-c:a",
                "pcm_s16le",
                str(destination),
            ]

        elif output_format == "m4a":

            args = [
                "-i",
                str(source),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(destination),
            ]

        elif output_format == "ogg":

            args = [
                "-i",
                str(source),
                "-c:a",
                "libopus",
                "-b:a",
                "128k",
                str(destination),
            ]

        else:

            raise ValueError(
                "Unsupported audio output."
            )

    run_ffmpeg(args)


# =========================
# CONVERSION CALLBACK
# =========================

async def convert_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    try:

        kind, output_format, filename = (
            query.data.split("|", 2)
        )

        files = context.user_data.get(
            "files",
            {}
        )

        source_string = files.get(
            filename
        )

        if not source_string:

            await query.message.reply_text(
                "Original file session expire ho gayi.\n"
                "File dobara send karein."
            )

            return

        source = Path(
            source_string
        )

        if not source.exists():

            await query.message.reply_text(
                "Original file available nahi hai.\n"
                "File dobara send karein."
            )

            return

        destination = source.with_name(
            f"{source.stem}_converted."
            f"{output_format}"
        )

        await query.message.reply_text(
            f"Converting to "
            f"{output_format.upper()}..."
        )

        if kind == "img":

            await asyncio.to_thread(
                image_convert,
                source,
                destination,
                output_format
            )

        else:

            await asyncio.to_thread(
                media_convert,
                source,
                destination,
                kind,
                output_format
            )

        with destination.open("rb") as file:

            await query.message.reply_document(
                document=file,
                filename=destination.name,
                caption=(
                    f"Done: "
                    f"{output_format.upper()}"
                )
            )

    except Exception as e:

        logger.exception(
            "Conversion failed"
        )

        await query.message.reply_text(
            f"Conversion failed:\n{e}"
        )


# =========================
# HANDLERS
# =========================

application.add_handler(
    CommandHandler(
        "start",
        start
    )
)

application.add_handler(
    CommandHandler(
        "help",
        help_command
    )
)

application.add_handler(
    CallbackQueryHandler(
        convert_callback,
        pattern=r"^(img|vid|aud)\|"
    )
)

application.add_handler(
    MessageHandler(
        filters.PHOTO
        | filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
        | filters.ANIMATION,
        handle_file
    )
)


# =========================
# HEALTH CHECK
# =========================

@app.get(
    "/",
    response_class=PlainTextResponse
)
async def health():

    return "TG Converter Bot is running."


# =========================
# TELEGRAM WEBHOOK
# =========================

@app.post(
    "/telegram/webhook"
)
async def telegram_webhook(
    request: Request
):

    data = await request.json()

    update = Update.de_json(
        data,
        application.bot
    )

    await application.process_update(
        update
    )

    return {
        "ok": True
    }


# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup():

    await application.initialize()

    await application.start()

    webhook_url = (
        f"{PUBLIC_URL}"
        f"/telegram/webhook"
    )

    await application.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

    logger.info(
        "Webhook set: %s",
        webhook_url
    )


# =========================
# SHUTDOWN
# =========================

@app.on_event("shutdown")
async def shutdown():

    await application.bot.delete_webhook(
        drop_pending_updates=False
    )

    await application.stop()

    await application.shutdown()


# =========================
# LOCAL RUN
# =========================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT
    )
