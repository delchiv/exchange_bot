import json
import logging
import os
import sys

from telegram.ext import CommandHandler, Updater

from bitcoin_com import Bitcoin_com, Hitbtc_com
from hotcoin_top import Hotcoin_top

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

ALARMS = {}
ALARMS_FILE = os.path.abspath(os.path.join(".", "alarms.json"))
ALARM_TIMEOUT = 60
EXCHANGES = {
    "bitcoin.com": Bitcoin_com(),
    "hitbtc.com": Hitbtc_com(),
    "hotcoin.top": Hotcoin_top(),
}


def save_alarms():
    with open(ALARMS_FILE, "w") as f:
        json.dump(ALARMS, f)


def remove_job_if_exists(name, context):
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def load_alarms(job_queue):
    global ALARMS
    if os.path.exists(ALARMS_FILE):
        with open(ALARMS_FILE, "r") as f:
            ALARMS = json.load(f)
    for chat_id in ALARMS:
        for exchange_name in ALARMS[chat_id]["alarms"]:
            for symbol in ALARMS[chat_id]["alarms"][exchange_name]:
                context = {
                    "chat_id": chat_id,
                    "exchange_name": exchange_name,
                    "symbol": symbol
                }
                job_queue.run_repeating(check_and_alarm, ALARM_TIMEOUT, context=context,
                                        name=f"{chat_id}-{exchange_name}-{symbol}")


def remove_alarm(chat_id, exchange_name, symbol):
    if chat_id in ALARMS:
        if exchange_name in ALARMS[chat_id]["alarms"] and symbol in ALARMS[chat_id]["alarms"][exchange_name]:
            ALARMS[chat_id]["alarms"][exchange_name].pop(symbol)
            save_alarms()
            return True
    return False


def remove(update, context):
    if len(context.args) == 2:
        chat_id = str(update.message.chat_id)
        exchange_name, symbol = tuple(context.args)
        if remove_alarm(chat_id, exchange_name, symbol):
            message = f"Пара {symbol} для {exchange_name} успешно удалена."
            if remove_job_if_exists(f"{chat_id}-{exchange_name}-{symbol}", context):
                message += " Проверка остановлена."
            update.message.reply_text(message)
        else:
            update.message.reply_text(f"Пара {symbol} для {exchange_name} не найдена")
    else:
        update.message.reply_text("Укажите биржу и пару для удаления")


def check_and_alarm(context):
    global ALARMS
    job = context.job

    chat_id = str(job.context["chat_id"])
    exchange_name = job.context["exchange_name"]
    symbol = job.context["symbol"]
    job_name = f"{chat_id}-{exchange_name}-{symbol}"
    if chat_id in ALARMS and exchange_name in ALARMS[chat_id]["alarms"] and \
            symbol in ALARMS[chat_id]["alarms"][exchange_name]:
        timeout = int(ALARMS[chat_id]["alarms"][exchange_name][symbol]["timeout"])
        usd_amount = int(ALARMS[chat_id]["alarms"][exchange_name][symbol]["usd_amount"])
        exchange = EXCHANGES.get(exchange_name)
        if exchange:
            total, amount, currency, rate, start_date, end_date = exchange.get_trades(symbol, timeout)
            print(exchange_name, total, amount, currency, rate, start_date, end_date, usd_amount)
            if total < usd_amount:
                if end_date:
                    # TODO добавить динамеческий формат даты
                    text = f"{exchange_name}\n{symbol} с {start_date:%H:%M:%S} по {end_date:%H:%M:%S} - ${int(total)} < ${int(usd_amount)}"
                    if rate is not None:
                        text += f"\n{amount:5f} {currency} x ${rate:.2f} = ${int(total)}"
                else:
                    text = f"{exchange_name}\nНет торгов {symbol} с {start_date:%Y-%m-%d %H:%M:%S}."
                context.bot.send_message(job.context["chat_id"], text=text)
        else:
            # Возможно, биржа уже не поддерживается
            remove_job_if_exists(job_name, context)
    else:
        # По какой-то случайности вызвался таск, которого не должно быть
        remove_job_if_exists(job_name, context)


def set_alarm(update, context):
    global ALARMS
    if len(context.args) == 4:
        chat_id = str(update.message.chat_id)
        exchange_name, symbol, timeout, usd_amount = tuple(context.args)

        exchange = EXCHANGES.get(exchange_name)
        if not exchange:
            update.message.reply_text(f"Биржа {exchange_name} не найдена. См. /exchanges")
            return

        if chat_id in ALARMS and exchange_name in ALARMS[chat_id]["alarms"] and symbol in ALARMS[chat_id]["alarms"][exchange_name]:
            ALARMS[chat_id]["alarms"][exchange_name][symbol] = {
                "timeout": timeout,
                "usd_amount": usd_amount,
            }
            save_alarms()
            update.message.reply_text(f"Пара {symbol} для {exchange_name} обновлена")
        else:
            if symbol in exchange.get_symbols():
                cnt = {
                    "chat_id": chat_id,
                    "exchange_name": exchange_name,
                    "symbol": symbol
                }
                context.job_queue.run_repeating(check_and_alarm, ALARM_TIMEOUT, context=cnt, name=f"{chat_id}-{exchange_name}-{symbol}")
                if chat_id not in ALARMS:
                    ALARMS[chat_id] = {
                        "alarms": {}
                    }
                if exchange_name not in ALARMS[chat_id]["alarms"]:
                    ALARMS[chat_id]["alarms"][exchange_name] = {}
                ALARMS[chat_id]["alarms"][exchange_name][symbol] = {
                    "timeout": timeout,
                    "usd_amount": usd_amount
                }
                save_alarms()
                update.message.reply_text(f"Пара {symbol} для {exchange_name} успешно добавлена.")
            else:
                update.message.reply_text(f"Недопустимая пара {symbol} для {exchange_name}. /symbols [биржа] - список допустимых пар.")
    else:
        update.message.reply_text("/set <биржа> <пара> <таймаут сек.> <сумма в USD>")


def alarms(update, context):
    chat_id = str(update.message.chat_id)
    if chat_id not in ALARMS:
        update.message.reply_text("Нет активных напоминаний")
        return

    exchange_name = ""
    if len(context.args):
        exchange_name = context.args[0]
    if exchange_name and exchange_name not in EXCHANGES:
        update.message.reply_text(f"Биржа {exchange_name} не найдена. См. /exchanges")
        return

    exchange_names = [exchange_name]
    if not exchange_name:
        exchange_names = ALARMS[chat_id]["alarms"].keys()

    result = []
    for exchange_name in exchange_names:
        if exchange_name in ALARMS[chat_id]["alarms"]:
            for symbol, constraints in ALARMS[chat_id]["alarms"][exchange_name].items():
                result.append("{exchange_name} {symbol} {timeout} {usd_amount}".format(symbol=symbol, exchange_name=exchange_name, **constraints))
    if result:
        update.message.reply_text("\n".join(result))
    else:
        update.message.reply_text("Нет активных напоминаний")


def symbols(update, context):
    if len(context.args):
        exchange_name = context.args[0]
        if exchange_name in EXCHANGES:
            symbols = EXCHANGES[exchange_name].get_symbols()
            update.message.reply_text("\n".join(list(symbols.keys())))
        else:
            update.message.reply_text(f"Биржа {exchange_name} не найдена. См. /exchanges")
    else:
        symbols = set()
        for exchange_name in EXCHANGES:
            if not symbols:
                symbols = set(EXCHANGES[exchange_name].get_symbols().keys())
            else:
                symbols.intersection(set(EXCHANGES[exchange_name].get_symbols().keys()))
        update.message.reply_text("\n".join(list(symbols)))


def exchanges(update, context):
    update.message.reply_text("\n".join(list(EXCHANGES.keys())))


def start(update, context):
    help_text = """
/exchanges - список бирж
/symbols [биржа] - список доступных пар для биржи
/alarms [биржа] - список оповещений
/set <биржа> <пара> <таймаут сек.> <сумма в USD>
/remove <биржа> <пара>
/help
    """
    update.message.reply_text(help_text)


def main(token):
    try:
        updater = Updater(token)
    except BaseException:
        logger.info(f"Авторизация при помощи токена {token} не удалась")
        exit(1)

    job_queue = updater.job_queue
    load_alarms(job_queue)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))

    dispatcher.add_handler(CommandHandler("exchanges", exchanges))
    dispatcher.add_handler(CommandHandler("symbols", symbols))
    dispatcher.add_handler(CommandHandler("alarms", alarms))
    dispatcher.add_handler(CommandHandler("remove", remove))
    dispatcher.add_handler(CommandHandler("set", set_alarm))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.info("Необходимо передать токен telegram-бота")
        exit(1)
    token = sys.argv[1]
    main(token)
