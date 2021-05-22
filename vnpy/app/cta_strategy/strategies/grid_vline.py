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
from pprint import pprint

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
                 'buy_prob', 'sell_prob', 'cur_invest', 'min_invest', 'max_invest', 'total_invest',
                 'buy_price', 'sell_price', 'vol_select',
                 'prev_buy_price', 'prev_sell_price', 'trade_speed', 'trade_gain',
                 'prev_high_price', 'prev_low_price', 'trading_quota']

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
        self.cur_invest = 0
        #self.cur_invest = {}

        # init price break count
        self.max_break_count = 4
        self.upper_break_count = self.max_break_count
        self.lower_break_count = self.max_break_count
        self.upper_break = True
        self.lower_break = True

        # previous buy or sell price
        self.prev_buy_price = None
        self.prev_buy_time = None
        self.prev_sell_price = None
        self.prev_sell_time = None

        # previous high and low peaks
        self.prev_high_price = None
        self.prev_high_time = None
        self.prev_low_price = None
        self.prev_low_time = None

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
        self.is_slip = False
        self.is_retreat = False
        self.is_slump = False

        #
        self.buy_price = None
        self.sell_price = None
        self.vol_select = self.market_params[self.symbol]['vline_vol_list'][0]

        # trading speed
        self.trade_speed = -1
        self.trade_gain = -1

        # position update time
        self.update_invest_limit_time = None

        # kline based features
        self.kline_phase1 = 20
        self.kline_phase2 = 3
        self.spread_vol1 = []
        self.spread_vol2 = []
        self.kline_phase = [3, 10, 20]
        self.spread_vol = {}
        self.kline_feature = {}
        self.kline_feature['spread_vol'] = {}
        for kp in self.kline_phase:
            self.spread_vol[kp] = []

        self.init_data()

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
        self.check_price_break(price=price, direction=Direction.LONG, use_vline=True)
        self.check_price_break(price=price, direction=Direction.SHORT, use_vline=True)
        self.update_trade_prob(price=price)
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
        #print(vol, vline)
        #self.vg[self.vt_symbol].update_vline(vline=vline, vol=vol)

    def on_kline(self, bar: BarData):
        self.kline_buf.append(bar)
        print(len(self.kline_buf), bar)

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
        self.update_avg_trade_price()

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

    def generate_volume(self, price: float, direction: Direction, ratio: float = 1.0,
                        check_balance=True, check_position=True) -> float:
        volume = 0.0
        if direction == Direction.LONG:
            # 1. check balance
            volume = random.uniform(0, 1) * self.trade_amount / price
            volume = volume * ratio
            if check_balance:
                #avail_volume = self.balance_info.data[self.quote_currency].available
                avail_volume = self.get_current_position(quote=True, available=True)
                volume = np.round(np.min([volume, avail_volume / price]), 4)
                #print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                #cur_position = self.balance_info.data[self.base_currency].available*price
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position > self.max_invest:
                    volume = np.round(volume * 0.0, 4)
                    #print(f'check_position {direction.value} {volume}')
        elif direction == Direction.SHORT:
            # 1. check balance
            if check_balance:
                volume = np.round(random.uniform(0, 1) * self.trade_amount / price, 2)
                volume = volume * ratio
                #avail_volume = self.balance_info.data[self.base_currency].available
                avail_volume = self.get_current_position(base=True, available=True)
                if volume > 0.9*avail_volume:
                    volume = np.round(avail_volume, 4)
                else:
                    volume = np.round(np.min([volume, avail_volume]), 4)
                #print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                #cur_position = self.balance_info.data[self.base_currency].available*price
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position < self.min_invest:
                    volume = np.round(volume * 0.5, 4)
                #print(f'check_position {direction.value} {volume}')
        else:
            volume = 0.0
        return volume

    def check_probability(self, direction: Direction):
        ratio_prob = 0.0
        if direction == Direction.LONG:
            if self.buy_prob > self.sell_prob and self.sell_prob < 0.03:
                ratio_prob = 1.0
        elif direction == Direction.SHORT:
            if self.sell_prob > self.buy_prob and self.buy_prob < 0.03:
                ratio_prob = 1.0
        return ratio_prob

    def check_lower_break(self):
        ratio = 0.0
        if self.lower_break:
            ratio = 1.0
        return ratio

    def check_upper_break(self):
        ratio = 0.0
        if self.upper_break:
            ratio = 1.0
        return ratio

    def check_quota(self):
        ratio = 0.0
        if self.trading_quota:
            ratio = 1.0
        return ratio

    def check_fall_down(self, price: float):
        td30m = datetime.timedelta(minutes=30)
        prev_sell_price, prev_sell_pos, prev_sell_timedelta = self.calc_avg_trade_price(direction=Direction.SHORT, timedelta=td30m)
        ratio_fall_down = 0.0
        if prev_sell_pos > 0 and price > 0.98 * prev_sell_price:
            ratio_fall_down = min(max((0.98 - price / prev_sell_price) * 100 * 0.1, 0), 4)
        ratio = ratio_fall_down
        return ratio

    def check_price_break_vline(self, price: float, direction: Direction, num_vline: int = 10):
        if not self.is_data_inited:
            return
        # detect vline
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) < num_vline:
            return
        min_price = np.min([vl.low_price for vl in vlines[-1 * num_vline:]])
        max_price = np.max([vl.high_price for vl in vlines[-1 * num_vline:]])
        self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)
        if direction == Direction.LONG:
            if price <= min_price:
                self.lower_break_count = int(1.0 * self.max_break_count)
                self.lower_break = True
        elif direction == Direction.SHORT:
            if price >= max_price:
                self.upper_break_count = int(1.0 * self.max_break_count)
                self.upper_break = True
        else:
            pass

    def check_price_break_kline(self, price: float, direction: Direction, num_kline: int = 20):
        if not self.is_data_inited:
            return
        # detect kline
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        if len(kline_1m) < num_kline:
            return

        min_price = np.min([kl.low_price for kl in kline_1m[-1*num_kline:]])
        max_price = np.max([kl.high_price for kl in kline_1m[-1*num_kline:]])
        self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)

        if direction == Direction.LONG:
            if price <= min_price:
                self.lower_break_count = int(1.0 * self.max_break_count)
                # if 0.5 < self.pos < 1.0:
                #     self.lower_break_count = int(1.5 * self.max_break_count)
                # elif 0.1 <= self.pos < 0.5:
                #     self.lower_break_count = int(1.0 * self.max_break_count)
                # elif 0.0 <= self.pos < 0.1:
                #     self.lower_break_count = int(0.5 * self.max_break_count)
                # else:
                #     self.lower_break_count = int(1.0 * self.max_break_count)
                self.lower_break = True
        elif direction == Direction.SHORT:
            if price >= max_price:
                self.upper_break_count = int(1.0 * self.max_break_count)
                # if 0.0 < self.pos < 0.3:
                #     self.upper_break_count = int(2.0 * self.max_break_count)
                # elif 0.3 <= self.pos < 0.9:
                #     self.upper_break_count = int(1.0 * self.max_break_count)
                # elif 0.9 <= self.pos < 1.0:
                #     self.upper_break_count = int(1.0 * self.max_break_count)
                # else:
                #     self.upper_break_count = int(1.0 * self.max_break_count)
                self.upper_break = True
        else:
            pass

    def check_price_break(self, price: float, direction: Direction,
                          use_vline: bool = True, use_kline: bool = True,
                          num_kline: int = 10,
                          num_vline: int = 10):
        if not self.is_data_inited:
            return
        # detect kline
        if use_vline:
            self.check_price_break_vline(price=price, direction=direction, num_vline=num_vline)
        if use_kline:
            self.check_price_break_kline(price=price, direction=direction, num_kline=num_kline)

    def check_min_max_price(self, price: float, direction: Direction):
        '''check min max price in previous time duration'''
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        bars1m_data = bars1m[-360:]
        min_price = min([bar.low_price for bar in bars1m_data])
        max_price = max([bar.high_price for bar in bars1m_data])
        ratio = 0.0
        if direction == Direction.LONG:
            if 0.90 * max_price < price < 0.95 * max_price:
                ratio = 0.5
            elif 0.85 * max_price < price < 0.90 * max_price:
                ratio = 1.0
            elif 0.80 * max_price < price < 0.85 * max_price:
                ratio = 1.5
            elif price < 0.80 * max_price:
                ratio = 2.0
            else:
                ratio = 0.0
        elif direction == Direction.SHORT:
            if 1.05 * min_price < price < 1.10 * min_price:
                ratio = 0.5
            elif 1.10 * min_price < price < 1.15 * min_price:
                ratio = 1.0
            elif 1.15 * min_price < price < 1.20 * min_price:
                ratio = 1.5
            elif price > 1.20 * min_price:
                ratio = 2.0
            else:
                ratio = 0.0
        return ratio

    def check_prev_high_low_price(self, price: float,
                                  direction: Direction,
                                  timedelta: datetime.timedelta = datetime.timedelta(minutes=30)):
        '''check previous high and low price'''
        ratio_base = 0.2
        ratio_high = 0.0
        ratio_low = 0.0
        ratio = 1.0
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        if direction == Direction.LONG:
            if self.prev_high_price and self.prev_high_time and datetime_now > self.prev_high_time + timedelta:
                ratio_high = min(max((0.95-price/self.prev_high_price)*100*ratio_base, 0), 4)
                ratio_high = float(np.round(ratio_high, 4))
            if self.prev_low_price:
                ratio_low = min(max((1.01-price/self.prev_low_price)*100*ratio_base, 0), 4)
                ratio_low = float(np.round(ratio_low, 4))
            ratio = max(ratio_low, ratio_high)
        elif direction == Direction.SHORT:
            if self.prev_low_price and self.prev_low_time and datetime_now > self.prev_low_time + timedelta:
                ratio_low = min(max((price/self.prev_low_price-1.05)*100*ratio_base, 0), 4)
                ratio_low = float(np.round(ratio_low, 4))
            if self.prev_high_price:
                ratio_high = min(max((price/self.prev_high_price-0.99)*100*ratio_base, 0), 4)
                ratio_high = float(np.round(ratio_high, 4))
            ratio = max(ratio_high, ratio_low)
        return ratio

    def check_prev_buy_sell_price(self, price: float,
                                  direction: Direction,
                                  timedelta: datetime.timedelta = datetime.timedelta(minutes=10)):
        '''check previous buy and sell price'''
        ratio = 1.0
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        ratio_buy = 1.0
        ratio_sell = 1.0
        if direction == Direction.LONG:
            if self.prev_buy_price and self.prev_buy_time and datetime_now < self.prev_buy_time + timedelta:
                if 0.98 * self.prev_buy_price < price < 0.99 * self.prev_buy_price:
                    ratio_buy = 0.5
                elif 0.95 * self.prev_buy_price < price < 0.98 * self.prev_buy_price:
                    ratio_buy = 1.0
                elif 0.90 * self.prev_buy_price < price < 0.95 * self.prev_buy_price:
                    ratio_buy = 1.5
                elif price < 0.90 * self.prev_buy_price:
                    ratio_buy = 2.0
                else:
                    ratio_buy = 0.0
            if self.prev_buy_time and datetime_now > self.prev_buy_time + timedelta:
                ratio_buy = 0.4
            ratio = ratio_buy
        if direction == Direction.SHORT:
            if self.prev_sell_price and self.prev_sell_time and datetime_now < self.prev_sell_time + timedelta:
                if 0.99 * self.prev_sell_price < price < 1.01 * self.prev_sell_price:
                    ratio_sell = 0.5
                elif 1.01 * self.prev_sell_price < price < 1.05 * self.prev_sell_price:
                    ratio_sell = 1.0
                elif 1.05 * self.prev_sell_price < price < 1.10 * self.prev_sell_price:
                    ratio_sell = 1.5
                elif price > 1.10 * self.prev_sell_price:
                    ratio_sell = 2.0
                else:
                    ratio_sell = 0.0
            if self.prev_sell_time and datetime_now > self.prev_sell_time + timedelta:
                ratio_sell = 0.4
            ratio = ratio_sell
        return ratio

    def check_profit(self, price: float):
        '''check profit'''
        avail_volume = self.get_current_position(base=True, available=True)
        prev_buy_price, prev_buy_pos, prev_buy_timedelta = self.calc_avg_trade_price(direction=Direction.LONG, vol=avail_volume, timedelta=datetime.timedelta(minutes=180))
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        prev_buy_time = datetime_now - prev_buy_timedelta
        holding_time = datetime.timedelta(minutes=180)
        ratio_take_profit = 0.0
        if prev_buy_price > 0.1 * price:
            # 1. check price
            if 1.05*prev_buy_price < price < 1.10*prev_buy_price:
                ratio_take_profit = 0.5
            elif 1.10*prev_buy_price < price < 1.15*prev_buy_price:
                ratio_take_profit = 1.0
            elif price > 1.15*prev_buy_price:
                ratio_take_profit = 1.5
            else:
                ratio_take_profit = 0.25
            # 2. check holding time
            if datetime_now < prev_buy_time + holding_time:
                ratio_take_profit = ratio_take_profit * 2
            # 3. check position
            if prev_buy_pos > 0.7 * self.total_invest:
                ratio_take_profit = ratio_take_profit * 2
            ratio_take_profit = float(np.round(ratio_take_profit, 4))
        return ratio_take_profit

    def release_trading_quota(self, timestep: int = 10):
        if self.timer_count % timestep == 0:
            self.trading_quota = True

    def check_rebound(self, price: float):
        # 1. check historical trades in 15 mins
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        timedelta = datetime.timedelta(minutes=15)
        avg_price = 0
        pos = 0
        total_timedelta = datetime.timedelta(seconds=0)
        for i, at in enumerate(reversed(self.account_trades)):
            if at.datetime > datetime_now - timedelta:
                if at.direction == Direction.LONG:
                    avg_price += at.price * at.volume
                    pos += at.volume
                    # datetime_last = at.datetime
                    total_timedelta += (datetime_now - at.datetime) * at.volume
        if pos > 0.01:
            avg_price = avg_price / pos
        # 2. if there is profit, sell immediately
        ratio_fast_sell = 0.0
        if 1.03 * avg_price < price < 1.05 * avg_price:
            ratio_fast_sell = 0.5
        elif 1.05 * avg_price < price < 1.10 * avg_price:
            ratio_fast_sell = 1.0
        elif price > 1.10 * avg_price:
            ratio_fast_sell = 2.0
        else:
            ratio_fast_sell = 0.0
        return ratio_fast_sell

    def generate_order(self, price: float, volume: float, direction: Direction, w: float = 1.0):
        volume1 = float(np.round(volume * w, 2))
        if direction == Direction.LONG:
            if random.uniform(0, 1) < 0.5 or True:
                if self.is_surge:
                    price = np.round(price * (1 + random.uniform(0, 5) * 0.01), 4)
                else:
                    price = np.round(price * (1 + random.uniform(0, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.bids.keys())[0]+0.0001, 4)
            if volume1*price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        elif direction == Direction.SHORT:
            if random.uniform(0, 1) < 0.5 or True:
                if self.is_slump:
                    price = np.round(price * (1 - random.uniform(0, 5) * 0.01), 4)
                else:
                    price = np.round(price * (1 - random.uniform(0, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.asks.keys())[0]-0.0001, 4)
            if volume1 * price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        else:
            return

    def swing_trading_long(self, price: float, debug_print: bool = True):
        exec_order = False
        td30m = datetime.timedelta(minutes=30)
        td10m = datetime.timedelta(minutes=10)
        td5m = datetime.timedelta(minutes=5)

        # 1. check probability
        ratio_prob = self.check_probability(direction=Direction.LONG)

        # 2. lower price break
        ratio_break = self.check_lower_break()

        # 3. lower than previous buy price
        ratio_buy = self.check_prev_buy_sell_price(price=price, direction=Direction.LONG, timedelta=td5m)

        # 4. lower than previous high price
        ratio_high = self.check_prev_high_low_price(price=price, direction=Direction.LONG, timedelta=td30m)

        # 5. price is low enough
        ratio_min = self.check_min_max_price(price=price, direction=Direction.LONG)

        # 6. has trading quota
        ratio_quota = self.check_quota()

        cur_invest = self.get_current_position(base=True, volume=True) * price
        is_low_position = cur_invest < 0.2 * self.max_invest
        ratio = 0.0
        if not is_low_position:
            ratio_all = ratio_prob * ratio_break * ratio_buy * ratio_high * ratio_min * ratio_quota
            if ratio_all > 0:
                ratio = max(min(ratio_buy, ratio_high, ratio_min), 0.25)
                exec_order = True
        else:
            ratio = 0.5 * ratio_prob * ratio_break * max(ratio_buy, ratio_high, ratio_min) * ratio_quota
            exec_order = ratio > 0.0

        if self.is_slump:
            ratio_all = ratio_prob * max(ratio_buy, ratio_high, ratio_min) * ratio_quota
            has_position = cur_invest < 0.5 * self.max_invest
            if ratio_all > 0 and has_position:
                ratio = max(ratio_buy, ratio_high, ratio_min)
                exec_order = True

        if debug_print:
            print(f'{Direction.LONG.value} E:{exec_order} P:{ratio_prob} B:{ratio_break} BUY:{ratio_buy} H:{ratio_high} MIN:{ratio_min} Q:{ratio_quota}')
        return exec_order, ratio

    def swing_trading_short(self, price: float, debug_print: bool = True):
        exec_order = False
        td30m = datetime.timedelta(minutes=30)
        td10m = datetime.timedelta(minutes=10)
        td5m = datetime.timedelta(minutes=5)

        # 1. check probability
        ratio_prob = self.check_probability(direction=Direction.SHORT)

        # 2. lower price break
        ratio_break = self.check_upper_break()

        # 3. higher than previous sell price
        ratio_sell = self.check_prev_buy_sell_price(price=price, direction=Direction.SHORT, timedelta=td5m)

        # 4. higher than previous low price
        ratio_low = self.check_prev_high_low_price(price=price, direction=Direction.SHORT, timedelta=td30m)

        # 5. price is high enough
        ratio_max = self.check_min_max_price(price=price, direction=Direction.SHORT)

        # 6. take profit
        ratio_profit = self.check_profit(price=price)

        # 7. has trading quota
        ratio_quota = self.check_quota()

        # 8. check rebound case
        ratio_fast_sell = self.check_rebound(price=price)

        # 1. normal case
        ratio = 0.0
        ratio_all = ratio_prob * ratio_break * ratio_sell * ratio_low * ratio_max * ratio_profit * ratio_quota
        if ratio_all > 0.0:
            ratio = max(ratio_sell, ratio_low, ratio_max, ratio_profit)
            exec_order = True

        '''solve rebound case'''
        # 2. fast sell case
        if ratio_fast_sell > 0.1:
            ratio = ratio_fast_sell
            exec_order = True

        # 3. surge sell
        if self.is_surge:
            '''check current '''
            ratio_vol = 1.0
            total_vol = self.get_current_position(base=True, volume=True)
            if total_vol*price < 0.2 * self.total_invest:
                ratio_vol = 0.25
            ratio_all = ratio_prob * ratio_sell * ratio_low * ratio_max * ratio_quota
            # 1. check position here
            ratio_all = ratio_all * ratio_vol
            if ratio_all > 0.0:
                ratio = max(ratio_sell, ratio_low, ratio_max, ratio_profit)
                exec_order = True

        if debug_print:
            print(f'{Direction.SHORT.value} E:{exec_order} P:{ratio_prob} B:{ratio_break} SELL:{ratio_sell} L:{ratio_low} MAX:{ratio_max} P:{ratio_profit} Q:{ratio_quota}')
        return exec_order, ratio

    def make_decision_swing_trading(self, price: float, direction: Direction):
        if not self.is_data_inited:
            return
        exec_order = False
        ratio = 1.0
        if direction == Direction.LONG:
            exec_order, ratio = self.swing_trading_long(price=price)
        elif direction == Direction.SHORT:
            exec_order, ratio = self.swing_trading_short(price=price)
        else:
            pass
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
            volume = self.generate_volume(price=price, direction=direction, ratio=ratio,
                                          check_balance=True, check_position=True)
            print(f'{direction.value} {price} {volume}')
            # 2. generate order
            self.generate_order(price=price, volume=volume, direction=direction)
        if random.uniform(0, 1) < self.sell_prob:
            direction = Direction.SHORT
            # 0. exec sell
            exec_sell, ratio = self.make_decision_swing_trading(price=price, direction=direction)
            if not exec_sell:
                return
            # 1. calc volume
            volume = self.generate_volume(price=price, direction=direction, ratio=ratio,
                                          check_balance=True, check_position=True)
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
                volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=False)
                self.generate_order(price=price, volume=volume, direction=direction)
                self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def take_profit(self, price: float, take_profit_ratio: float = 0.3):
        if self.timer_count % 60 != 0:
            return
        if self.prev_buy_price and price > (1+take_profit_ratio)*self.prev_buy_price:
            #self.write_log(f'take_profit {datetime.datetime.now(tz=MY_TZ)}')
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=False)
            self.generate_order(price=price, volume=volume, direction=direction)
            self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def chase_up(self, price: float, price_buy_ratio: float = 1.02):
        '''
        1. trading volume change: low to high
        2. previous price variation
        3. previous high low price bound
        '''
        # 1. check current price with previous kline: is_slip or is_climb
        # 1. check current price with previous price: low or high
        # 2. check previous low peaks price
        # 3. check holding position
        # 4. check price break kline
        # 5. trading volume change: low to high
        # 6. price break

        # 1. check kline
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        num_kline = len(bars1m)
        bars1m_data = bars1m[-360:]
        low_price = np.array([bar.low_price for bar in bars1m_data])
        high_price = np.array([bar.high_price for bar in bars1m_data])
        # phase 1: -20:-4, phase 2: -4:len(kline)
        spread_vol1, total_vol1, avg_spread_vol1 = self.calc_spread_vol_kline(start=num_kline-20, end=num_kline-4)
        spread_vol2, total_vol2, avg_spread_vol2 = self.calc_spread_vol_vline(start=num_kline-4, end=num_kline)

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
                                              check_position=True)
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
                                          check_position=True)
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
                volume = self.generate_volume(price=price, direction=direction, check_position=True)
                self.generate_order(price=price, volume=volume, direction=direction)
                self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def make_decision(self, price: float):
        ''''''
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        num_vlines = len(vlines)
        tt = num_vlines
        #self.calc_spread_turn_over_signal(num_vline1=100, num_vline2=5)
        spread_vol1, _, _ = self.calc_spread_vol_vline(start=tt - 100, end=tt)
        spread_vol2, _, _ = self.calc_spread_vol_vline(start=tt - 10, end=tt)
        spread_vol3, _, _ = self.calc_spread_vol_vline(start=tt - 5, end=tt)
        spread_vol4, _, _ = self.calc_spread_vol_vline(start=tt - 3, end=tt)
        spread_vol5, _, _ = self.calc_spread_vol_vline(start=tt - 1, end=tt)
        print('%.6f, %.6f, %.6f %.6f %.6f'%(spread_vol1, spread_vol2, spread_vol3, spread_vol4, spread_vol5))
        # 1. swing trading
        if False:
            self.swing_trading(price=price)

        # 2. chasing up
        if False:
            self.chase_up(price=price)

        # 3. killing down
        if False:
            self.kill_down(price=price)

        # 4. stop loss
        if False:
            self.stop_loss(price=price)

        # 5. take profit
        if False:
            self.take_profit(price=price)

        # 6. re-balance operation
        if False:
            pass

    def update_high_low_price(self):
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        bars1m_data = bars1m[-360:]
        low_price = np.array([bar.low_price for bar in bars1m_data])
        high_price = np.array([bar.high_price for bar in bars1m_data])

        # 1. reverse price array to find low minimal
        if len(low_price) > 0:
            peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
            if len(peaks_low) > 0:
                self.prev_low_price = bars1m_data[peaks_low[-1]].low_price
            else:
                self.prev_low_price = None

        if len(high_price) > 0:
            peaks_high, _ = find_peaks(high_price, distance=10, prominence=0.3, width=5)
            if len(peaks_high) > 0:
                self.prev_high_price = bars1m_data[peaks_high[-1]].high_price
            else:
                self.prev_high_price = None

    def update_ref_price(self):
        '''update reference price for buy and sell'''
        # 1. choose proper vline to calculate ref price
        kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
        kl360 = kline_1m[-20:]
        avg_vol = float(sum([kl.amount for kl in kl360]) / len(kl360))
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        vol = min([vol for vol in vol_list if avg_vol*20 < vol])

        self.vol_select = vol
        self.buy_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.05), 4))
        self.sell_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.95), 4))

    def update_trade_prob(self, price: float):
        # 1. choose proper vline to calculate ref price
        # 2. update buy or sell probility
        if self.buy_price:
            self.buy_prob = self.calc_pro_buy(price=price, price_ref=self.buy_price, theta=self.theta, global_prob=self.global_prob)
        if self.sell_price:
            self.sell_prob = self.calc_pro_sell(price=price, price_ref=self.sell_price, theta=self.theta, global_prob=self.global_prob)

    def update_position_budget(self, price: float):
        # check current position
        #cur_position = self.balance_info.data[self.base_currency].available * price
        cur_position = self.get_current_position(base=True, available=True)*price
        if cur_position > 0.9*self.max_invest:
            self.max_invest = min(self.total_invest, cur_position+0.1*self.total_invest)

    def allocate_invest_limit(self, unit_size: int = 1, unit_ratio: float = 0.1):
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        self.max_invest = self.max_invest + unit_size * unit_ratio * self.total_invest
        self.update_invest_limit_time = datetime_now

    def update_invest_limit(self, update_time_period: datetime.timedelta = datetime.timedelta(minutes=5)):
        '''
        1. current invest: max_invest = max_invest + base_invest, and allocate periodically
        2. allocate more invest limit for specific case
        '''
        if self.last_trade:
            price = self.last_trade.price
        else:
            return
        # 1. adjust position base on current invest
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        base_invest = 0.1 * self.total_invest
        cur_invest = self.get_current_position(base=True, volume=True) * price
        self.cur_invest = float(np.round(cur_invest, 4))
        new_max_invest = min(max(int(self.cur_invest/base_invest+1)*base_invest, base_invest), self.total_invest)

        if not self.update_invest_limit_time:
            self.max_invest = new_max_invest
            self.update_invest_limit_time = datetime_now

        if self.update_invest_limit_time+update_time_period < datetime_now:
            self.update_invest_limit_time = datetime_now
            self.max_invest = min(self.total_invest, new_max_invest)

    def update_invest_position(self):
        '''update invest position'''
        price = self.last_trade.price
        if not price:
            return
        self.update_trade_prob(price=price)
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)
        pos_floor = np.floor(pos*10)/10

        self.min_invest = 0.2 * self.total_invest
        base_invest = (1.0 - pos_floor) * self.total_invest * 0.5
        self.max_invest = base_invest + self.min_invest

        # update budget from current position
        #cur_position = self.balance_info.data[self.base_currency].available * price
        cur_position = self.get_current_position(base=True, available=True)*price
        if cur_position > 0.9 * self.max_invest:
            self.max_invest = min(self.total_invest, self.max_invest + 0.1 * self.total_invest)
        self.max_invest = np.round(self.max_invest, 4)

    def calc_vline_break(self):
        pass

    def calc_spread_vol_vline(self, start: int, end: int) -> float:
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        avg_spread_vol = 0
        spread_vol = 0
        total_vol = 0
        if not start:
            start = 0
        if not end:
            end = len(vlines)
        if start and end and start < end and start <= len(vlines) and end <= len(vlines):
            vline_start_end = vlines[start: end]
            spread_vol = np.sum([(vl.close_price - vl.open_price) / vl.open_price * vl.volume for vl in vline_start_end])
            total_vol = np.sum([vl.volume for vl in vline_start_end])
            #avg_vol = total_vol / len(vline_start_end)
            if total_vol > 0:
                avg_spread_vol = spread_vol / total_vol
        return spread_vol, total_vol, avg_spread_vol

    def calc_spread_vol_kline(self, start: int, end: int, interval: Interval = Interval.MINUTE) -> float:
        klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
        #num_kline = len(klines)
        avg_spread_vol = 0
        spread_vol = 0
        total_vol = 0
        if not start:
            start = 0
        if not end:
            end = len(klines)
        if start and end and start < end and start <= len(klines) and end <= len(klines):
            kline_start_end = klines[start: end]
            spread_vol = np.sum([(kl.close_price - kl.open_price) / kl.open_price * kl.volume for kl in kline_start_end])
            total_vol = np.sum([kl.volume for kl in kline_start_end])
            if total_vol > 0:
                avg_spread_vol = spread_vol / total_vol
        return spread_vol, total_vol, avg_spread_vol

    def calc_gain_speed(self, num_vline: int = 3):
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
        total_timedelta = datetime.timedelta(seconds=0)
        datetime_now = datetime.datetime.now(tz=MY_TZ)
        datetime_last = None
        avg_timedelta = datetime.timedelta(seconds=0)
        if vol:
            for i, at in enumerate(reversed(self.account_trades)):
                if at.datetime > datetime_now - timedelta:
                    if at.direction == direction:
                        price += at.price * at.volume
                        pos += at.volume
                        #datetime_last = at.datetime
                        total_timedelta += (datetime_now - at.datetime) * at.volume
                        if pos > vol:
                            break
        else:
            for i, at in enumerate(reversed(self.account_trades)):
                if at.datetime > datetime_now - timedelta:
                    if at.direction == direction:
                        price += at.price * at.volume
                        pos += at.volume
                        #datetime_last = at.datetime
                        total_timedelta += (datetime_now - at.datetime) * at.volume
        if pos > 0.0001:
            price = price / pos
            avg_timedelta = total_timedelta / pos
        return price, pos, avg_timedelta

    def update_avg_trade_price(self, timedelta: datetime.timedelta = datetime.timedelta(hours=6)):
        #cur_position = self.balance_info.data[self.base_currency].available
        if self.balance_info:
            cur_position = self.get_current_position(base=True, available=True)
            cur_datetime = datetime.datetime.now(tz=MY_TZ)
            long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG,
                                                                             vol=cur_position,
                                                                             timedelta=timedelta)
            short_price, short_pos, short_timedelta = self.calc_avg_trade_price(direction=Direction.SHORT,
                                                                                vol=10,
                                                                                timedelta=timedelta)
            long_datetime = cur_datetime - long_timedelta
            short_datetime = cur_datetime - short_timedelta
            if long_pos > 0.0001:
                self.prev_buy_price = float(np.round(long_price, 4))
                self.prev_buy_time = long_datetime
            else:
                self.prev_buy_price = None
                self.prev_buy_time = None
            if short_pos > 0.0001:
                self.prev_sell_price = float(np.round(short_price, 4))
                self.prev_sell_time = short_datetime
            else:
                self.prev_sell_price = None
                self.prev_sell_time = None

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

    def update_price_gain_speed_vline(self, num_vline: int = 3, time_step: int = 1):
        self.trade_gain, self.trade_speed = self.calc_gain_speed(num_vline=num_vline)
        self.trade_gain = np.round(self.trade_gain, 4)
        self.trade_speed = np.round(self.trade_speed, 4)
        self.check_surge_slump(thresh_gain=0.01, thresh_speed=30, num_vline=5)

    def determine_market_status_vline(self):
        pass

    def check_gain_slip(self, count: int = 3):
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        kline_tmp = kline_1m[-1 * count:]
        close_open_ratio = [bar.close_price / bar.open_price for bar in kline_tmp]
        high_low_ratio = [bar.high_price / bar.low_price for bar in kline_tmp]
        gain_count = sum([int(close_open_ratio[i] > 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        slip_count = sum([int(close_open_ratio[i] < 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        self.is_gain = gain_count >= count
        self.is_slip = slip_count >= count

    def calc_spread_turn_over_signal(self, num_vline1: int = 1000, num_vline2: int = 5):
        '''1. previous negative spread, 2. receive position spread'''
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        num_vlines = len(vlines)
        if num_vlines < num_vline1 or num_vlines < num_vline2:
            return 
        s1 = num_vlines - num_vline1
        e1 = num_vlines - num_vline2
        s2 = num_vlines - num_vline2
        e2 = num_vlines - 1
        spread_vol1 = self.calc_spread_vol_vline(start=s1, end=e1)
        spread_vol2 = self.calc_spread_vol_vline(start=s2, end=e2)
        if spread_vol2 > 0.0001:
            pass
        print()
        print(spread_vol1)
        print(vlines[s1])
        print(vlines[e1])
        print(spread_vol2)
        print(vlines[s2])
        print(vlines[e2])

    def check_gain_slip_vline(self, start: int = None, end: int = None, num_vline: int = 3, thresh: float = 0.01):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if start and end and start < end and start < len(vlines) and end < len(vlines):
            vline_start_end = vlines[start: end]
            avg_spread_vol = np.mean([(vl.close_price-vl.open_price)/vl.open_price * vl.volume for vl in vline_start_end])
            avg_vol = np.mean([vl.volume for vl in vline_start_end])
            if avg_spread_vol > thresh*avg_vol:
                self.is_gain = True
            elif avg_spread_vol < -1*thresh*avg_vol:
                self.is_slip = True
            else:
                self.is_gain = False
                self.is_slip = False

        # kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        # kline_tmp = kline_1m[-1 * count:]
        # close_open_ratio = [bar.close_price / bar.open_price for bar in kline_tmp]
        # high_low_ratio = [bar.high_price / bar.low_price for bar in kline_tmp]
        # gain_count = sum(
        #     [int(close_open_ratio[i] > 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        # slip_count = sum(
        #     [int(close_open_ratio[i] < 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
        # self.is_gain = gain_count >= count
        # self.is_slip = slip_count >= count

    def check_climb_retreat(self, thresh: float = 100, num_vline: int = 20):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) < num_vline:
            self.is_climb = False
            self.is_retreat = False
            return
        vlines20 = vlines[-1*num_vline:]
        price_gain_vol = 0
        for vl in vlines20:
            price_gain_vol += (vl.close_price-vl.open_price)*vl.volume
        self.is_climb = price_gain_vol > thresh
        self.is_retreat = price_gain_vol < thresh

    def check_surge_slump(self, thresh_gain: float = 0.01, thresh_speed: float = 10, num_vline: int = 10):
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
        self.is_surge = (price_gain > thresh_gain) & (vol_speed > thresh_speed)
        self.is_slump = (price_gain < -1*thresh_gain) & (vol_speed > thresh_speed)

    def check_hover(self):
        return False

    def get_current_position(self, base=False, quote=False, available=False, volume=False):
        pos = None
        if base:
            if available:
                pos = self.balance_info.data[self.base_currency].available
            elif volume:
                pos = self.balance_info.data[self.base_currency].volume
        if quote:
            if available:
                pos = self.balance_info.data[self.quote_currency].available
            elif volume:
                pos = self.balance_info.data[self.quote_currency].volume
        return pos

    def update_market_status(self):
        '''check market status'''
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        if len(kline_1m) < 20:
            return
        # check bull market
        self.check_gain_slip(count=3)
        #self.is_climb = self.check_climb()
        #self.is_surge = self.check_surge()

        # check bear market
        self.is_slip = self.check_slip()
        self.is_retreat = self.check_retreat()
        self.is_slump = self.check_slump()

        # check hover market
        self.is_hover = self.check_hover()

    def update_market_trade(self, time_step: int = 1):
        if not self.is_data_inited:
            return
        if self.timer_count % time_step == 0:
            for t in self.trade_buf:
                self.vqg[t.vt_symbol].update_market_trades(trade=t)

            for t in self.trade_buf:
                self.vg[t.vt_symbol].update_market_trades(trade=t)

            for bar in self.kline_buf:
                self.kqg.update_bar(bar=bar)

                # update kline based features here:
                if bar.interval == Interval.MINUTE:
                    self.update_kline_feature(bar=bar, interval=Interval.MINUTE)

            self.trade_buf = []
            self.kline_buf = []
            self.tick_buf = []

    def update_kline_feature(self, bar: BarData, interval: Interval = Interval.MINUTE):
        # update kline based features
        for kp in self.kline_phase:
            start = -1 * kp
            end = None
            spread_vol, total_vol, avg_spread_vol = self.calc_spread_vol_kline(start=start, end=end, interval=interval)




        spread_vol1, total_vol1, avg_spread_vol1 = self.calc_spread_vol_kline(start=-1 * self.kline_phase1,
                                                                              end=-1 * self.kline_phase2,
                                                                              interval=interval)
        spread_vol2, total_vol2, avg_spread_vol2 = self.calc_spread_vol_kline(start=-1 * self.kline_phase2,
                                                                              end=None,
                                                                              interval=interval)
        klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
        if len(self.spread_vol1) == 0:
            self.spread_vol1.append(spread_vol1)
        else:
            if bar.open_time == klines[-1].open_time:
                self.spread_vol1[-1] = spread_vol1
            else:
                self.spread_vol1.append(spread_vol1)

        if len(self.spread_vol2) == 0:
            self.spread_vol2.append(spread_vol2)
        else:
            if bar.open_time == klines[-1].open_time:
                self.spread_vol2[-1] = spread_vol2
            else:
                self.spread_vol2.append(spread_vol2)
        #vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
        print(len(self.spread_vol1), spread_vol1, spread_vol2, klines[-1].open_time, klines[-1].datetime)

    def update_variable(self):
        if self.timer_count > 10:
            self.timer_count = int(self.timer_count)
            self.upper_break_count = int(self.upper_break_count)
            self.lower_break_count = int(self.lower_break_count)
            self.buy_prob = float(self.buy_prob)
            self.sell_prob = float(self.sell_prob)
            self.min_invest = float(self.min_invest)
            self.max_invest = float(self.max_invest)
            self.total_invest = float(self.total_invest)
            if self.buy_price:
                self.buy_price = float(self.buy_price)
            if self.sell_price:
                self.sell_price = float(self.sell_price)
            if self.prev_buy_price:
                self.prev_buy_price = float(self.prev_buy_price)
            if self.prev_sell_price:
                self.prev_sell_price = float(self.prev_sell_price)
            if self.prev_high_price:
                self.prev_high_price = float(self.prev_high_price)
            if self.prev_low_price:
                self.prev_low_price = float(self.prev_low_price)

    def on_timer(self):
        '''
        if data init, update market trades for vline queue generator, vline generator
        '''
        if not self.is_data_inited:
            return

        self.update_market_trade(time_step=1)
        self.update_price_gain_speed_vline(num_vline=3, time_step=1)
        if self.is_slump or self.is_surge:
            self.release_trading_quota(timestep=1)
        else:
            self.release_trading_quota(timestep=10)
        self.update_invest_limit()

        #if self.timer_count % 1 == 0 and self.timer_count > 10:
        #    self.update_market_trade()
        #    self.update_price_gain_speed_vline(num_vline=3)
        if self.timer_count % 1 == 0 and self.timer_count > 10:
            if self.last_trade:
                price = self.last_trade.price
                self.check_price_break(price=price, direction=Direction.LONG)
                self.check_price_break(price=price, direction=Direction.SHORT)
                self.make_decision(price=price)

        if self.timer_count % 10 == 0 and self.timer_count > 10:
            self.update_avg_trade_price()
            self.update_ref_price()
            self.update_high_low_price()

        if self.timer_count % 60 == 0 and self.timer_count > 10:
            print(datetime.datetime.now(tz=MY_TZ))
            self.update_break_count()

        if self.timer_count % 600 == 0 and self.timer_count > 10:
            #self.update_invest_position()
            self.update_invest_limit()

        if self.timer_count % 3600 == 0 and self.timer_count > 10:
            self.cancel_all()

        self.timer_count += 1
        self.update_variable()
        self.put_event()


if __name__ == '__main__':
    pass
