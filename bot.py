import requests
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Получаем токены из переменных окружения
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ВРЕМЕННОЕ хранилище просмотренных фильмов (RAM, сбрасывается при перезапуске Railway)
watched_movies = {}

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Введи название фильма, который хочешь найти")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    movies = search_tmdb_movies(query)

    if not movies:
        await update.message.reply_text("❌ Ничего не найдено.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m.get('release_date', '')[:4]})", callback_data=str(m["id"]))]
        for m in movies[:5]
    ]
    await update.message.reply_text("🔍 Выбери фильм:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

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
    caption = f"<b>{title}</b> ({year})\n⭐ iMDb: {rating:.1f}\n🎭 Жанр: {genres}\n⏱ Длительность: {runtime_str}\n\n<tg-spoiler>{overview}</tg-spoiler>"
    keyboard = [[InlineKeyboardButton(watched_mark, callback_data=f"watch_toggle_{movie_id}")]]
    markup = InlineKeyboardMarkup(keyboard)

    poster_path = movie.get('poster_path')
    if poster_path:
        image_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        await message.reply_photo(photo=image_url, caption=caption, parse_mode='HTML', reply_markup=markup)
    else:
        await message.reply_text(caption, parse_mode='HTML', reply_markup=markup)

if __name__ == '__main__':
    print("✅ Бот запущен на Railway!")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_button))

    # 🔥 Удерживаем polling и логируем всё, что приходит
    app.run_polling(allowed_updates=Update.ALL_TYPES)

