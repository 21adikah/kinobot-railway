import requests
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from urllib.parse import quote
from HdRezkaApi import HdRezkaSession


hdrezka = HdRezkaSession(origin="http://hdrezka.ag")


TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

watched_movies = {}
awaiting_reply = {}

def add_watched(user_id, movie_id):
    watched_movies.setdefault(str(user_id), set()).add(movie_id)

def remove_watched(user_id, movie_id):
    watched_movies.setdefault(str(user_id), set()).discard(movie_id)

def is_watched(user_id, movie_id):
    return movie_id in watched_movies.get(str(user_id), set())

def search_tmdb_movies(query):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=ru"
    response = requests.get(url)
    return response.json().get("results", [])

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=ru&append_to_response=external_ids"
    return requests.get(url).json()

# /start (личка)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Введи название фильма, который хочешь найти")

# /film (в группе)
async def film_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Найти фильм", callback_data="start_search")]
    ])
    await update.message.reply_text("Нажми кнопку ниже, чтобы начать поиск фильма:", reply_markup=keyboard)

# Нажатие кнопки "Найти фильм"
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_search":
        awaiting_reply[query.from_user.id] = query.message.chat_id
        await query.message.reply_text(
            "✍️ Введите название фильма:",
            reply_markup=ForceReply(selective=True)
        )
        return

    data = query.data
    user_id = query.from_user.id

    if data.startswith("watch_"):
        movie_id = data.split("_")[2]
        if is_watched(user_id, movie_id):
            remove_watched(user_id, movie_id)
        else:
            add_watched(user_id, movie_id)

        movie = get_movie_details(movie_id)
        await send_movie_card(query.message, movie, is_watched(user_id, movie_id))
    else:
        movie = get_movie_details(data)
        await send_movie_card(query.message, movie, is_watched(user_id, data))

# Поиск фильма
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text

    print(f"📨 Сообщение от {user_id} ({chat_id}): {text}")

    # Если ожидаем ввод названия фильма
    if user_id in awaiting_reply:
        chat_id = awaiting_reply.pop(user_id)
    else:
        chat_id = update.effective_chat.id

    movies = search_tmdb_movies(text)
    if not movies:
        await context.bot.send_message(chat_id=chat_id, text="❌ Ничего не найдено.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m.get('release_date', '')[:4]})", callback_data=str(m["id"]))]
        for m in movies[:5]
    ]
    await context.bot.send_message(chat_id=chat_id, text="🔍 Выбери фильм:", reply_markup=InlineKeyboardMarkup(keyboard))

# Отправка карточки
async def send_movie_card(message, movie, is_watched=False):
    movie_id = str(movie['id'])
    title = movie['title']
    year = movie.get('release_date', '')[:4]
    rating = movie.get('vote_average', '–')
    genres = ", ".join([g['name'] for g in movie.get('genres', [])[:2]])
    runtime = movie.get('runtime') or 0
    hours, minutes = divmod(runtime, 60)
    runtime_str = f"{hours}ч {minutes}мин" if hours else f"{minutes}мин"
    overview = movie.get('overview', 'Описание недоступно.')

    watched_mark = "✅ Просмотрено" if is_watched else "🎬 Отметить как просмотренный"
    caption = f"<b>{title}</b> ({year})\n"
    caption += f"⭐ iMDb: {rating:.1f}\n"
    caption += f"🎭 Жанр: {genres}\n"
    caption += f"⏱ Длительность: {runtime_str}\n\n"
    caption += f"<tg-spoiler>{overview}</tg-spoiler>"

    # 🔎 HDRezka-поиск
    try:
        search_results = hdrezka.search(title)
        if search_results:
            rezka_url = search_results[0].url
        else:
            rezka_url = f"//hdrezka.ag/search/?do=search&subaction=search&q={quote(title)}"
    except Exception as e:
        print(f"HDRezka Error: {e}")
        rezka_url = f"https://rezka.ag/search/?q={quote(title)}"

    caption += f"\n\n🔗 <a href=\"{rezka_url}\">Смотреть на HDRezka</a>"

    keyboard = [[InlineKeyboardButton(watched_mark, callback_data=f"watch_toggle_{movie_id}")]]
    markup = InlineKeyboardMarkup(keyboard)

    poster_path = movie.get('poster_path')
    if poster_path:
        image_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        await message.reply_photo(photo=image_url, caption=caption, parse_mode='HTML', reply_markup=markup)
    else:
        await message.reply_text(caption, parse_mode='HTML', reply_markup=markup)

# Запуск
if __name__ == '__main__':
    print("✅ Бот запущен на Railway!")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("film", film_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_button))

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

