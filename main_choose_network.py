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

@dp.message_handler(commands="start", state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Выберите монету", callback_data="select_token")
    )
    await message.reply("Добро пожаловать! Нажмите кнопку ниже, чтобы выбрать монету.", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "select_token")
async def select_token(callback_query: CallbackQuery):
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
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_token"),
                 InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

    await callback_query.message.edit_text("Выберите сеть:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("network_"), state=Form.network_selection)
async def finalize_selection(callback_query: CallbackQuery, state: FSMContext):
    network = callback_query.data.split("_")[1].upper()
    data = await state.get_data()
    token = data["token"].upper()

    await state.finish()
    await callback_query.message.edit_text(
        f"Вы выбрали:\n\n💼 Сеть: **{network}**\n💰 Монета: **{token}**"
    )

@dp.callback_query_handler(lambda c: c.data == "back_to_token", state=Form.network_selection)
async def back_to_token(callback_query: CallbackQuery):
    await select_token(callback_query)

@dp.callback_query_handler(lambda c: c.data == "cancel", state="*")
async def cancel_action(callback_query: CallbackQuery, state: FSMContext):
    await state.finish()
    await callback_query.message.edit_text("Операция отменена.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
