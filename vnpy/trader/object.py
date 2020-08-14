"""
Basic data structure used for general trading function in VN Trader.
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO
import pandas as pd

from .constant import Direction, Exchange, Interval, Offset, Status, Product, OptionType, OrderType
import numpy as np

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
        return '%s P:%.3f V:%.3f %s %s' % (self.symbol, self.last_price, self.last_volume, self.exchange, self.datetime)


@dataclass
class DistData(BaseData):
    """
    Price distribution of single vline
    """
    symbol: str = 'BTCUSDT'
    exchange: Exchange = Exchange.HUOBI
    gateway_name: str = None

    open_time: datetime = None
    close_time: datetime = None
    dist = {}

    def calc_dist(self, ticks: list):
        t0 = ticks[0]
        tend = ticks[-1]
        self.symbol = t0.symbol
        self.exchange = t0.exchange
        self.gateway_name = t0.gateway_name
        self.open_time = t0.datetime
        self.close_time = tend.datetime
        dist = {}
        for t in ticks:
            key = int(t.last_price)
            vol = t.last_volume
            if key in dist:
                dist[key] += vol
            else:
                dist[key] = vol
        self.dist = dist

    def calc_teeterboard(self, ticks, avg_price):
        func = lambda t, v: ((t.last_price-v)/v)*t.last_volume
        weight = sum([func(t, avg_price) for t in ticks])
        return weight

    def __str__(self):
        ss = [str(k) + ' ' + '%.3f' % v + ' ' for k, v in sorted(self.dist.items(), key=lambda x: x[0])]
        return ''.join(ss)

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


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
        return '%s O:%.3f C:%.3f H:%.3f L:%.3f V:%.3f OT:%s CT:%s' % (self.symbol, self.open_price, self.close_price,
                                                                      self.high_price, self.low_price, self.volume,
                                                                      self.datetime,
                                                                      self.datetime+pd.to_timedelta(self.interval.value))

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
    open_price: float = None
    high_price: float = None
    low_price: float = None
    close_price: float = None
    avg_price: float = 0

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def __add__(self, other):
        #print(self.__str__())
        #print(other)
        symbol = self.symbol
        exchange = self.exchange
        open_time = self.open_time
        close_time = other.close_time

        volume = self.volume + other.volume
        open_price = self.open_price
        close_price = other.close_price
        #print(self.high_price, self.low_price, self.open_price, self.close_price)
        high_price = max(self.high_price, other.high_price)
        low_price = min(self.low_price, other.low_price)
        vd = VlineData(symbol=symbol, exchange=exchange, open_time=open_time, close_time=close_time,
                       gateway_name=self.gateway_name, volume=volume,
                       open_price=open_price, close_price=close_price, high_price=high_price, low_price=low_price)
        return vd

    def init_by_tick(self, tick: TickData):
        self.symbol = tick.symbol
        self.exchange = tick.exchange
        self.open_time = tick.datetime
        self.close_time = tick.datetime

        self.volume = tick.last_volume
        self.avg_price = tick.last_price
        self.open_price = tick.last_price
        self.close_price = tick.last_price
        self.high_price = tick.last_price
        self.low_price = tick.last_price
        self.gateway_name = tick.gateway_name

    def add_tick(self, tick: TickData):
        if self.symbol == tick.symbol and self.exchange == tick.exchange:
            if self.open_time <= tick.datetime and self.close_time <= tick.datetime:
                self.close_time = tick.datetime

                sum_vol_price = self.avg_price * self.volume
                sum_vol_price = sum_vol_price + tick.last_price * tick.last_volume

                self.volume = self.volume + tick.last_volume

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

    def __str__(self):
        return '%s P:%.3f O:%.3f C:%.3f H:%.3f L:%.3f V:%.3f OT:%s CT:%s' % (self.symbol, self.avg_price,
                                                                             self.open_price, self.close_price,
                                                                             self.high_price, self.low_price,
                                                                             self.volume,
                                                                             self.open_time, self.close_time)

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


@dataclass
class OrderData(BaseData):
    """
    Order data contains information for tracking lastest status
    of a specific order.
    """

    symbol: str
    exchange: Exchange
    orderid: str

    type: OrderType = OrderType.LIMIT
    direction: Direction = None
    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    traded: float = 0
    status: Status = Status.SUBMITTING
    datetime: datetime = None

    def __post_init__(self):
        """"""
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


@dataclass
class TradeData(BaseData):
    """
    Trade data contains information of a fill of an order. One order
    can have several trade fills.
    """

    symbol: str
    exchange: Exchange
    orderid: str
    tradeid: str
    direction: Direction = None

    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    datetime: datetime = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"
        self.vt_tradeid = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class BalanceData(BaseData):
    symbol: str
    exchange: Exchange
    volume: float = 0
    available: float = 0
    frozen: float = 0
    price: float = 0

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.available = self.volume
        self.frozen = self.volume - self.available
        #self.vt_balanceid = f"{self.vt_symbol}.{self.direction.value}"

    def __str__(self):
        return '%s %s V:%.3f A:%.3f F:%.3f P:%.3f' % (self.symbol, self.exchange.value, self.volume, self.available, self.frozen, self.price)


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
    Account data contains information about balance, frozen and
    available.
    """

    accountid: str

    balance: float = 0
    frozen: float = 0

    def __post_init__(self):
        """"""
        self.available = self.balance - self.frozen
        self.vt_accountid = f"{self.gateway_name}.{self.accountid}"


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
