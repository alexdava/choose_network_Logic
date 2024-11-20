import random
import string
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils import executor
import configparser
import logging

logging.basicConfig(level=logging.INFO)

config = configparser.ConfigParser()
config.read("config.ini")
TOKEN = config["BOT"]["token1"]

bot = Bot(token=TOKEN)
storage = RedisStorage2(host="localhost", port=6379)
dp = Dispatcher(bot, storage=storage)


class Form(StatesGroup):
    token_selection = State()
    network_selection = State()
    address_generation = State()


def generate_address(prefix: str, length: int, charset: str) -> str:
    """
    Генерирует адрес для заданной сети.

    :param prefix: Префикс адреса (например, '1' для BTC).
    :param length: Длина основной части адреса (без учета префикса).
    :param charset: Набор символов, из которых создается адрес.
    :return: Сгенерированный адрес.
    """
    return prefix + ''.join(random.choice(charset) for _ in range(length))


NETWORK_FORMATS = {
    "BTC": {"prefix": "1", "length": 33, "charset": "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"},
    "ETH": {"prefix": "0x", "length": 40, "charset": string.hexdigits.lower()},
    "BSC": {"prefix": "0x", "length": 40, "charset": string.hexdigits.lower()},
    "TRON": {"prefix": "T", "length": 33, "charset": "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"}
}

user_state_stack = {}


def push_state(user_id, state):
    if user_id not in user_state_stack:
        user_state_stack[user_id] = []
    user_state_stack[user_id].append(state)


def pop_state(user_id):
    if user_id in user_state_stack and user_state_stack[user_id]:
        return user_state_stack[user_id].pop()
    return None


@dp.message_handler(commands="start", state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    user_state_stack[user_id] = []  # Очищаем стек для нового сеанса
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Выберите монету", callback_data="select_token")
    )
    await message.reply("Добро пожаловать! Нажмите кнопку ниже, чтобы выбрать монету.", reply_markup=keyboard)



@dp.callback_query_handler(lambda c: c.data == "select_token")
async def select_token(callback_query: CallbackQuery):
    push_state(callback_query.from_user.id, Form.token_selection)
    await Form.token_selection.set()
    keyboard = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("TRX", callback_data="token_trx"),
        InlineKeyboardButton("USDT", callback_data="token_usdt"),
        InlineKeyboardButton("ETH", callback_data="token_eth"),
        InlineKeyboardButton("USDC", callback_data="token_usdc"),
        InlineKeyboardButton("BTC", callback_data="token_btc"),
    )
    await callback_query.message.edit_text("Выберите монету:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("token_"), state=Form.token_selection)
async def select_network(callback_query: CallbackQuery, state: FSMContext):
    token = callback_query.data.split("_")[1]
    await state.update_data(token=token)
    push_state(callback_query.from_user.id, Form.network_selection)
    await Form.network_selection.set()

    networks = {
        "trx": ["TRON"],
        "usdt": ["TRON", "ETH", "BSC"],
        "eth": ["ETH"],
        "usdc": ["ETH", "BSC"],
        "btc": ["BTC"]
    }

    keyboard = InlineKeyboardMarkup(row_width=1)
    for network in networks[token]:
        keyboard.add(InlineKeyboardButton(network, callback_data=f"network_{network.lower()}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"),
                 InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

    await callback_query.message.edit_text("Выберите сеть:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("network_"), state=Form.network_selection)
async def generate_network_address(callback_query: CallbackQuery, state: FSMContext):
    network = callback_query.data.split("_")[1].upper()
    data = await state.get_data()
    token = data["token"].upper()


    if network in NETWORK_FORMATS:
        address = generate_address(**NETWORK_FORMATS[network])
    else:
        address = "Неизвестная сеть!"

    push_state(callback_query.from_user.id, Form.address_generation)
    await Form.address_generation.set()

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 Назад", callback_data="back"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )

    await callback_query.message.edit_text(
        f"Вы выбрали:\n\n💼 Сеть: **{network}**\n💰 Монета: **{token}**\n\nСгенерированный адрес: `{address}`",
        reply_markup=keyboard
    )


@dp.callback_query_handler(lambda c: c.data == "back", state="*")
async def go_back(callback_query: CallbackQuery, state: FSMContext):
    prev_state = pop_state(callback_query.from_user.id)
    if prev_state:
        await prev_state.set()
        if prev_state == Form.token_selection:
            await select_token(callback_query)
        elif prev_state == Form.network_selection:
            await select_network(callback_query, state)


@dp.callback_query_handler(lambda c: c.data == "cancel", state="*")
async def cancel_action(callback_query: CallbackQuery, state: FSMContext):
    await state.finish()
    user_state_stack.pop(callback_query.from_user.id, None)  # Очистка стека
    await callback_query.message.edit_text("Операция отменена.")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
