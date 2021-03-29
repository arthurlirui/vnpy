from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.object import VlineData, BarData, PositionData, MarketEventData, AccountData, BalanceData
from vnpy.trader.engine import BaseEngine
from vnpy.app.algo_trading import AlgoTemplate
from vnpy.trader.utility import VlineGenerator, MarketEventGenerator, VlineQueueGenerator, BarQueueGenerator
from pprint import pprint
from vnpy.trader.object import HistoryRequest
from typing import Any, Callable
from pprint import pprint
import math
from scipy.signal import argrelextrema, argrelmin, argrelmax
import numpy as np

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


class GridVline(CtaTemplate):
    """"""
    display_name = "Grid Vline - 网格v线"
    author = "Arthur"
    default_setting = {
        "vt_symbol": "",
        "price": 0.0,
        "step_price": 0.0,
        "step_volume": 0,
        "interval": 10,
        "test": 1000,
    }

    #variables = ["pos", "timer_count", "vt_orderid"]
    variables = []

    usdt_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]
    bch3l_vol_list = [1000, 4000, 16000, 64000, 256000, 1024000, 4096000]
    market_params = {'btcusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0},
                     'bch3lusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 0.01}}
    market_params = {'bch3lusdt': {'vline_vol': 100, 'vline_vol_list': bch3l_vol_list, 'bin_size': 0.01}}

    parameters = ['vline_vol', 'vline_num', 'vline_vol_list']
    vline_vol = 0
    vline_num = 0
    vline_vol_list = []
    # variables = ['kk_up', 'kk_down']

    # parameters = {'vline_vol': 10,
    #               'vline_vol_list': [40, 160, 640, 2560, 10240, 40960],
    #               'vt_symbol_list': ['btcusdt.HUOBI', 'ethusdt.HUOBI'],
    #               'symbols': ['btcusdt', 'ethusdt'],
    #               'exchanges': ['HUOBI'],
    #               'vline_min_num': 10,
    #               'vline_max_num': 1000,
    #               'ttb_min_num': 10,
    #               'first_symbol': 'BTC',
    #               'second_symbol': 'USDT',
    #               'min_trade_vol': 0.01,
    #               'max_trade_vol': 0.1,
    #               'total_position': 10,
    #               'position_step': 0.1,
    #               'min_position': 0.1,
    #               'max_position': 2,
    #               'init_position': 0,
    #               'position_constant_decrease': 0.01}

    def __init__(
        self,
        cta_engine,
        strategy_name,
        vt_symbol,
        setting
    ):
        """"""
        super(GridVline, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.symbols = ['bch3lusdt']
        self.exchanges = ['HUOBI']

        # data buffer
        self.trade_buf = []
        self.kline_buf = []
        self.tick_buf = []

        # working account: spot account
        self.account_info = None
        self.balance_info = None

        self.on_init()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # init vline queue generator
        self.vqg = {}
        self.init_vline_queue_generator()

        # init vline generator
        self.vg = {}
        self.init_vline_generator()

        self.kqg = BarQueueGenerator()

        self.is_data_inited = False
        self.init_data()

        self.last_tick = None
        self.timer_count = 0

        # init internal parameters
        self.max_amount = 1000
        self.max_ratio = 1.0
        self.support_min = []
        self.support_max = []

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

    def init_data(self):
        # init local market data for vline
        self.load_market_trade(callback=self.on_init_market_trade)
        self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_init_vline_queue)
        #self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_init_vline)

        # init local market data for bar
        self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_kline)
        self.load_bar(days=2, interval=Interval.MINUTE_5, callback=self.on_kline)
        self.load_bar(days=2, interval=Interval.MINUTE_15, callback=self.on_kline)
        self.load_bar(days=2, interval=Interval.MINUTE_30, callback=self.on_kline)
        self.load_bar(days=7, interval=Interval.HOUR, callback=self.on_kline)
        self.load_bar(days=7, interval=Interval.HOUR_4, callback=self.on_kline)
        self.load_bar(days=60, interval=Interval.DAILY, callback=self.on_kline)

        # load account and balance
        self.load_account()
        self.is_data_inited = True

    def init_account(self):
        pass

    def init_balance(self):
        pass

    def init_account_trade(self):
        pass

    def check_vline_pos(self, price):
        vol_pos = {}
        #print(self.vt_symbol)
        for vol in self.vqg[self.vt_symbol].vol_list:
            vq = self.vqg[self.vt_symbol].get_vq(vol=vol)
            pc = vq.less_vol(price=price)
            vol_pos[vol] = pc
        return vol_pos

    def check_open_close_price(self):
        open_close_price = {}
        for vol in self.vqg[self.vt_symbol].vol_list:
            vq = self.vqg[self.vt_symbol].get_vq(vol=vol)
            if len(vq.trades) > 0:
                t0 = vq.trades[0]
                tl = vq.trades[-1]
                open_close_price[vol] = {'o': t0.__str__(), 'c': tl.__str__()}
        return open_close_price

    def load_tick(self, days: int, callback: Callable):
        """
        Load historical tick data for initializing strategy.
        """
        self.cta_engine.load_tick(self.vt_symbol, days, callback=callback)

    def load_market_trade(self, callback: Callable):
        self.cta_engine.load_market_trade(self.vt_symbol, callback=callback)

    def load_account(self, account_type='spot'):
        accounts = self.cta_engine.load_account_data(self.vt_symbol)
        account_info = None
        balance_info = None
        for acc in accounts:
            if acc.account_type == account_type:
                account_id = acc.account_id
                account_info = acc
                balance_info = self.cta_engine.load_balance_data(vt_symbol=self.vt_symbol, account_id=account_id)

        if account_info and balance_info:
            self.account_info = account_info
            self.balance_info = balance_info

        for d in self.balance_info.data:
            if self.balance_info.data[d].available > 0:
                print(self.balance_info.data[d])

    def on_init_tick(self, tick: TickData):
       pass

    def on_init_market_trade(self, trade: TradeData):
        for vt_symbol in self.vqg:
            if trade.vt_symbol == vt_symbol:
                self.vqg[vt_symbol].init_by_trade(trade=trade)
        for vt_symbol in self.vg:
            if trade.vt_symbol == vt_symbol:
                self.vg[vt_symbol].init_by_trade(trade=trade)

    def on_init_vline_queue(self, bar: BarData):
        # init load_bar data is from reversed order
        for vt_symbol in self.vqg:
            if bar.vt_symbol == vt_symbol:
                self.vqg[vt_symbol].init_by_kline(bar=bar)

    def on_init_vline(self, bar: BarData):
        for vt_symbol in self.vg:
            if bar.vt_symbol == vt_symbol:
                self.vg[vt_symbol].init_by_kline(bar=bar)

    def init_setting(self, setting: dict = {}):
        for key in setting:
            if key in self.default_setting:
                setattr(self, key, setting[key])

    def init_parameter(self, parameters: dict = {}):
        for key in parameters:
            if key in self.parameters:
                self.parameters[key] = parameters[key]

        for name in self.parameters:
            setattr(self, name, self.parameters[name])

    def init_vline_queue_generator(self):
        for s in self.symbols:
            for ex in self.exchanges:
                vt_sym = s + '.' + ex
                vline_vol_list = self.market_params[s]['vline_vol_list']
                bin_size = self.market_params[s]['bin_size']
                self.vqg[vt_sym] = VlineQueueGenerator(vol_list=vline_vol_list, vt_symbol=self.vt_symbol, bin_size=bin_size)

    def init_vline_generator(self):
        for s in self.symbols:
            for ex in self.exchanges:
                vt_sym = s+'.'+ex
                vline_vol = self.market_params[s]['vline_vol']
                vline_vol_list = self.market_params[s]['vline_vol_list']
                self.vg[vt_sym] = VlineGenerator(on_vline=self.on_vline, vol_list=[vline_vol])

    def on_tick(self, tick: TickData):
        self.tick_buf.append(tick)
        self.last_tick = tick

    def on_market_trade(self, trade: TradeData):
        self.trade_buf.append(trade)
        print(trade)
        for vol in self.vqg[self.vt_symbol].vq:
            pos = self.vqg[self.vt_symbol].vq[vol].less_vol(trade.price)
            total_vol = self.vqg[self.vt_symbol].vq[vol].vol
            print('%.4f %.4f' % (pos*100, total_vol))

    def on_vline(self, vline: VlineData, vol: int):
        print(vline)

    def on_kline(self, bar: BarData):
        self.kline_buf.append(bar)

    def on_trade(self, trade: TradeData):
        print('OnTrade:', trade)

    def on_order(self, order: OrderData):
        print('OnOrder:', order)

    def on_account(self, accdata: AccountData):
        #print('InputData:', accdata)
        if accdata.account_id != self.account_info.account_id:
            return
        currency = accdata.currency
        exchange = accdata.exchange
        account_id = accdata.account_id
        account_type = accdata.account_type
        if accdata.available:
            self.balance_info.update(exchange=exchange,
                                     account_id=account_id,
                                     account_type=account_type,
                                     currency=currency, available=accdata.available)
        if accdata.frozen:
            self.balance_info.update(exchange=exchange,
                                     account_id=account_id,
                                     account_type=account_type,
                                     currency=currency, frozen=accdata.frozen)

        if accdata.balance:
            self.balance_info.update(exchange=exchange,
                                     account_id=account_id,
                                     account_type=account_type,
                                     currency=currency, volume=accdata.balance)
        #print('OnAccount:', self.balance_info.data[currency])

    def on_balance(self, balance_data: BalanceData):
        print(balance_data)

    def make_decision(self):
        pass

    def on_timer(self):
        """"""
        if self.is_data_inited:
            for t in self.trade_buf:
                self.vqg[t.vt_symbol].update_market_trades(trade=t)

            for t in self.trade_buf:
                self.vg[t.vt_symbol].update_market_trades(trade=t)

            for bar in self.kline_buf:
                self.kqg.update_bar(bar=bar)

            self.trade_buf = []
            self.kline_buf = []
            self.tick_buf = []

            debug_print = False
            if debug_print:
                for vqi in self.vqg[self.vt_symbol].vq:
                    print(self.vqg[self.vt_symbol].vq[vqi])

                for vi in self.vg[self.vt_symbol].vlines:
                    vl = self.vg[self.vt_symbol].vlines[vi]
                    if len(vl) > 0:
                        print(len(vl), vl[0], vl[-1])

        if self.timer_count % 10 == 0:
            '''update reference buy and sell point'''
            for vol in self.vg[self.vt_symbol].vlines:
                vlines = self.vg[self.vt_symbol].vlines[vol]
                if len(vlines) == 0:
                    continue
                buy_price = np.array([v.low_price for v in vlines])
                sell_price = np.array([v.high_price for v in vlines])
                avg_price = np.array([v.avg_price for v in vlines])
                local_min_ind = argrelmin(avg_price)[0]
                local_max_ind = argrelmax(avg_price)[0]
                for i in local_min_ind:
                    print(f'min_{i}', vlines[i])
                for i in local_max_ind:
                    print(f'max_{i}', vlines[i])
                for i in range(len(vlines)):
                    print('%04d' % i, vlines[i])

        if self.timer_count % 30 == 0:
            '''
            update min max vline
            '''
            for vol in self.vg[self.vt_symbol].vlines:
                vlines = self.vg[self.vt_symbol].vlines[vol]
                if len(vlines) == 0:
                    continue
                low_price = np.array([v.low_price for v in vlines])
                high_price = np.array([v.high_price for v in vlines])
                avg_price = np.array([v.avg_price for v in vlines])
                local_min_ind = argrelmin(avg_price)[0]
                local_max_ind = argrelmax(avg_price)[0]
                for i in local_min_ind:
                    print(f'min_{i}', vlines[i])
                for i in local_max_ind:
                    print(f'max_{i}', vlines[i])
                for i in range(len(vlines)):
                    print('%04d' % i, vlines[i])

            print(self.timer_count)
        self.timer_count += 1

