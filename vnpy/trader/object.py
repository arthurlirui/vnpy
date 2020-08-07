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
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    close_price: float = 0
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


@dataclass
class VlineData(BaseData):
    """
    Candlestick vline data of a certain trading volume.
    """

    symbol: str = 'BTCUSDT'
    exchange: Exchange = Exchange.HUOBI
    open_time: datetime = datetime.today()
    close_time: datetime = datetime.today()

    volume: float = 0.0
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    close_price: float = 0
    gateway_name: str = 'HUOBI'

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def __add__(self, other):
        symbol = self.symbol
        exchange = self.exchange
        open_time = self.open_time
        close_time = other.close_time

        volume = self.volume + other.volume
        open_price = self.open_price
        close_price = other.close_price
        high_price = max(self.high_price, other.high_price)
        low_price = min(self.low_price, other.low_price)
        t = VlineData(symbol=symbol, exchange=exchange, open_time=open_time, close_time=close_time,
                      gateway_name=self.gateway_name,
                      volume=volume, open_price=open_price, close_price=close_price,
                      high_price=high_price, low_price=low_price)
        return t

    def init_by_tick(self, tick: TickData):
        self.symbol = tick.symbol
        self.exchange = tick.exchange
        self.open_time = tick.datetime
        self.close_time = tick.datetime

        self.volume = tick.volume
        self.open_price = tick.last_price
        self.close_price = tick.last_price
        self.high_price = tick.last_price
        self.low_price = tick.last_price
        self.gateway_name = tick.gateway_name

    def add_tick(self, tick: TickData):
        if self.symbol == tick.symbol and self.exchange == tick.exchange:
            if self.open_time < tick.datetime and self.close_time < tick.datetime:
                self.close_time = tick.datetime
                self.volume = self.volume + tick.last_volume
                self.close_price = tick.last_price
                self.high_price = max(self.high_price, tick.last_price)
                self.low_price = min(self.low_price, tick.last_price)
                #print(self.open_time, self.volume)

    def __str__(self):
        return '%s O:%.3f C:%.3f H:%.3f L:%.3f V:%.3f OT:%s CT:%s' % (self.symbol, self.open_price, self.close_price,
                                                                       self.high_price, self.low_price, self.volume,
                                                                       self.open_time, self.close_time)


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
