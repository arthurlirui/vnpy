from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.object import VlineData, BarData, PositionData, MarketEventData, AccountData, BalanceData, OrderBookData
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
import random
import datetime
import matplotlib.pyplot as plt
#from scipy.misc import electrocardiogram
from scipy.signal import find_peaks

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

import pytz
SAUDI_TZ = pytz.timezone("Asia/Qatar")
MY_TZ = SAUDI_TZ


class GridVline(CtaTemplate):
    """"""
    display_name = "Grid Vline - 网格v线"
    author = "Arthur"
    #default_setting = {"vt_symbol": "", "price": 0.0, "step_price": 0.0, "step_volume": 0, "interval": 10, "test": 1000}
    default_setting = {'base_currency': 'bch3l', 'quote_currency': 'usdt', 'exchange': 'HUOBI',
                       'vline_vol': 100, 'total_invest': 500,
                       'trade_amount': 40, 'global_prob': 0.5, 'max_break_count': 4}
    base_currency = 'bch3l'
    quote_currency = 'usdt'
    exchange = 'HUOBI'
    vline_vol = 100
    total_invest = 500
    trade_amount = 40
    global_prob = 0.5
    max_break_count = 4
    parameters = ['base_currency', 'quote_currency', 'exchange', 'vline_vol',
                  'total_invest', 'trade_amount', 'global_prob', 'max_break_count']

    variables = ['timer_count', 'upper_break', 'lower_break', 'upper_break_count', 'lower_break_count',
                 'buy_prob', 'sell_prob', 'min_invest', 'max_invest', 'total_invest',
                 'buy_price', 'sell_price', 'vol_select',
                 'prev_buy_price', 'prev_sell_price', 'trade_speed', 'trade_gain',
                 'is_kill_down', 'prev_high_price', 'is_chase_up', 'prev_low_price', 'trading_quota']

    #usdt_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]
    bch3l_vol_list = [1000, 10000, 100000, 1000000]
    #market_params = {'btcusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0},
    #                 'bch3lusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 0.01}}
    market_params = {'bch3lusdt': {'vline_vol': 100, 'vline_vol_list': bch3l_vol_list, 'bin_size': 0.01}}

    def __init__(
        self,
        cta_engine,
        strategy_name,
        vt_symbol,
        setting=default_setting
    ):
        """"""
        super(GridVline, self).__init__(cta_engine, strategy_name, vt_symbol, setting=setting)
        # exchange and trading pair
        self.symbol, self.exchange = vt_symbol.split('.')
        self.exchanges = []
        self.exchanges.append(self.exchange)
        self.symbol = self.base_currency+self.quote_currency
        self.symbols = []
        self.symbols.append(self.symbol)

        # data buffer
        self.trade_buf = []
        self.kline_buf = []
        self.tick_buf = []

        # account trade buffer
        self.account_trades = []
        self.orders = {}

        # working account: spot account
        self.account_info = None
        self.balance_info = None

        # order book buffer
        self.order_book = None
        self.on_init()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # init buffer for saving trades and klines
        self.his_trade_buf = {}
        self.his_kline_buf = {}

        # init vline queue generator
        self.vqg = {}
        self.init_vline_queue_generator()

        # init vline generator
        self.vg = {}
        self.init_vline_generator()
        self.kqg = BarQueueGenerator()
        self.is_data_inited = False
        #self.trading = False
        self.init_data()

        self.last_tick = None
        self.last_trade = None

        # init internal parameters
        self.timer_count = 0
        self.theta = 0.01
        #self.global_prob = 0.3
        self.buy_prob = 0
        self.sell_prob = 0
        #self.trade_amount = 20

        # self.max_amount = 1000
        # self.max_ratio = 1.0
        # self.support_min = []
        # self.support_max = []
        # self.max_num_vline = 100000
        # self.max_local_num_extrema = 100
        # self.vline_loca_order = 200
        # self.theta = 0.01
        # self.global_prob = 0.3
        # self.buy_prob = 0
        # self.sell_prob = 0
        # #self.sell(price=11, volume=0.5)
        # self.trade_amount = 20

        # init invest position (usdt unit)
        #self.total_invest = 400.0
        self.max_invest = 100.0
        self.min_invest = 0
        #self.cur_invest = {}

        # init price break count
        self.max_break_count = 4
        self.upper_break_count = self.max_break_count
        self.lower_break_count = self.max_break_count
        self.upper_break = True
        self.lower_break = True

        # previous buy or sell price
        self.prev_buy_price = None
        self.prev_sell_price = None

        # previous high and low peaks
        self.prev_high_price = None
        self.prev_low_price = None
        self.is_chase_up = False
        self.is_kill_down = False

        # trading quota
        self.trading_quota = True

        # market signal
        # bull market
        self.is_gain = False
        self.is_climb = False
        self.is_surge = False

        # hover market
        self.is_hover = False

        # bear market
        self.slip = False
        self.retreat = False
        self.slump = False

        #self.pre_trade = []
        #self.live_timedelta = datetime.timedelta(hours=12)

        # self.buy_price0 = None
        # self.sell_price0 = None
        # self.buy_price1 = None
        # self.sell_price1 = None
        # self.buy_price2 = None
        # self.sell_price2 = None
        # self.buy_price3 = None
        # self.sell_price3 = None
        # self.buy_price4 = None
        # self.sell_price4 = None

        #self.buy_price = [self.buy_price0, self.buy_price1, self.buy_price2, self.buy_price3, self.buy_price4]
        #self.sell_price = [self.sell_price0, self.sell_price1, self.sell_price2, self.sell_price3, self.sell_price4]
        self.buy_price = None
        self.sell_price = None
        self.vol_select = self.market_params[self.symbol]['vline_vol_list'][0]

        # trading speed
        self.trade_speed = -1
        self.trade_gain = -1

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

    def init_buf(self):
        for s in self.symbols:
            for ex in self.exchanges:
                vt_sym = s + '.' + ex
                self.his_trade_buf[vt_sym] = []
                self.his_kline_buf[vt_sym] = []

    def init_data(self):
        # init local market data for vline
        # first init vline queue generator, vline generator by kline
        # then update vline queue generator, vline generator by history trade
        self.init_buf()
        self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_save_his_kline)
        self.load_market_trade(callback=self.on_save_his_trades)
        self.on_init_kline_trade()
        self.load_account_trade(callback=self.on_trade)

        #self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_init_vline_queue)
        #self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_init_vline)
        #self.load_market_trade(callback=self.on_init_market_trade)

        # init local market data for bar
        if True:
            self.load_bar(days=2, interval=Interval.MINUTE, callback=self.on_kline)
            self.load_bar(days=2, interval=Interval.MINUTE_5, callback=self.on_kline)
            self.load_bar(days=2, interval=Interval.MINUTE_15, callback=self.on_kline)
        if False:
            self.load_bar(days=2, interval=Interval.MINUTE_30, callback=self.on_kline)
            self.load_bar(days=7, interval=Interval.HOUR, callback=self.on_kline)
            self.load_bar(days=7, interval=Interval.HOUR_4, callback=self.on_kline)
            self.load_bar(days=60, interval=Interval.DAILY, callback=self.on_kline)

        # load account and balance
        self.load_account()
        self.is_data_inited = True
        #self.trading = True

        if True:
            for vt_symbol in self.vg:
                vlines = self.vg[vt_symbol].vlines
                for vol in vlines:
                    print(f'{vt_symbol}-{vol}:', len(vlines[vol]))

    def on_save_his_trades(self, trade: TradeData):
        self.his_trade_buf[trade.vt_symbol].append(trade)

    def on_save_his_kline(self, bar: BarData):
        self.his_kline_buf[bar.vt_symbol].append(bar)

    def on_init_kline_trade(self):
        for vt_symbol in self.vg:
            his_trades = self.his_trade_buf[vt_symbol]
            his_kline = self.his_kline_buf[vt_symbol]
            for i, bar in enumerate(his_kline):
                if bar.datetime < his_trades[0].datetime:
                    self.vg[vt_symbol].init_by_kline(bar=bar)
                    self.vqg[vt_symbol].init_by_kline(bar=bar)
            for trade in his_trades:
                #print(trade)
                self.vg[vt_symbol].init_by_trade(trade=trade)
                self.vqg[vt_symbol].init_by_trade(trade=trade)

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

    def load_account_trade(self, callback: Callable):
        self.cta_engine.load_account_trade(vt_symbol=self.vt_symbol, callback=callback)

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
            if self.balance_info.data[d].volume > 0:
                print('load account:', self.balance_info.data[d])

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
        #print('Tick:', self.last_tick)

    def on_order_book(self, order_book: OrderBookData):
        #print(order_book)
        if self.order_book:
            if order_book.pre_seq_num == self.order_book.seq_num:
                pre_seq_num = self.order_book.seq_num
                seq_num = order_book.seq_num
                time = order_book.time
                bids = order_book.bids
                asks = order_book.asks
                self.order_book.update(seq_num=seq_num, pre_seq_num=pre_seq_num, time=time, bids=bids, asks=asks)
            elif order_book.pre_seq_num == 0:
                pre_seq_num = self.order_book.seq_num
                seq_num = order_book.seq_num
                time = order_book.time
                bids = order_book.bids
                asks = order_book.asks
                self.order_book.refresh(seq_num=seq_num, time=time, bids=bids, asks=asks)
        else:
            if order_book.pre_seq_num == 0:
                self.order_book = order_book

        if self.order_book and False:
            print(list(self.order_book.bids.items())[0:10])
            print(list(self.order_book.asks.items())[0:10])

    def on_market_trade(self, trade: TradeData):
        self.trade_buf.append(trade)
        self.last_trade = trade
        price = self.last_trade.price
        #print('on_market_trade:', self.last_trade)
        self.check_price_break(price=price, direction=Direction.LONG)
        self.check_price_break(price=price, direction=Direction.SHORT)
        self.make_decision(price=trade.price)
        self.put_event()

    def calc_pro_buy(self, price: float, price_ref: float, theta: float, global_prob: float, min_p: float=0.01):
        buy_ref_price = (price_ref - price) / (price * theta)
        p_buy = global_prob * (0.5 * (np.tanh(buy_ref_price)) + 0.5)
        if p_buy < min_p:
            p_buy = 0
        p_buy = float(np.round(p_buy, 2))
        return p_buy

    def calc_pro_sell(self, price: float, price_ref: float, theta: float, global_prob: float, min_p: float=0.01):
        sell_ref_price = (price - price_ref) / (price * theta)
        p_sell = global_prob * (0.5 * (np.tanh(sell_ref_price)) + 0.5)
        if p_sell < min_p:
            p_sell = 0
        p_sell = float(np.round(p_sell, 2))
        return p_sell

    def on_vline(self, vline: VlineData, vol: int):
        if not self.is_data_inited:
            return
        # update price break signal
        #vol = self.market_params[self.symbol]['vline_vol']
        #vlines = self.vg[self.vt_symbol].vlines[vol]
        print(vol, vline)
        #self.vg[self.vt_symbol].update_vline(vline=vline, vol=vol)

    def on_kline(self, bar: BarData):
        self.kline_buf.append(bar)

    def on_trade(self, trade: TradeData):
        if len(self.account_trades) > 0:
            if trade.datetime > self.account_trades[-1].datetime:
                self.account_trades.append(trade)
            else:
                for i, td in enumerate(self.account_trades):
                    if trade.datetime < td.datetime:
                        self.account_trades.insert(i, trade)
                        break
        else:
            self.account_trades.append(trade)

        # slow buy, quick sell
        for trade in reversed(self.account_trades):
            if trade.direction == Direction.LONG:
                if trade.datetime > datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(seconds=30):
                    self.trading_quota = False
                    break
            elif trade.direction == Direction.SHORT:
                if trade.datetime > datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(seconds=30):
                    self.trading_quota = False
                    break

    def on_order(self, order: OrderData):
        if order.status == Status.NOTTRADED or order.status == Status.SUBMITTING:
            print('OnOrder:', order)
            self.orders[order.vt_orderid] = order

    def on_account(self, accdata: AccountData):
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
        print('OnAccount:', self.balance_info.data[currency])

    def on_balance(self, balance_data: BalanceData):
        print('OnBalance:', balance_data)

    def generate_volume(self, price: float, direction: Direction,
                        check_balance=True,
                        check_position=True,
                        check_probability=True,
                        check_price_break=True,
                        check_price=True,
                        check_break_risk=True,
                        check_quota=True) -> float:
        volume = 0.0
        if direction == Direction.LONG:
            # 1. check balance
            volume = random.uniform(0, 1) * self.trade_amount / price
            if check_balance:
                avail_volume = self.balance_info.data[self.quote_currency].available
                volume = np.round(np.min([volume, avail_volume / price]), 4)
                print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                cur_position = self.balance_info.data[self.base_currency].available*price
                if cur_position > self.max_invest:
                    volume = np.round(volume * 0.0, 4)
                    print(f'check_position {direction.value} {volume}')
        elif direction == Direction.SHORT:
            # 1. check balance
            if check_balance:
                volume = np.round(random.uniform(0, 1) * self.trade_amount / price, 2)
                avail_volume = self.balance_info.data[self.base_currency].available
                volume = np.round(np.min([volume, avail_volume]), 4)
                print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                cur_position = self.balance_info.data[self.base_currency].available*price
                if cur_position < self.min_invest:
                    volume = np.round(volume * 1.0, 4)
                print(f'check_position {direction.value} {volume}')
            # 3. check probability
            if check_probability:
                if self.buy_prob > self.sell_prob or self.buy_prob > 0.03:
                    volume = np.round(volume*0.0, 4)
                print(f'check_probability {direction.value} {volume}')
            # 4. check profit
            if check_price:
                ratio = 1.0
                if self.prev_buy_price and False:
                    if price < 1.02 * self.prev_buy_price:
                        ratio = 0.0
                    elif 1.02 * self.prev_buy_price < price < 1.05 * self.prev_buy_price:
                        ratio = 1.0
                    else:
                        ratio = 2.0
                else:
                    if price < self.sell_price:
                        ratio = 0.25
                    elif price > self.sell_price:
                        ratio = 1.0
                    else:
                        ratio = 0.0
                volume = np.round(volume * ratio, 4)
                print(f'check_price {direction.value} {volume}')
            # 5. upper price breaking
            if check_price_break:
                if self.upper_break:
                    volume = np.round(volume * 0.0, 4)
                print(f'check_price_break {direction.value} {volume}')
            # 5.1 price break risk
            if check_break_risk:
                if price > 1.05 * self.sell_price:
                    ratio = 0.25
                    volume = np.round(volume * ratio, 4)
                print(f'check_break_risk {direction.value} {volume}')
            # 6. has trading quota
            if check_quota:
                if not self.trading_quota:
                    volume = np.round(volume*0.0, 4)
                print(f'check_quota {direction.value} {volume}')
        else:
            volume = 0.0
        return volume

    def check_price_break(self, price: float, direction: Direction):
        if not self.is_data_inited:
            return
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        if len(kline_1m) < 20:
            return

        min_price = np.min([kl.low_price for kl in kline_1m[-20:-1]])
        max_price = np.max([kl.high_price for kl in kline_1m[-20:-1]])
        self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)

        if direction == Direction.LONG:
            #min_price = np.min([v.low_price for v in vlines[-30:]])
            if price <= min_price:
                if 0.5 < self.pos < 1.0:
                    self.lower_break_count = int(1.5 * self.max_break_count)
                elif 0.1 <= self.pos < 0.5:
                    self.lower_break_count = int(1.0 * self.max_break_count)
                elif 0.0 <= self.pos < 0.1:
                    self.lower_break_count = int(0.5 * self.max_break_count)
                else:
                    self.lower_break_count = int(1.0 * self.max_break_count)
                self.lower_break = True
        elif direction == Direction.SHORT:
            #max_price = np.max([v.high_price for v in vlines[-30:]])
            if price >= max_price:
                if 0.0 < self.pos < 0.3:
                    self.upper_break_count = int(2.0 * self.max_break_count)
                elif 0.3 <= self.pos < 0.9:
                    self.upper_break_count = int(1.0 * self.max_break_count)
                elif 0.9 <= self.pos < 1.0:
                    self.upper_break_count = int(1.0 * self.max_break_count)
                else:
                    self.upper_break_count = int(1.0 * self.max_break_count)
                #self.upper_break_count = self.max_break_count
                self.upper_break = True
        else:
            pass

    def generate_order(self, price: float, volume: float, direction: Direction, w1: float = 1.0, w2: float = 1.0, w3: float = 1.0):
        volume1 = float(np.round(volume * w1, 2))
        if direction == Direction.LONG:
            if random.uniform(0, 1) < 0.5 or True:
                price = np.round(price * (1 - random.uniform(-1, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.bids.keys())[0]+0.0001, 4)
            if volume1*price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        elif direction == Direction.SHORT:
            if random.uniform(0, 1) < 0.5 or True:
                price = np.round(price * (1 + random.uniform(-1, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.asks.keys())[0]-0.0001, 4)
            if volume1 * price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        else:
            return

    def swing_trading_long(self, price: float):
        exec_order = False
        ratio_prob = 1.0
        ratio_break = 1.0
        ratio_slow_suck = 1.0
        ratio_fall_down = 1.0
        ratio_high_price = 1.0
        ratio_quota = 1.0
        # 1. check probability
        if self.sell_prob > self.buy_prob or self.sell_prob > 0.03:
            ratio_prob = 0.0
        # 2. lower price break
        if self.lower_break:
            ratio_break = 0.0
        # 3. check prev_buy_price
        if self.prev_buy_price:
            if price < 0.995 * self.prev_buy_price:
                ratio_slow_suck = 0.5
            elif 0.98 * self.prev_buy_price < price < 0.995 * self.prev_buy_price:
                ratio_slow_suck = 0.75
            elif 0.95 * self.prev_buy_price < price < 0.98 * self.prev_buy_price:
                ratio_slow_suck = 1.0
            else:
                # stop loss here
                ratio_slow_suck = 0.0
        # 4. check prev_sell_price: avoid buy after selling
        prev_sell_price, prev_sell_pos = self.calc_avg_trade_price(direction=Direction.SHORT,
                                                                   timedelta=datetime.timedelta(minutes=30))
        if prev_sell_pos > 0 and price > 0.95 * prev_sell_price:
            ratio_fall_down = 0.0
        # 5. check prev_high_price: avoid buy after a high price
        if self.prev_high_price and price > 0.95 * self.prev_high_price:
            ratio_high_price = 0.0
        # 6. has trading quota
        if not self.trading_quota:
            ratio_quota = 0.0
        ratio = ratio_prob*ratio_break*ratio_fall_down*ratio_slow_suck*ratio_high_price*ratio_quota
        if ratio > 0:
            exec_order = True
        return exec_order, ratio

    def swing_trading_short(self, price: float):
        exec_order = False
        ratio_prob = 1.0
        ratio_break = 1.0
        ratio_slow_suck = 1.0
        ratio_fall_down = 1.0
        ratio_high_price = 1.0
        ratio_quota = 1.0
        # 1. check probability
        if self.buy_prob > self.sell_prob or self.buy_prob > 0.03:
            ratio_prob = 0.0
        # 2. upper price break
        if self.upper_break:
            ratio_break = 0.0
        # 3. check prev_sell_price
        prev_sell_price, prev_sell_pos = self.calc_avg_trade_price(direction=Direction.SHORT, vol=10,
                                                                   timedelta=datetime.timedelta(minutes=30))
        ratio_fast_sell = 1.0
        if prev_sell_pos > 0:
            if price >= 1.01 * prev_sell_price:
                ratio_fast_sell = 1.0
            elif 1.00 * prev_sell_price < price < 1.01 * prev_sell_price:
                ratio_fast_sell = 0.5
            else:
                # stop loss here
                ratio_fast_sell = 0.0
        # 4. price roars to highest and fall back
        bars = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)

        # 5. take profit

        # 6. has trading quota
        if not self.trading_quota:
            ratio_quota = 0.0
        ratio = ratio_prob * ratio_break * ratio_fast_sell * ratio_quota
        if ratio > 0:
            exec_order = True
        return exec_order, ratio

    def make_decision_swing_trading(self, price: float, direction: Direction):
        exec_order = False
        ratio = 1.0
        if direction == Direction.LONG:
            exec_order, ratio = self.swing_trading_long(price=price)
        elif direction == Direction.SHORT:
            exec_order, ratio = self.swing_trading_short(price=price)
        else:
            pass
        #print(f'check_probability {direction.value} {volume}')
        return exec_order, ratio

    def swing_trading(self, price: float):
        # 1. swing trading
        if random.uniform(0, 1) < self.buy_prob:
            direction = Direction.LONG
            # 0. make decision
            exec_buy, ratio = self.make_decision_swing_trading(price=price, direction=direction)
            if not exec_buy:
                return
            # 1. calc volume
            volume = self.generate_volume(price=price, direction=direction,
                                          check_balance=True, check_position=True, check_probability=True,
                                          check_price_break=True, check_price=True, check_break_risk=True,
                                          check_quota=True)
            print(f'{direction.value} {price} {volume}')
            # 2. generate order
            self.generate_order(price=price, volume=volume, direction=direction)
        if random.uniform(0, 1) < self.sell_prob:
            direction = Direction.SHORT
            # 0. exec sell
            exec_sell = self.make_decision_swing_trading(price=price, direction=direction)
            if not exec_sell:
                return

                # 1. calc volume
            volume = self.generate_volume(price=price, direction=direction,
                                          check_balance=True, check_position=True, check_probability=True,
                                          check_price_break=True, check_price=True, check_break_risk=True,
                                          check_quota=True)
            print(f'{direction.value} {price} {volume}')
            # 2. generate order
            self.generate_order(price=price, volume=volume, direction=direction)

    def need_stop_loss(self, stop_loss_rate: float = 0.95, stop_loss_count: int = 3):
        # check 1m kline to determine
        bars = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        is_stop_loss = False
        if not self.prev_buy_price:
            return is_stop_loss
        stop_price = stop_loss_rate*self.prev_buy_price
        bars_tmp = bars[-1*stop_loss_count:]
        count = sum([int(b.high_price < stop_price) for b in bars_tmp])
        if count >= stop_loss_count:
            is_stop_loss = True
        return is_stop_loss

    def stop_loss(self, price, stop_loss_rate: float = 0.95):
        if self.prev_buy_price and price < stop_loss_rate * self.prev_buy_price:
            # check 1m kline to determine
            is_stop_loss = self.need_stop_loss(stop_loss_rate=stop_loss_rate)
            if is_stop_loss:
                self.write_log(f'stop_loss {datetime.datetime.now(tz=MY_TZ)}')
                direction = Direction.SHORT
                # if stop loss, do care position, prob, quota, price, break, risk
                volume = self.generate_volume(price=price, direction=direction,
                                              check_position=False,
                                              check_probability=False,
                                              check_price=False,
                                              check_price_break=False,
                                              check_quota=True,
                                              check_break_risk=False)
                self.generate_order(price=price, volume=volume, direction=direction)
                self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def take_profit(self, price: float, take_profit_ratio: float = 0.3):
        if self.prev_buy_price and price > (1+take_profit_ratio)*self.prev_buy_price:
            self.write_log(f'take_profit {datetime.datetime.now(tz=MY_TZ)}')
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction,
                                          check_position=False,
                                          check_probability=False,
                                          check_price=False,
                                          check_price_break=False,
                                          check_quota=False,
                                          check_break_risk=False)
            self.generate_order(price=price, volume=volume, direction=direction)
            self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def chase_up(self, price: float, price_buy_ratio: float = 1.02):
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        bars1m_data = bars1m[-360:]
        low_price = np.array([bar.low_price for bar in bars1m_data])

        # 1. reverse price array to find low minimal
        if len(low_price) == 0:
            return
        peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
        if len(peaks_low) > 0:
            bar_low = bars1m_data[peaks_low[-1]]
            self.prev_low_price = bar_low.low_price
        else:
            self.prev_low_price = None
            return
        self.is_chase_up = False

        # 1. check market crash
        if price < price_buy_ratio*bar_low.low_price:
            self.is_chase_up = True

        # 2. check timestamp: 30min for buy low
        if bar_low.datetime < datetime.datetime.now(tz=MY_TZ)-datetime.timedelta(minutes=30):
            self.is_chase_up = False

        # 3. check position
        if self.is_chase_up:
            '''start chasing up'''
            # 1. price is in low position: check bars
            cur_position = self.balance_info.data[self.base_currency].available*price
            if cur_position < 0.2 * self.max_invest:
                self.write_log(f'Chasing up {datetime.datetime.now(tz=MY_TZ)}')
                direction = Direction.LONG
                volume = self.generate_volume(price=price, direction=direction,
                                              check_position=True,
                                              check_probability=False,
                                              check_price=False,
                                              check_price_break=True,
                                              check_quota=True,
                                              check_break_risk=False)
                self.generate_order(price=price, volume=volume, direction=direction)
                self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def kill_down(self, price: float, price_sell_ratio: float = 0.95):
        # bars15m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE_15)
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        bars1m_data = bars1m[-360:]
        high_price = np.array([bar.high_price for bar in bars1m_data])
        #low_price = np.array([bar.low_price for bar in bars1m_data])

        if len(high_price) == 0:
            #print('No high_price found!')
            return
        peaks_high, _ = find_peaks(high_price, distance=10, prominence=0.3, width=5)
        # reverse price array to find low minimal
        #peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=1, width=5)
        if len(peaks_high) > 0:
            bar_high = bars1m_data[peaks_high[-1]]
            self.prev_high_price = bar_high.high_price
            #print(bar_high)
        else:
            self.prev_high_price = None
            #print('No peaks_high found!')
            return

        self.is_kill_down = False
        # 1. check market crash
        if price > price_sell_ratio * bar_high.close_price:
            self.is_kill_down = True

        # 2. check timestamp: 30min for buy low
        if bar_high.datetime < datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(minutes=30):
            self.is_kill_down = False

        # 3. check position
        if self.is_kill_down:
            '''start killing down'''
            self.write_log(f'Killing down {datetime.datetime.now(tz=MY_TZ)}')
            # 1. price is in low position: check bars
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction,
                                          check_position=True,
                                          check_probability=False,
                                          check_price=False,
                                          check_price_break=True,
                                          check_quota=True,
                                          check_break_risk=False)
            self.generate_order(price=price, volume=volume, direction=direction)
            self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def chase_rebound_buy(self, price: float, price_buy_ratio: float = 1.03):
        pass

    def chase_rebound_sell(self, price: float, price_sell_ratio: float = 1.05):
        pass

    def chase_rebound(self, price: float, price_buy_ratio: float = 1.03, price_sell_ratio: float = 1.05):
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        bars1m_data = bars1m[-360:]
        low_price = np.array([bar.low_price for bar in bars1m_data])

        # 1. reverse price array to find low minimal
        if len(low_price) == 0:
            return
        peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
        if len(peaks_low) > 0:
            bar_low = bars1m_data[peaks_low[-1]]
            self.prev_low_price = bar_low.low_price
        else:
            self.prev_low_price = None
            return

        self.is_rebound = False

        # 1. check market crash: if price rebound
        if price < price_buy_ratio*bar_low.low_price:
            self.is_rebound = True

        # 2. check timestamp: 30min for buy low
        if bar_low.datetime < datetime.datetime.now(tz=MY_TZ)-datetime.timedelta(minutes=15):
            self.is_rebound = False

        if self.is_rebound:
            '''start chase rebound'''
            # 3. check current position
            cur_position = self.balance_info.data[self.base_currency].available*price
            if cur_position < 0.2 * self.max_invest:
                self.write_log(f'Chasing up {datetime.datetime.now(tz=MY_TZ)}')
                direction = Direction.LONG
                volume = self.generate_volume(price=price, direction=direction,
                                              check_position=True,
                                              check_probability=False,
                                              check_price=False,
                                              check_price_break=False,
                                              check_quota=False,
                                              check_break_risk=False)
                self.generate_order(price=price, volume=volume, direction=direction)
                self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def make_decision(self, price: float):
        ''''''
        # 1. swing trading
        self.swing_trading(price=price)

        # 2. chasing up
        if False:
            self.chase_up(price=price)

        # 3. killing down
        if False:
            self.kill_down(price=price)

        # 4. stop loss
        if True:
            self.stop_loss(price=price)

        # 5. take profit
        if True:
            self.take_profit(price=price)

        # if random.uniform(0, 1) < self.buy_prob:
        #     direction = Direction.LONG
        #     # 1. calc volume
        #     volume = self.generate_volume(price=price, direction=direction)
        #     # 2. price break
        #     #self.check_price_break(price=price, direction=direction)
        #     #print('In buy:', volume, self.lower_break, self.trading_quota)
        #     #if not self.lower_break and self.trading_quota:
        #         # 3. send multiple orders
        #     self.generate_order(price=price, volume=volume, direction=direction)
        #     #print('Sending buy order:', price)
        # if random.uniform(0, 1) < self.sell_prob:
        #     direction = Direction.SHORT
        #     # 1. calc volume
        #     volume = self.generate_volume(price=price, direction=direction)
        #     # 2. price break
        #     #self.check_price_break(price=price, direction=direction)
        #     #print('In sell:', volume)
        #     # if no upper breaking
        #     self.generate_order(price=price, volume=volume, direction=direction)
            # if not self.upper_break:
            #     # 3. send multiple orders
            #     self.generate_order(price=price, volume=volume, direction=direction)
            # else:
            #     # or if has profit
            #     if self.prev_buy_price and price > 1.10 * self.prev_buy_price:
            #         print('Has a good price:', price)
            #         self.generate_order(price=price, volume=volume, direction=direction)

    def update_ref_price(self):
        '''update reference price for buy and sell'''
        # 1. choose proper vline to calculate ref price
        kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
        kl60 = kline_1m[-60:]
        avg_vol = float(sum([kl.amount for kl in kl60]) / len(kl60))
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        vol = min([vol for vol in vol_list if avg_vol*10 < vol])

        self.vol_select = vol
        self.buy_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.05), 4))
        self.sell_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.95), 4))

        # for i, vol in enumerate(vol_list):
        #     self.buy_price[i] = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.05), 4))
        #     self.sell_price[i] = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.95), 4))
        #     spread = np.abs(self.sell_price[i]-self.buy_price[i])/(0.5*(self.buy_price[i]+self.sell_price[i]))
        #     if spread < 0.04:
        #         self.buy_price[i] = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.03), 4))
        #         self.sell_price[i] = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.97), 4))
        #     #print(i, self.buy_price[i], self.sell_price[i])
        # self.buy_price0, self.sell_price0 = self.buy_price[0], self.sell_price[0]
        # self.buy_price1, self.sell_price1 = self.buy_price[1], self.sell_price[1]
        # self.buy_price2, self.sell_price2 = self.buy_price[2], self.sell_price[2]
        # self.buy_price3, self.sell_price3 = self.buy_price[3], self.sell_price[3]
        # self.buy_price4, self.sell_price4 = self.buy_price[4], self.sell_price[4]

    def update_trade_prob(self, price: float):
        # 1. choose proper vline to calculate ref price
        # 2. update buy or sell probility
        self.buy_prob = self.calc_pro_buy(price=price, price_ref=self.buy_price, theta=self.theta, global_prob=self.global_prob)
        self.sell_prob = self.calc_pro_sell(price=price, price_ref=self.sell_price, theta=self.theta, global_prob=self.global_prob)

    def update_invest_position(self):
        '''update invest position'''
        price = self.last_trade.price
        if not price:
            return
        self.update_trade_prob(price=price)
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)
        pos_floor = np.floor(pos*10)/10
        self.max_invest = np.round((1.0 - pos_floor) * self.total_invest)
        self.min_invest = 0.2*self.total_invest

    def calc_price_gain_speed(self, num_vline: int = 3):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) < num_vline:
            return
        vlines_tmp = vlines[-1*num_vline:]
        total_gain_vol = 0
        total_vol = 0
        total_time = datetime.timedelta(seconds=0)
        for vl in vlines_tmp:
            total_gain_vol += (vl.close_price - vl.open_price) * vl.volume
            total_vol += vl.volume
            total_time += (vl.close_time - vl.open_time)
        if total_time.total_seconds() > 0 and total_vol > 0:
            trade_speed = total_vol / total_time.total_seconds()
            trade_gain = total_gain_vol / total_vol
        else:
            trade_speed = None
            trade_gain = None
        #self.trade_speed = np.round(total_vol / total_time.total_seconds(), 4)
        #self.trade_gain = np.round(total_gain_vol / total_vol, 4)
        return trade_gain, trade_speed

    def calc_avg_trade_price(self, direction: Direction, vol: float = None,
                             timedelta: datetime.timedelta = datetime.timedelta(minutes=60)):
        pos = 0
        price = 0
        if vol:
            for i, at in enumerate(reversed(self.account_trades)):
                if at.datetime > datetime.datetime.now(tz=MY_TZ) - timedelta:
                    if at.direction == direction:
                        price += at.price * at.volume
                        pos += at.volume
                        if pos > vol:
                            break
        else:
            for i, at in enumerate(reversed(self.account_trades)):
                if at.datetime > datetime.datetime.now(tz=MY_TZ) - timedelta:
                    if at.direction == direction:
                        price += at.price * at.volume
                        pos += at.volume
        if pos > 0.0001:
            price = price / pos
        return price, pos

    def update_avg_trade_price(self, timedelta: datetime.timedelta = datetime.timedelta(hours=6)):
        cur_position = self.balance_info.data[self.base_currency].available
        long_price, long_pos = self.calc_avg_trade_price(direction=Direction.LONG, vol=cur_position, timedelta=timedelta)
        short_price, short_pos = self.calc_avg_trade_price(direction=Direction.SHORT, vol=10, timedelta=timedelta)

        if long_pos > 0.0001:
            self.prev_buy_price = float(np.round(long_price, 4))
        else:
            self.prev_buy_price = None
        if short_pos > 0.0001:
            self.prev_sell_price = float(np.round(short_price, 4))
        else:
            self.prev_sell_price = None

        # long_price = 0
        # long_pos = 0
        # short_price = 0
        # short_pos = 0
        #
        # # self.balance_info.data[self.base_currency]
        # for i, at in enumerate(reversed(self.account_trades)):
        #     if at.datetime > datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(hours=3):
        #         if at.direction == Direction.LONG and long_pos < self.balance_info.data[self.base_currency].available:
        #             long_price += at.price*at.volume
        #             long_pos += at.volume
        #         if at.direction == Direction.SHORT:
        #             short_price += at.price*at.volume
        #             short_pos += at.volume
        #
        # if long_pos > 0.1:
        #     long_price = float(np.round(long_price/long_pos, 4))
        #     self.prev_buy_price = long_price
        # else:
        #     self.prev_buy_price = None
        # if short_pos > 0.1:
        #     short_price = float(np.round(short_price/short_pos, 4))
        #     self.prev_sell_price = short_price
        # else:
        #     self.prev_sell_price = None

    def update_break_count(self):
        if self.upper_break_count > 0:
            self.upper_break_count -= 1
        if self.upper_break_count == 0:
            self.upper_break = False
        else:
            self.upper_break = True

        if self.lower_break_count > 0:
            self.lower_break_count -= 1
        if self.lower_break_count == 0:
            self.lower_break = False
        else:
            self.lower_break = True

    def update_price_gain_speed_kline(self):
        pass

    def update_price_gain_speed_vline(self, num_vline: int = 3):
        self.trade_gain, self.trade_speed = self.calc_price_gain_speed(num_vline=num_vline)
        self.trade_gain = np.round(self.trade_gain, 4)
        self.trade_speed = np.round(self.trade_speed, 4)

    def check_gain_slip(self, count: int = 3):
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        kline_tmp = kline_1m[-1 * count:]
        close_open_ratio = [bar.close_price / bar.open_price for bar in kline_tmp]
        high_low_ratio = [bar.high_price / bar.low_price for bar in kline_tmp]
        gain_count = sum([int(close_open_ratio[i] > 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        slip_count = sum([int(close_open_ratio[i] < 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        self.is_gain = gain_count >= count
        self.is_slip = slip_count >= count

    def check_climb_retreat(self, thresh: float = 100, num_vline: int = 20):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) < num_vline:
            return
        vlines20 = vlines[-1*num_vline:]
        price_gain_vol = 0
        for vl in vlines20:
            price_gain_vol += (vl.close_price-vl.open_price)*vl.volume
        self.is_climb = price_gain_vol > thresh
        self.is_retreat = price_gain_vol < thresh

    def check_surge_slump(self, thresh_gain: float = 0, thresh_speed: float = 10, num_vline: int = 10):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) < num_vline:
            return
        vlines_tmp = vlines[-1 * num_vline:]
        total_gain_vol = 0
        total_vol = 0
        total_time = datetime.timedelta(seconds=0)
        for vl in vlines_tmp:
            total_gain_vol += (vl.close_price - vl.open_price) * vl.volume
            total_vol += vl.volume
            total_time += (vl.close_time - vl.open_time)
        vol_speed = total_vol / total_time.total_seconds()
        price_gain = total_gain_vol / total_vol
        self.is_surge = price_gain > thresh_gain & vol_speed > thresh_speed
        self.is_slump = price_gain < -1*thresh_gain & vol_speed > thresh_speed

    def check_hover(self):
        return False

    def update_market_status(self):
        '''check market status'''
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        if len(kline_1m) < 20:
            return
        # check bull market
        self.check_gain_slip(count=3)
        self.is_climb = self.check_climb()
        self.is_surge = self.check_surge()

        # check bear market
        self.is_slip = self.check_slip()
        self.is_retreat = self.check_retreat()
        self.is_slump = self.check_slump()

        # check hover market
        self.is_hover = self.check_hover()

    def update_market_trade(self):
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

            # debug_print = False
            # if debug_print:
            #     for vqi in self.vqg[self.vt_symbol].vq:
            #         print(self.vqg[self.vt_symbol].vq[vqi])
            #
            #     for vi in self.vg[self.vt_symbol].vlines:
            #         vl = self.vg[self.vt_symbol].vlines[vi]
            #         if len(vl) > 0:
            #             print(len(vl), vl[0], vl[-1])

    def update_variable(self):
        # variables = ['timer_count', 'upper_break', 'lower_break', 'upper_break_count', 'lower_break_count', 'buy_prob',
        #              'sell_prob', 'min_invest', 'max_invest', 'total_invest',
        #              'buy_price0', 'sell_price0', 'buy_price1', 'sell_price1', 'buy_price2', 'sell_price2',
        #              'buy_price3', 'sell_price3', 'buy_price4', 'sell_price4']
        self.timer_count = int(self.timer_count)
        self.upper_break_count = int(self.upper_break_count)
        self.lower_break_count = int(self.lower_break_count)
        self.buy_prob = float(self.buy_prob)
        self.sell_prob = float(self.sell_prob)
        self.min_invest = float(self.min_invest)
        self.max_invest = float(self.max_invest)
        self.total_invest = float(self.total_invest)

        #self.buy_price0, self.sell_price0 = float(self.buy_price[0]), float(self.sell_price[0])
        #self.buy_price1, self.sell_price1 = float(self.buy_price[1]), float(self.sell_price[1])
        #self.buy_price2, self.sell_price2 = float(self.buy_price[2]), float(self.sell_price[2])
        #self.buy_price3, self.sell_price3 = float(self.buy_price[3]), float(self.sell_price[3])
        #self.buy_price4, self.sell_price4 = float(self.buy_price[4]), float(self.sell_price[4])

    def on_timer(self):
        '''
        if data init, update market trades for vline queue generator, vline generator
        '''
        if not self.is_data_inited:
            return
        if self.timer_count % 1 == 0 and self.timer_count > 10:
            self.update_market_trade()
            self.update_price_gain_speed_vline(num_vline=3)

        if self.timer_count % 10 == 0 and self.timer_count > 10:
            if self.last_trade:
                price = self.last_trade.price
                self.check_price_break(price=price, direction=Direction.LONG)
                self.check_price_break(price=price, direction=Direction.SHORT)
                self.update_ref_price()
                #self.update_trade_prob(price=price)
                self.update_invest_position()
                self.update_avg_trade_price()
                self.make_decision(price=price)

        if self.timer_count % 60 == 0 and self.timer_count > 10:
            #self.update_ref_price()
            self.update_break_count()
            # for orderid in self.orders:
            #     order = self.orders[orderid]
            #     if order.datetime < datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(minutes=10):
            #         self.cancel_order(order.vt_orderid)
            self.trading_quota = True

        if self.timer_count % 3600 == 0 and self.timer_count > 10:
            self.cancel_all()

        self.timer_count += 1
        #if self.timer_count % 10 == 0 and self.timer_count > 10:
        self.update_variable()
        self.put_event()


if __name__ == '__main__':
    pass
