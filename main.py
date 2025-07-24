import os
import yt_dlp
import requests
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "7059319217:AAFDvse9R6O55rnMuiUjTO1Fam2qqwLv7ow"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_url_dict = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("請傳送影片網址給我，我會幫你下載影片。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("請傳送一個正確的影片網址。")
        return

    user_id = update.message.from_user.id
    user_url_dict[user_id] = url

    keyboard = [
        [InlineKeyboardButton("🎥 高畫質影片", callback_data="video_best")],
        [InlineKeyboardButton("📱 中畫質影片", callback_data="video_mid")],
        [InlineKeyboardButton("🎵 音訊 (MP3)", callback_data="audio_mp3")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("請選擇你要下載的格式：", reply_markup=reply_markup)

def build_ydl_opts(format_code: str, is_audio=False):
    opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'quiet': True
    }

    if is_audio:
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        opts['format'] = format_code

    return opts

def download_media(url: str, ydl_opts) -> str:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info).replace(".webm", ".mp3") if 'postprocessors' in ydl_opts else ydl.prepare_filename(info)

def upload_to_transfersh(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        file_name = os.path.basename(file_path)
        response = requests.put(f'https://transfer.sh/{file_name}', data=f)
        if response.status_code == 200:
            return response.text.strip()
        else:
            raise Exception(f"上傳失敗：{response.status_code} {response.text}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_url_dict:
        await query.edit_message_text("請先傳送影片網址。")
        return

    url = user_url_dict[user_id]
    choice = query.data
    format_code = 'best'
    is_audio = False

    if choice == "video_best":
        format_code = 'best[ext=mp4]'
    elif choice == "video_mid":
        format_code = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
    elif choice == "audio_mp3":
        is_audio = True

    await query.edit_message_text("下載中，請稍候...")

    try:
        ydl_opts = build_ydl_opts(format_code, is_audio)
        filepath = download_media(url, ydl_opts)
        file_size = os.path.getsize(filepath)

        if file_size < 49 * 1024 * 1024:
            await query.message.reply_document(InputFile(filepath)) if is_audio else await query.message.reply_video(InputFile(filepath))
        else:
            await query.message.reply_text("檔案太大，正在上傳到 transfer.sh ...")
            link = upload_to_transfersh(filepath)
            await query.message.reply_text(f"✅ 下載完成：\n{link}")
    except Exception as e:
        await query.message.reply_text(f"❌ 發生錯誤：{e}")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()
