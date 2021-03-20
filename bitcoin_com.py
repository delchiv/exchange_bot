import datetime

import pytz
import requests
from dateutil.parser import parse

utc = pytz.UTC


class Bitcoin_com(object):
    URL = "https://api.exchange.bitcoin.com/api/2"
    SYMBOLS = {}

    def get_symbols(self, force=False):
        if force or not self.SYMBOLS:
            self.SYMBOLS = {}
            response = requests.get(self.URL + "/public/symbol")
            if response.status_code == 200:
                symbols = response.json()
                for symbol in symbols:
                    if symbol["quoteCurrency"] in ("BTC", "ETH", "USD", "USDT"):
                        self.SYMBOLS[symbol["id"]] = symbol
        return self.SYMBOLS

    def get_trades(self, symbol, timeout):
        start_date = datetime.datetime.utcnow() - datetime.timedelta(seconds=timeout)
        start_date = utc.localize(start_date).replace(second=0, microsecond=0)
        data = {
            "limit": 1000,
            "offset": 0,
        }
        trades = []
        response = requests.get(self.URL + f"/public/trades/{symbol}", data)
        while response.status_code == 200:
            data_chunk = response.json()
            trades.extend(data_chunk)
            if parse(trades[-1]["timestamp"]) < start_date:
                break
            # TODO: Проверить правильность работы offset на основе min/max id в каждом из запросов
            data["offset"] += 1000 + 1
            response = requests.get(self.URL + f"/public/trades/{symbol}", data)
        total = 0
        end_date = None
        direct_calc = symbol.endswith("USD") or symbol.endswith("USDT")
        for trade in trades:
            timestamp = parse(trade["timestamp"])
            if timestamp < start_date:
                break
            total += float(trade["quantity"]) * float(trade["price"])
            if not end_date:
                end_date = timestamp

        rate = None
        amount = total
        currency = "USD"
        if not direct_calc:
            if symbol.endswith("BTC"):
                symbol = "BTCUSD"
                if symbol not in self.get_symbols():
                    symbol = "BTCUSDT"
                currency = "BTC"
            elif symbol.endswith("ETH"):
                symbol = "ETHUSD"
                if symbol not in self.get_symbols():
                    symbol = "ETHUSDT"
                currency = "ETH"
            if symbol in self.get_symbols():
                response = requests.get(self.URL + f"/public/ticker/{symbol}")
                if response.status_code == 200:
                    rate = float(response.json()["last"])
                    total = amount * rate
                else:
                    total = 0
            else:
                total = 0

        return total, amount, currency, rate, start_date, end_date


class Hitbtc_com(Bitcoin_com):
    URL = "https://api.hitbtc.com/api/2"
