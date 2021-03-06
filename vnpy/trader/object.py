"""
Basic data structure used for general trading function in VN Trader.
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO
import pandas as pd
from termcolor import colored
from .constant import Direction, Exchange, Interval, Offset, Status, Product, OptionType, OrderType, MarketEvent
import numpy as np
#from .calc import BarFeature, VlineFeature

ACTIVE_STATUSES = set([Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED])


@dataclass
class BaseData:
    """
    Any data object needs a gateway_name as source
    and should inherit base data.
    """

    gateway_name: str


@dataclass
class TickData(BaseData):
    """
    Tick data contains information about:
        * last trade in market
        * orderbook snapshot
        * intraday market statistics.
    """

    symbol: str
    exchange: Exchange
    datetime: datetime

    name: str = ""
    volume: float = 0
    open_interest: float = 0
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0
    direction: Direction = None

    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def __str__(self):
        return '%s P:%.3f V:%.8f Bid:%.8f Ask:%.8f %s %s' % (self.symbol, self.last_price, self.last_volume, self.bid_price_1, self.ask_price_1, self.exchange, self.datetime)


class MarketEventData:
    def __init__(self, event_type: MarketEvent = MarketEvent.NONE, event_datetime: datetime = None):
        self.event_type = event_type
        if event_datetime is None:
            self.event_datetime = None
        else:
            self.event_datetime = event_datetime

    def __str__(self):
        return f'{self.event_datetime} {self.event_type.value}'

# class MarketEventData(BaseData):
#     def __init__(self, symbol: str = None,
#                  exchange: Exchange = None,
#                  gateway_name: str = None,
#                  open_time: datetime = None,
#                  close_time: datetime = None):
#         self.symbol = symbol
#         self.exchange = exchange
#         self.gateway_name = gateway_name
#         self.open_time = open_time
#         self.close_time = close_time
#
#         # default event is None
#         self.event: MarketEvent = None
#
#     def init_by_vlines(self, vlines: list = []):
#         if len(vlines) > 0:
#             self.symbol = vlines[0].symbol
#             self.exchange = vlines[0].exchange
#             self.gateway_name = vlines[0].gateway_name
#             self.open_time = vlines[0].open_time
#             self.close_time = vlines[-1].close_time
#
#     def is_empty(self):
#         if not self.event and not self.open_time and not self.close_time:
#             return True
#         else:
#             return False
#
#     def __str__(self):
#         if self.is_empty():
#             return None
#         else:
#             return '%s %s %s %s %s' % (self.event.value, self.symbol, self.exchange.value, self.open_time, self.close_time)


class DistData(BaseData):
    """
    Price distribution of ticks
    """
    def __init__(self, bin_size=1.0,
                 symbol: str = 'BTCUSDT',
                 exchange: Exchange = Exchange.HUOBI,
                 gateway_name: str = None,
                 open_time: datetime = None,
                 close_time: datetime = None):
        self.bin_size = bin_size
        self.symbol = symbol
        self.exchange = exchange
        self.gateway_name = gateway_name
        self.open_time = open_time
        self.close_time = close_time
        self.dist = {}
        self.volume = 0
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def add_tick(self, tick: TickData):
        if self.symbol == tick.symbol and self.exchange == tick.exchange:
            #key = int(tick.last_price)
            key = int(tick.last_price/self.bin_size)
            vol = tick.last_volume
            self.volume += vol
            if key in self.dist:
                self.dist[key] += vol
            else:
                self.dist[key] = vol

    def add_trade(self, trade):
        if self.vt_symbol == trade.vt_symbol:
            key = int(trade.price/self.bin_size)
            vol = trade.volume
            self.volume += vol
            if key in self.dist:
                self.dist[key] += vol
            else:
                self.dist[key] = vol

    def init_by_dist(self, dist):
        self.bin_size = dist.bin_size
        self.symbol = dist.symbol
        self.exchange = dist.exchange
        self.gateway_name = dist.gateway_name
        self.open_time = dist.open_time
        self.close_time = dist.close_time
        self.dist = dist.dist.copy()
        self.volume = dist.volume

    def calc_dist(self, ticks: list = []):
        t0 = ticks[0]
        tend = ticks[-1]
        self.symbol = t0.symbol
        self.exchange = t0.exchange
        self.gateway_name = t0.gateway_name
        self.open_time = t0.datetime
        self.close_time = tend.datetime
        dist = {}
        total_vol = 0
        for t in ticks:
            key = int(t.last_price/self.bin_size)
            vol = t.last_volume
            total_vol += vol
            if key in dist:
                dist[key] += vol
            else:
                dist[key] = vol
        self.dist = dist
        self.volume = total_vol

    def calc_dist_trades(self, trades: list = []):
        t0 = trades[0]
        tend = trades[-1]
        self.symbol = t0.symbol
        self.exchange = t0.exchange
        self.gateway_name = t0.gateway_name
        self.open_time = t0.datetime
        self.close_time = tend.datetime
        dist = {}
        total_vol = 0
        for t in trades:
            key = int(t.price/self.bin_size)
            vol = t.volume
            total_vol += vol
            if key in dist:
                dist[key] += vol
            else:
                dist[key] = vol
        self.dist = dist
        self.volume = total_vol

    # def calc_teeterboard(self, ticks, avg_price):
    #     # func = lambda t, v: ((t.last_price-v)/v)*t.last_volume
    #     weight = sum([func(t, avg_price) for t in ticks])
    #     return weight

    def total_vol(self):
        if self.volume <= 0:
            self.volume = sum(self.dist.values())
            return self.volume
        else:
            return self.volume

    def less_vol(self, price: float = 0):
        return sum([self.dist[k] for k in self.dist if price > k])

    def __add__(self, other):
        if self.symbol == other.symbol and self.exchange == other.exchange:
            self.open_time = min(self.open_time, other.open_time)
            self.close_time = max(self.close_time, other.close_time)
            for d in other.dist:
                if d in self.dist:
                    self.dist[d] += other.dist[d]
                else:
                    self.dist[d] = other.dist[d]
            self.volume += other.volume
        return self

    def __str__(self):
        ss = [str(k) + ' ' + '%.3f' % v + ' ' for k, v in sorted(self.dist.items(), key=lambda x: x[0])]
        return ''.join(ss)

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


class BarFeature:
    def __init__(self):
        pass


@dataclass
class BarData(BaseData):
    """
    Candlestick bar data of a certain trading period.
    """

    symbol: str = 'BTCUSDT'
    exchange: Exchange = Exchange.HUOBI
    datetime: datetime = None

    interval: Interval = None
    volume: float = 0
    amount: float = 0
    count: int = 0
    open_time: datetime = None
    open_interest: float = 0
    open_price: float = None
    high_price: float = None
    low_price: float = None
    close_price: float = None
    gateway_name: str = 'HUOBI'

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def init_by_tick(self, tick: TickData, interval: Interval = Interval.MINUTE):
        self.symbol = tick.symbol
        self.exchange = tick.exchange
        self.datetime = tick.datetime.replace(second=0, microsecond=0)
        self.interval = interval
        self.volume = tick.last_volume
        self.open_price = tick.last_price
        self.close_price = tick.last_price
        self.high_price = tick.last_price
        self.low_price = tick.last_price
        self.gateway_name = tick.gateway_name

    def add_tick(self, tick: TickData):
        if self.symbol == tick.symbol and self.exchange == tick.exchange:
            self.volume = self.volume + tick.last_volume
            self.close_price = tick.last_price
            self.high_price = max(self.high_price, tick.last_price)
            self.low_price = min(self.low_price, tick.last_price)

    def __str__(self):
        return '%s O:%.3f C:%.3f H:%.3f L:%.3f V:%.3f A:%.3f OT:%s I:%s' % (self.symbol, self.open_price, self.close_price,
                                                                            self.high_price, self.low_price,
                                                                            self.volume, self.amount, self.open_time, self.interval.value)

    def is_empty(self):
        if not self.high_price:
            return True
        if not self.low_price:
            return True
        if not self.open_price:
            return True
        if not self.close_price:
            return True
        return False


class TradeData(BaseData):
    """
    Trade data contains information of a fill of an order. One order
    can have several trade fills.
    """
    def __init__(self, symbol: str, exchange: Exchange, gateway_name: str, price: float = 0,
                 volume: float = 0, datetime: datetime = None, direction: Direction = Direction.NONE,
                 orderid: str = None, tradeid: str = None):
        self.symbol = symbol
        self.exchange = exchange
        self.orderid = orderid
        self.tradeid = tradeid
        self.direction = direction

        self.offset = Offset.NONE
        self.price = float(np.round(price, 4))
        self.volume = float(np.round(volume, 4))
        self.datetime = datetime

        self.gateway_name = gateway_name

        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"
        self.vt_tradeid = f"{self.gateway_name}.{self.tradeid}"

    def __str__(self):
        pstr = f"{self.vt_symbol} {self.price} {self.volume} {self.direction.value} {self.datetime}"
        return pstr


class OrderBookData(BaseData):
    """Market Depth Data Structure"""
    def __init__(self, symbol: str, exchange: Exchange, gateway_name: str,
                 time: datetime, seq_num: int, pre_seq_num: int, bids: dict, asks: dict):
        self.symbol = symbol
        self.exchange = exchange
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.gateway_name = gateway_name
        self.time = time
        self.seq_num = seq_num
        # pre_seq_num=0 means refresh order book
        self.pre_seq_num = pre_seq_num
        self.bids = bids
        self.asks = asks

    def update(self, seq_num: int, pre_seq_num: int, time: datetime, bids: dict, asks: dict):
        if pre_seq_num == self.seq_num:
            self.seq_num = seq_num
            self.time = time
            if len(bids) > 0:
                for k in bids:
                    self.bids[k] = bids[k]
                self.bids = dict(sorted([t for t in self.bids.items() if t[1] > 0.01], key=lambda x: x[0], reverse=True))
            if len(asks) > 0:
                for k in asks:
                    self.asks[k] = asks[k]
                self.asks = dict(sorted([t for t in self.asks.items() if t[1] > 0.01], key=lambda x: x[0]))

    def refresh(self, seq_num: int, time: datetime, bids: dict, asks: dict):
        self.pre_seq_num = self.seq_num
        self.seq_num = seq_num
        self.time = time
        self.bids = dict(sorted(self.bids.items(), key=lambda x: x[0], reverse=True))
        self.asks = dict(sorted(self.asks.items(), key=lambda x: x[0]))

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def __str__(self):
        strs = f"{self.vt_symbol} {self.seq_num} Ask:{len(self.asks)} Bid:{len(self.bids)}"
        return strs


@dataclass
class VlineData(BaseData):
    """
    Candlestick vline data of a certain trading volume.
    """

    symbol: str = 'BTCUSDT'
    exchange: Exchange = Exchange.HUOBI
    gateway_name: str = None

    open_time: datetime = None
    close_time: datetime = None

    volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    open_price: float = None
    high_price: float = None
    low_price: float = None
    close_price: float = None
    avg_price: float = 0
    ticks = []
    trades = []

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def __add__(self, other):
        if other.symbol == self.symbol and other.exchange == self.exchange:
            self.open_time = min([self.open_time, other.open_time])
            self.close_time = max([self.close_time, other.close_time])
            self.avg_price = (self.avg_price * self.volume + other.avg_price * other.volume) / (self.volume+other.volume)

            self.volume += other.volume
            self.buy_volume += other.buy_volume
            self.sell_volume += other.sell_volume

            if self.open_time < other.open_time and self.close_time < other.close_time:
                self.open_price = self.open_price
                self.close_price = other.close_price
            else:
                self.open_price = other.open_price
                self.close_price = self.close_price
            self.high_price = max(self.high_price, other.high_price)
            self.low_price = min(self.low_price, other.low_price)
            self.ticks.extend(other.ticks)
        return self

    def init_by_tick(self, tick: TickData):
        self.symbol = tick.symbol
        self.exchange = tick.exchange
        self.open_time = tick.datetime
        self.close_time = tick.datetime

        self.volume = tick.last_volume
        if tick.direction == Direction.LONG:
            self.buy_volume = tick.last_volume
        elif tick.direction == Direction.SHORT:
            self.sell_volume = tick.last_volume
        else:
            pass

        self.avg_price = tick.last_price
        self.open_price = tick.last_price
        self.close_price = tick.last_price
        self.high_price = tick.last_price
        self.low_price = tick.last_price
        self.gateway_name = tick.gateway_name

        self.ticks.append(tick)

    def init_by_trade(self, trade: TradeData):
        self.symbol = trade.symbol
        self.exchange = trade.exchange
        self.open_time = trade.datetime
        self.close_time = trade.datetime

        self.volume = trade.volume
        if trade.direction == Direction.LONG:
            self.buy_volume = trade.volume
        elif trade.direction == Direction.SHORT:
            self.sell_volume = trade.volume
        else:
            pass
        self.avg_price = trade.price
        self.open_price = trade.price
        self.close_price = trade.price
        self.high_price = trade.price
        self.low_price = trade.price
        self.gateway_name = trade.gateway_name

        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

        self.trades.append(trade)

    def init_by_vline(self, vline):
        self.symbol = vline.symbol
        self.exchange = vline.exchange
        self.open_time = vline.open_time
        self.close_time = vline.open_time

        self.volume = vline.volume
        self.buy_volume = vline.buy_volume
        self.sell_volume = vline.sell_volume

        self.avg_price = vline.avg_price
        self.open_price = vline.open_price
        self.close_price = vline.close_price
        self.high_price = vline.high_price
        self.low_price = vline.low_price
        self.gateway_name = vline.gateway_name

        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

        self.ticks = vline.ticks.copy()
        self.trades = vline.trades.copy()

    def add_tick(self, tick: TickData):
        if self.symbol == tick.symbol and self.exchange == tick.exchange:
            if self.open_time <= tick.datetime and self.close_time <= tick.datetime:
                self.close_time = tick.datetime

                sum_vol_price = self.avg_price * self.volume
                sum_vol_price = sum_vol_price + tick.last_price * tick.last_volume

                self.volume = self.volume + tick.last_volume
                if tick.direction == Direction.LONG:
                    self.buy_volume = self.buy_volume + tick.last_volume
                elif tick.direction == Direction.SHORT:
                    self.sell_volume = self.sell_volume + tick.last_volume
                else:
                    pass

                self.avg_price = sum_vol_price / self.volume

                if not self.open_price:
                    self.open_price = tick.open_price

                self.close_price = tick.last_price

                if not self.high_price:
                    self.high_price = tick.last_price
                else:
                    self.high_price = max(self.high_price, tick.last_price)

                if not self.low_price:
                    self.low_price = tick.last_price
                else:
                    self.low_price = min(self.low_price, tick.last_price)
                self.ticks.append(tick)

    def add_trade(self, trade: TradeData):
        if self.symbol == trade.symbol and self.exchange == trade.exchange:
            if self.open_time <= trade.datetime and self.close_time <= trade.datetime:
                self.close_time = trade.datetime
                sum_vol_price = self.avg_price * self.volume
                sum_vol_price = sum_vol_price + trade.price * trade.volume

                self.volume = self.volume + trade.volume
                if trade.direction == Direction.LONG:
                    self.buy_volume = self.buy_volume + trade.volume
                elif trade.direction == Direction.SHORT:
                    self.sell_volume = self.sell_volume + trade.volume
                else:
                    pass

                self.avg_price = sum_vol_price / self.volume

                if not self.open_price:
                    self.open_price = trade.price

                self.close_price = trade.price

                if not self.high_price:
                    self.high_price = trade.price
                else:
                    self.high_price = max(self.high_price, trade.price)

                if not self.low_price:
                    self.low_price = trade.price
                else:
                    self.low_price = min(self.low_price, trade.price)
                self.trades.append(trade)

    def is_empty(self):
        if self.volume <= 0:
            return True
        if not self.open_price:
            return True
        if not self.close_price:
            return True
        if not self.high_price:
            return True
        if not self.low_price:
            return True
        return False

    def __str__(self):
        return '%s P:%.3f O:%.3f C:%.3f H:%.3f L:%.3f V:%.8f BV:%.8f SV:%.8f %s OT:%s CT:%s' % (self.symbol, self.avg_price, self.open_price, self.close_price,
                                                                                                self.high_price, self.low_price,
                                                                                                self.volume, self.buy_volume, self.sell_volume,
                                                                                                self.close_time - self.open_time, self.open_time, self.close_time)


@dataclass
class OrderData(BaseData):
    """
    Order data contains information for tracking lastest status
    of a specific order.
    """

    def __init__(self, symbol: str, exchange: Exchange, orderid: str, gateway_name: str,
                 type: OrderType = OrderType.LIMIT, direction: Direction = None, offset: Offset = Offset.NONE,
                 price: float = 0, volume: float = 0, traded: float = 0,
                 remain_amount: float = 0, exec_amount: float = 0, status: Status = Status.SUBMITTING,
                 datetime: datetime = None):
        self.symbol = symbol
        self.exchange = exchange
        self.gateway_name = gateway_name
        self.orderid = orderid
        self.type = type
        self.direction = direction
        self.offset = offset
        self.price = price
        self.volume = volume
        self.traded = traded
        self.remain_amount = remain_amount
        self.exec_amount = exec_amount
        self.status = status
        self.datetime = datetime

        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"

    def is_active(self) -> bool:
        """
        Check if the order is active.
        """
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False

    def create_cancel_request(self) -> "CancelRequest":
        """
        Create cancel request object from order.
        """
        req = CancelRequest(
            orderid=self.orderid, symbol=self.symbol, exchange=self.exchange
        )
        return req

    def __str__(self):
        strs = f'{self.vt_symbol} {self.price} {self.volume} {self.type.value} {self.direction.value} {self.status.value} {self.datetime}'
        return strs


@dataclass
class AccountInfo(BaseData):
    exchange: Exchange
    account_id: str
    account_type: str
    account_subtype: str
    account_state: str

    def __str__(self):
        return f'{self.exchange.value}-{self.account_id}-{self.account_type}-{self.account_subtype}-{self.account_state}'


@dataclass
class BalanceInfo(BaseData):
    exchange: Exchange
    account_id: str
    account_type: str
    account_state: str

    # usdt {'trade': 224.86003307318344, 'frozen': 520.0, 'available': -295.13996692681656}
    # usdt: BalanceData
    data = {}

    def update(self, exchange: Exchange,
               account_id: str,
               account_type: str,
               currency: str,
               available: float = None,
               frozen: float = None,
               volume: float = None):
        #bd = self.data[currency]
        if exchange == self.exchange and account_id == self.account_id:
            if available:
                volume = self.data[currency].available + self.data[currency].frozen
                frozen = volume - available
                self.data[currency].available = available
                self.data[currency].frozen = frozen
                #self.data[currency].volume = volume
            if frozen:
                self.data[currency].frozen = frozen
            if volume:
                frozen = volume - self.data[currency].available
                self.data[currency].volume = volume
                self.data[currency].frozen = frozen

            #print(bd)
            #self.data[currency] = bd

    def update_balance(self, exchange: Exchange,
                       accound_id: str,
                       account_type: str,
                       currency: str, available: float, frozen: float):
        if exchange == self.exchange and accound_id == self.account_id and account_type == self.account_type:
            bd = BalanceData(exchange=exchange,
                             account_id=accound_id,
                             account_type=account_type,
                             currency=currency, frozen=frozen, available=available)
            self.data[currency] = bd

    def __str__(self):
        return ''


@dataclass
class BalanceData(BaseData):
    exchange: Exchange
    account_id: str
    account_type: str
    currency: str

    account_state: str = None
    volume: float = None
    available: float = None
    frozen: float = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.currency}.{self.exchange.value}"
        #if self.available and self.frozen:
        self.volume = self.available + self.frozen

    def __str__(self):
        return '%s %s V:%.3f A:%.3f F:%.3f' % (self.currency, self.exchange.value, self.volume, self.available, self.frozen)


@dataclass
class PositionData(BaseData):
    """
    Positon data is used for tracking each individual position holding.
    """

    symbol: str
    exchange: Exchange
    direction: Direction

    volume: float = 0
    frozen: float = 0
    price: float = 0
    pnl: float = 0
    yd_volume: float = 0

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_positionid = f"{self.vt_symbol}.{self.direction.value}"


@dataclass
class AccountData(BaseData):
    """
    Account data contains information about balance, frozen and available.
    """
    exchange: Exchange
    account_id: str
    account_type: str = None
    account_subtype: str = None
    account_state: str = None
    currency: str = None

    # old currency: don't delete
    accountid: str = None

    balance: float = None
    frozen: float = None
    available: float = None

    def __post_init__(self):
        """"""
        if self.balance and self.frozen:
            self.available = self.balance - self.frozen
        self.vt_accountid = f"{self.gateway_name}.{self.accountid}"

    def __str__(self):
        s1 = f'{self.exchange.value} {self.currency} {self.account_id} {self.account_type}'
        if self.available:
            s1 += f' A:{self.available}'
        if self.frozen:
            s1 += f' F:{self.frozen}'
        if self.balance:
            s1 += f' B:{self.balance}'
        return s1


@dataclass
class LogData(BaseData):
    """
    Log data is used for recording log messages on GUI or in log files.
    """

    msg: str
    level: int = INFO

    def __post_init__(self):
        """"""
        self.time = datetime.now()


@dataclass
class ContractData(BaseData):
    """
    Contract data contains basic information about each contract traded.
    """

    symbol: str
    exchange: Exchange
    name: str
    product: Product
    size: int
    pricetick: float

    min_volume: float = 1           # minimum trading volume of the contract
    stop_supported: bool = False    # whether server supports stop order
    net_position: bool = False      # whether gateway uses net position volume
    history_data: bool = False      # whether gateway provides bar history data

    option_strike: float = 0
    option_underlying: str = ""     # vt_symbol of underlying contract
    option_type: OptionType = None
    option_expiry: datetime = None
    option_portfolio: str = ""
    option_index: str = ""          # for identifying options with same strike price

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class SubscribeRequest:
    """
    Request sending to specific gateway for subscribing tick data update.
    """

    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderRequest:
    """
    Request sending to specific gateway for creating a new order.
    """

    symbol: str
    exchange: Exchange
    direction: Direction
    type: OrderType
    volume: float
    price: float = 0
    offset: Offset = Offset.NONE
    reference: str = ""
    account_id: str = ""

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def create_order_data(self, orderid: str, gateway_name: str) -> OrderData:
        """
        Create order data from request.
        """
        order = OrderData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=orderid,
            type=self.type,
            direction=self.direction,
            offset=self.offset,
            price=self.price,
            volume=self.volume,
            gateway_name=gateway_name,
        )
        return order


@dataclass
class CancelRequest:
    """
    Request sending to specific gateway for canceling an existing order.
    """

    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

@dataclass
class AccountTradeRequest:
    exchange: Exchange
    vt_symbol: str = None
    account_id: str = None
    symbol: str = None
    start_time: int = None
    end_time: int = None
    direct: str = None
    size: int = None

@dataclass
class BalanceRequest:
    exchange: Exchange
    account_id: str

    def __str__(self):
        return f'{self.exchange}-{self.account_id}'


@dataclass
class HistoryRequest:
    """
    Request sending to specific gateway for querying history data.
    """

    symbol: str
    exchange: Exchange
    start: datetime
    end: datetime = None
    interval: Interval = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

