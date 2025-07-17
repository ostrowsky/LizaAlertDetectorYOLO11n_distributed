# ---------------- app.py (полностью) ----------------
import os, asyncio, logging, httpx, sys
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters
)

TG_TOKEN = os.getenv("TG_TOKEN")
HF_URL   = os.getenv("HF_URL")          # https://space.hf.space/predict
PORT     = int(os.getenv("PORT", 7860)) # Railway задаёт $PORT

if not TG_TOKEN or not HF_URL:
    raise RuntimeError("TG_TOKEN и/или HF_URL не заданы в переменных среды")

# ---------- HTTP-клиент к Hugging Face ----------
async def call_hf(img_bytes: bytes) -> bytes:
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(
            HF_URL, files={"image": ("img.jpg", img_bytes, "image/jpeg")}
        )
    r.raise_for_status()
    return r.content

# ---------------- Telegram -----------------
async def start(update: Update, _):
    await update.message.reply_text("👋 Пришли фото — отмечу людей.")

async def handle_img(update: Update, _):
    photo = update.message.photo[-1]
    img_bytes = await (await photo.get_file()).download_as_bytearray()
    try:
        result = await call_hf(img_bytes)
        await update.message.reply_photo(photo=result)
    except Exception:
        logging.exception("HF inference error")
        await update.message.reply_text("⚠️ Ошибка инференса")

async def handle_doc(update: Update, _):
    if not update.message.document.mime_type.startswith("image/"):
        return await update.message.reply_text("📄 Пришлите изображение.")
    file = await update.message.document.get_file()
    await handle_img(Update.de_json({"photo":[{"file_id":file.file_id}]}, _), _)

async def handle_other(update: Update, _):
    await update.message.reply_text("📸 Отправьте изображение.")

# -------------- Flask (index + predict) -------------
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "✅ LizaAlert bot alive"

# простой прокси для тестов (curl /predict -F image=@img.jpg)
@flask_app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify(error="no image"), 400
    img_bytes = request.files["image"].read()
    result = asyncio.run(call_hf(img_bytes))
    return result, 200, {"Content-Type":"image/jpeg"}

# ---------- Запуск: Flask + long-polling -------------
async def main():
    tg_app = ApplicationBuilder().token(TG_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_img))
    tg_app.add_handler(MessageHandler(filters.Document.IMAGE, handle_doc))
    tg_app.add_handler(MessageHandler(~(filters.PHOTO|filters.Document.IMAGE),
                                      handle_other))

    await asyncio.gather(
        tg_app.run_polling(),
        flask_app.run_task(host="0.0.0.0", port=PORT)
    )

if name == "__main__":
    import nest_asyncio; nest_asyncio.apply()
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout)
    asyncio.run(main())