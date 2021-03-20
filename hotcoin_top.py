import datetime

import pytz
import requests
from dateutil.parser import parse

utc = pytz.UTC


class Hotcoin_top(object):
    URL = "https://hkapi.hotcoin.top"
    SYMBOLS = {}

    def get_symbols(self, force=False):
        if force or not self.SYMBOLS:
            self.SYMBOLS = {}
            response = requests.get(self.URL + "/v1/market/ticker")
            if response.status_code == 200:
                for ticker in response.json()["ticker"]:
                    symbol = ticker["symbol"].upper().replace("_", "")
                    if symbol.endswith("BTC") or symbol.endswith("ETH") or symbol.endswith("USD") or symbol.endswith("USDT"):
                        self.SYMBOLS[symbol] = ticker["symbol"]
        return self.SYMBOLS

    def get_trades(self, symbol, timeout):
        start_date = datetime.datetime.utcnow() - datetime.timedelta(seconds=timeout)
        start_date = utc.localize(start_date).replace(second=0, microsecond=0)
        hotcoin_symbol = self.SYMBOLS[symbol]
        direct_calc = hotcoin_symbol.endswith("_usd") or hotcoin_symbol.endswith("_usdt")
        response = requests.get(self.URL + f"/v1/trade?count=1000&symbol={hotcoin_symbol}")
        total = 0
        end_date = None
        if response.status_code == 200:
            for trade in response.json()["data"]["trades"]:
                # TODO разобраться с конвертацией дат
                timestamp = utc.localize(parse(trade["time"]) - datetime.timedelta(hours=8))
                if timestamp.time() < start_date.time():
                    break
                total += float(trade["amount"]) * float(trade["price"])
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
                response = requests.get(self.URL + "/v1/market/ticker")
                if response.status_code == 200:
                    hotcoin_symbol = self.SYMBOLS[symbol]
                    for symbol in response.json()["ticker"]:
                        if hotcoin_symbol == symbol["symbol"]:
                            rate = float(symbol["last"])
                            break
                    total = amount * rate
                else:
                    total = 0
            else:
                total = 0

        return total, amount, currency, rate, start_date, end_date
