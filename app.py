import os
import logging
import io
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# === Конфигурация ===
TG_TOKEN = os.getenv("TG_TOKEN")
HF_URL = os.getenv("HF_URL")

if not TG_TOKEN or not HF_URL:
    raise RuntimeError("TG_TOKEN и/или HF_URL не заданы в переменных среды")

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# === Telegram Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"/start от пользователя {update.effective_user.id}")
    await update.message.reply_text("📸 Отправьте изображение для анализа.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_bytes = await file.download_as_bytearray()
        logging.info(f"📥 Получено изображение от {update.effective_user.id}, размер {len(image_bytes)} байт")

        # Отправка в Hugging Face
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("image", io.BytesIO(image_bytes), filename="image.jpg", content_type="image/jpeg")

            async with session.post(HF_URL, data=form) as resp:
                if resp.status != 200:
                    logging.error(f"❌ Ошибка HF: код {resp.status}")
                    await update.message.reply_text("⚠️ Ошибка инференса (HF недоступен).")
                    return

                result_bytes = await resp.read()
                logging.info(f"✅ Получен результат от HF, размер {len(result_bytes)} байт")
                await update.message.reply_photo(photo=io.BytesIO(result_bytes))

    except Exception as e:
        logging.exception("Ошибка при обработке изображения")
        await update.message.reply_text("⚠️ Ошибка инференса.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await update.message.reply_text("❗️ Пожалуйста, отправьте изображение.")
        return

    try:
        file = await doc.get_file()
        image_bytes = await file.download_as_bytearray()
        logging.info(f"📄 Получен документ-изображение от {update.effective_user.id}, размер {len(image_bytes)} байт")

        # Отправка в HF
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("image", io.BytesIO(image_bytes), filename="document.jpg", content_type="image/jpeg")

            async with session.post(HF_URL, data=form) as resp:
                if resp.status != 200:
                    logging.error(f"❌ Ошибка HF (document): код {resp.status}")
                    await update.message.reply_text("⚠️ Ошибка инференса (HF недоступен).")
                    return

                result_bytes = await resp.read()
                logging.info(f"✅ Ответ HF (document), размер {len(result_bytes)} байт")
                await update.message.reply_photo(photo=io.BytesIO(result_bytes))

    except Exception as e:
        logging.exception("Ошибка при обработке документа")
        await update.message.reply_text("⚠️ Ошибка инференса.")

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Пожалуйста, отправьте изображение.")

# === Запуск бота ===
async def main():
    logging.info("🚀 Бот запускается...")

    application = ApplicationBuilder().token(TG_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    application.add_handler(MessageHandler(~(filters.PHOTO | filters.Document.IMAGE), handle_other))

    logging.info("✅ Бот успешно запущен.")
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    asyncio.run(main())
