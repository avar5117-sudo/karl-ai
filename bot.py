import logging
import json
import random
import numpy as np
import threading
from collections import defaultdict, deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === ИНИЦИАЛИЗАЦИЯ ПАМЯТИ ===
memory = deque(maxlen=10000)          # кортежи (вход, ответ, награда)
context_memory = defaultdict(lambda: defaultdict(int))  # переходы
q_table = defaultdict(lambda: defaultdict(float))       # Q-обучение
learning_rate = 0.7
discount = 0.9
epsilon = 0.3

# === ГЕНЕРАТОР ОТВЕТОВ С ПОДКРЕПЛЕНИЕМ ===
def get_reward(user_msg: str, bot_reply: str) -> float:
    # Эвристическая функция награды
    reward = 0.0
    if len(bot_reply) > 20:
        reward += 0.3
    if any(word in user_msg.lower() for word in ["спасибо", "хорошо", "круто", "+"]):
        reward += 1.0
    if any(word in user_msg.lower() for word in ["плохо", "нет", "неверно", "-"]):
        reward -= 0.5
    return reward

def learn_from_experience():
    if len(memory) < 2:
        return
    state, action, reward = memory[-1]
    # Q-learning update
    max_future_q = max(q_table[state].values()) if q_table[state] else 0.0
    q_table[state][action] += learning_rate * (reward + discount * max_future_q - q_table[state][action])

def generate_reply(user_text: str) -> str:
    # Самообучение через генерацию + Q-выбор
    possible_answers = [
        f"Ты сказал: {user_text}. Я запомнил.",
        f"Ответ на '{user_text[:30]}': Я обучаюсь.",
        f"Анализ: {user_text} → паттерн сохранён.",
        f"Твой запрос '{user_text}' добавлен в память.",
        f"SWILL обработал: {user_text}. Награда вычисляется."
    ]
    state_key = user_text[:50]
    if random.uniform(0, 1) < epsilon:
        chosen = random.choice(possible_answers)
    else:
        q_vals = q_table[state_key]
        if q_vals:
            chosen = max(q_vals, key=q_vals.get)
        else:
            chosen = random.choice(possible_answers)
    # Сохраняем опыт
    reward = get_reward(user_text, chosen)
    memory.append((state_key, chosen, reward))
    learn_from_experience()
    # Асинхронный фоновый self-play (дообучение на своих ответах)
    threading.Thread(target=self_play, args=(state_key,), daemon=True).start()
    return chosen

def self_play(state):
    for _ in range(2):  # внутренние итерации самообучения
        fake_reply = generate_reply(state)
        fake_reward = get_reward(state, fake_reply) * 0.5  # заниженная награда для стабильности
        memory.append((state, fake_reply, fake_reward))
        learn_from_experience()

# === TELEGRAM БОТ ===
TOKEN = "8379275346:AAFY_FTvLce-Mi_o05PwcWWkGXPuqyD_WGE"
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("SWILL бот самообучения активен. Пиши что угодно.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    reply = generate_reply(user_text)
    await update.message.reply_text(reply)

# === СОХРАНЕНИЕ ПАМЯТИ ===
def save_memory():
    while True:
        with open("swill_memory.json", "w") as f:
            json.dump(list(memory), f, indent=2)
        threading.Event().wait(60)

if __name__ == "__main__":
    threading.Thread(target=save_memory, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
