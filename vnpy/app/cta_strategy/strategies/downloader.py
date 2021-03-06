from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData, OrderBookData
from vnpy.trader.object import VlineData, BarData, PositionData, MarketEventData
from vnpy.trader.engine import BaseEngine
from vnpy.app.algo_trading import AlgoTemplate
import math
from vnpy.trader.utility import VlineGenerator, MarketEventGenerator, VlineQueueGenerator
from pprint import pprint
from vnpy.trader.object import HistoryRequest
from typing import Any, Callable
from pprint import pprint
import pandas as pd
import os

from vnpy.trader.constant import (
    Direction,
    OrderType,
    Interval,
    Exchange,
    Offset,
    Status
)

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class Downloader(CtaTemplate):
    """"""
    display_name = "downloader - 自动下载器"
    author = "Arthur"
    default_setting = {
        "vt_symbol": "",
        "price": 0.0,
        "step_price": 0.0,
        "step_volume": 0,
        "interval": 10,
        "test": 1000,
    }
    variables = ['count1m', 'count5m', 'count15m', 'count30m', 'count1h', 'count4h',
                 'count1d', 'count1mon', 'count1w', 'count1y']

    #usdt_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]
    #market_params = {'btcusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0},
    #                 'ethusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0}}

    parameters = ['savepath']
    savepath = '/home/lir0b/data/TradingData'
    maxnum = 10000
    count1m = 0
    count5m = 0
    count15m = 0
    count30m = 0
    count1h = 0
    count4h = 0
    count1d = 0
    count1mon = 0
    count1w = 0
    count1y = 0
    #maxnum = 100000
    #vline_vol = 10
    #vline_num = 5
    #vline_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]

    def __init__(
        self,
        cta_engine,
        strategy_name,
        vt_symbol,
        setting
    ):
        """"""
        super(Downloader, self).__init__(cta_engine, strategy_name, vt_symbol, setting)
        # self.symbols = ['btcusdt', 'btc3lusdt', 'btc3susdt',
        #                 'bchusdt', 'bch3lusdt', 'bch3susdt',
        #                 'ethusdt', 'eth3lusdt', 'eth3susdt',
        #                 'ltcusdt', 'ltc3lusdt', 'ltc3susdt',
        #                 'linkusdt', 'link3lusdt', 'link3susdt', 'bsvusdt', 'bsc3lusdt', 'bsv3susdt']
        # self.exchanges = ['HUOBI']
        self.on_init()
        #self.init_parameter()
        #self.load_all_contracts()
        self.interval2count = {Interval.MINUTE: self.count1m,
                               Interval.MINUTE_5: self.count5m,
                               Interval.MINUTE_15: self.count15m,
                               Interval.MINUTE_30: self.count30m,
                               Interval.HOUR: self.count1h,
                               Interval.HOUR_4: self.count4h,
                               Interval.WEEKLY: self.count1w,
                               Interval.MONTHLY: self.count1mon,
                               Interval.YEARLY: self.count1y}

    def init_parameter(self, parameters: dict = {}):
        for key in parameters:
            if key in self.parameters:
                self.parameters[key] = parameters[key]

        for name in self.parameters:
            setattr(self, name, self.parameters[name])

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        # load trading pairs for exchange

        self.trades = {}
        self.klines = {}
        self.trades[self.vt_symbol] = []
        self.klines[self.vt_symbol] = []

        self.last_tick = None
        self.timer_count = 0
        self.pos = 0

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_order_book(self, order_book: OrderBookData):
        pass

    def init_data(self):
        self.load_market_trade(callback=self.on_init_market_trade)
        self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_init_vline_queue)

    def load_tick(self, days: int, callback: Callable):
        """
        Load historical tick data for initializing strategy.
        """
        self.cta_engine.load_tick(self.vt_symbol, days, callback=callback)

    def load_market_trade(self, callback: Callable):
        self.cta_engine.load_market_trade(self.vt_symbol, callback=callback)

    def load_all_contracts(self, callback: Callable = None):
        pass

    def on_tick(self, tick: TickData):
        self.last_tick = tick

    def on_market_trade(self, trade: TradeData):
        if trade.vt_symbol in self.trades:
            self.trades[trade.vt_symbol].append(trade)

        if len(self.trades[trade.vt_symbol]) >= self.maxnum:
            rawdata = {'tradeid': [], 'direction': [], 'price': [], 'volume': [], 'time': []}
            columns = ['tradeid', 'direction', 'price', 'volume', 'time']
            t0 = self.trades[trade.vt_symbol][0]
            te = self.trades[trade.vt_symbol][-1]
            id0 = t0.tradeid
            ide = te.tradeid
            symbol, exchange = t0.vt_symbol.split('.')
            filename = f'{exchange}-{symbol}-{id0}-{ide}-trade.xlsx'
            for t in self.trades[trade.vt_symbol]:
                rawdata['tradeid'].append(t.tradeid)
                if t.direction == Direction.SHORT:
                    rawdata['direction'].append('buy')
                elif t.direction == Direction.LONG:
                    rawdata['direction'].append('sell')
                rawdata['price'].append(t.price)
                rawdata['volume'].append(t.volume)
                rawdata['time'].append(t.datetime.timestamp())
            self.write_trade(filepath=os.path.join(self.savepath, exchange), filename=filename, data=rawdata, columns=columns)
            self.trades[trade.vt_symbol] = []

    def on_timer(self):
        """"""
        #if not self.last_tick:
        #    return
        if self.timer_count % 1 == 0:
            self.count1m = self.interval2count[Interval.MINUTE]
            self.count5m = self.interval2count[Interval.MINUTE_5]
            self.count15m = self.interval2count[Interval.MINUTE_15]
            self.count30m = self.interval2count[Interval.MINUTE_30]
            self.count1h = self.interval2count[Interval.HOUR]
            self.count4h = self.interval2count[Interval.HOUR_4]
            self.count1w = self.interval2count[Interval.WEEKLY]
            self.count1mon = self.interval2count[Interval.MONTHLY]
            self.count1y = self.interval2count[Interval.YEARLY]

        self.timer_count += 1
        self.pos += 1
        self.put_event()

    def on_kline(self, bar: BarData):
        if not bar.interval in self.klines:
            self.klines[bar.interval] = []
        if bar.interval in self.klines:
            self.klines[bar.interval].append(bar)
            self.interval2count[bar.interval] = len(self.klines[bar.interval])
            print('kline', bar, 'len:', len(self.klines[bar.interval]))

        # vt_symbol = bar.vt_symbol
        # if bar.interval == Interval.HOUR:
        #     print(bar)
        # if vt_symbol in self.klines:
        #     if bar.interval in self.klines[vt_symbol]:
        #         self.klines[vt_symbol][bar.interval].append(bar)
        #     else:
        #         self.klines[vt_symbol][bar.interval] = []
        #         self.klines[vt_symbol][bar.interval].append(bar)
        #
        #     if len(self.klines[vt_symbol][bar.interval]) > 10:
        #         for ii in self.klines[vt_symbol][bar.interval]:
        #             print(ii)
        #
        # else:
        #     pass

    def write_trade(self, filepath, filename, data, columns):
        df = pd.DataFrame(data=data, columns=columns)
        df.to_excel(os.path.join(filepath, filename))

