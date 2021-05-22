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


class ChaseBear(CtaTemplate):
    """"""
    display_name = "Chase Bear - 熊市追涨算法"
    author = "Arthur"
    default_setting = {'base_currency': 'bch3s',
                       'quote_currency': 'usdt',
                       'exchange': 'HUOBI',
                       'vline_vol': 100,
                       'total_invest': 500,
                       'trade_amount': 40,
                       'global_prob': 0.5,
                       'max_break_count': 4}
    base_currency = 'bch3s'
    quote_currency = 'usdt'
    exchange = 'HUOBI'
    vline_vol = 100
    total_invest = 500
    trade_amount = 40
    global_prob = 0.5
    max_break_count = 4
    parameters = ['base_currency', 'quote_currency', 'exchange', 'vline_vol',
                  'total_invest', 'trade_amount', 'global_prob', 'max_break_count']

    variables = ['timer_count', 'cur_invest', 'min_invest', 'max_invest', 'total_invest',
                 'vol1m', 'up_line', 'mean_vol', 'buy_price', 'sell_price', 'vol_select', 'trading_quota']

    bch3l_vol_list = [1000, 10000, 100000, 1000000]
    default_vol_list = [1000, 10000, 100000, 1000000]
    market_params = {'bch3susdt': {'vline_vol': 100, 'vline_vol_list': bch3l_vol_list, 'bin_size': 0.000001},
                     'btc3susdt': {'vline_vol': 100, 'vline_vol_list': default_vol_list, 'bin_size': 0.0001}}

    def __init__(
        self,
        cta_engine,
        strategy_name,
        vt_symbol,
        setting=default_setting
    ):
        """"""
        super(ChaseBear, self).__init__(cta_engine, strategy_name, vt_symbol, setting=setting)
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

        self.vol1m = 0
        self.up_line = 0
        self.mean_vol = 0

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
            #self.load_bar(days=2, interval=Interval.MINUTE_5, callback=self.on_kline)
            #self.load_bar(days=2, interval=Interval.MINUTE_15, callback=self.on_kline)
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
                self.vg[vt_symbol].init_by_trade(trade=trade)
                self.vqg[vt_symbol].init_by_trade(trade=trade)

    def check_vline_pos(self, price):
        vol_pos = {}
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

    def on_order_book(self, order_book: OrderBookData):
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
        #print(trade)
        self.trade_buf.append(trade)
        self.last_trade = trade
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

    def on_kline(self, bar: BarData):
        self.kline_buf.append(bar)
        if bar.interval == Interval.MINUTE:
            self.vol1m = bar.volume
        #print(len(self.kline_buf), bar)

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
                avail_volume = self.get_current_position(quote=True, available=True)
                volume = np.round(np.min([volume, avail_volume / price]), 4)
            # 2. check position
            if check_position:
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position > self.max_invest:
                    volume = np.round(volume * 0.0, 4)
        elif direction == Direction.SHORT:
            # 1. check balance
            if check_balance:
                volume = np.round(random.uniform(0, 1) * self.trade_amount / price, 2)
                volume = volume * ratio
                avail_volume = self.get_current_position(base=True, available=True)
                if volume > 0.9*avail_volume:
                    volume = np.round(avail_volume, 4)
                else:
                    volume = np.round(np.min([volume, avail_volume]), 4)
            # 2. check position
            if check_position:
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position < self.min_invest:
                    volume = np.round(volume * 0.5, 4)
        else:
            volume = 0.0
        return volume

    def release_trading_quota(self, timestep: int = 10):
        if self.timer_count % timestep == 0:
            self.trading_quota = True

    def generate_order(self, price: float, volume: float, direction: Direction, w: float = 1.0):
        volume1 = float(np.round(volume * w, 2))
        if direction == Direction.LONG:
            price = np.round(price * (1 + random.uniform(0, 1) * 0.01), 8)
            if volume1*price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        elif direction == Direction.SHORT:
            price = np.round(price * (1 - random.uniform(0, 1) * 0.01), 8)
            if volume1 * price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
        else:
            return

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

    def stop_loss(self, price, stop_loss_rate: float = 0.90):
        timedelta_long = datetime.timedelta(minutes=360)
        cur_vol = self.get_current_position(base=True, volume=True)
        long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG,
                                                                         vol=cur_vol,
                                                                         timedelta=timedelta_long)

        if long_price and price < stop_loss_rate * long_price:
            # check 1m kline to determine
            is_stop_loss = self.need_stop_loss(stop_loss_rate=stop_loss_rate)
            if is_stop_loss:
                #self.write_log(f'stop_loss {datetime.datetime.now(tz=MY_TZ)}')
                direction = Direction.SHORT
                # if stop loss, do care position, prob, quota, price, break, risk
                volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
                self.generate_order(price=price, volume=volume, direction=direction)
                #self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def take_profit(self, price: float):
        if self.timer_count % 60 != 0:
            return
        # 1. check holding position time
        tp_ratio_0_75 = 1.1
        tp_ratio_0_5 = 1.5
        tp_ratio_0_0 = 2.0
        tp_ratio_default = 1.05
        cur_vol = self.get_current_position(base=True, volume=True)
        timedelta = datetime.timedelta(minutes=360)
        long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG,
                                                                         vol=cur_vol,
                                                                         timedelta=timedelta)

        timedelta_short = datetime.timedelta(minutes=10)
        short_price, short_pos, short_timedelta = self.calc_avg_trade_price(direction=Direction.SHORT, timedelta=timedelta_short)
        if long_timedelta > datetime.timedelta(minutes=30):
            #self.write_log(f'take_profit {datetime.datetime.now(tz=MY_TZ)}')
            direction = Direction.SHORT
            if long_price and price > tp_ratio_default * long_price:
                volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=False)
                self.generate_order(price=price, volume=volume, direction=direction)
        elif long_timedelta > datetime.timedelta(minutes=10):
            cur_position = price * self.get_current_position(base=True, volume=True)
            if cur_position > 0.75 * self.total_invest:
                if long_price and price > tp_ratio_0_75 * long_price:
                    direction = Direction.SHORT
                    volume = self.generate_volume(price=price, direction=direction, check_balance=True,
                                                  check_position=False)
                    self.generate_order(price=price, volume=volume, direction=direction)
            elif 0.5 * self.total_invest < cur_position < 0.75 * self.total_invest:
                if long_price and price > tp_ratio_0_75 * long_price and price < tp_ratio_0_5 * long_price:
                    direction = Direction.SHORT
                    volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
                    self.generate_order(price=price, volume=volume, direction=direction)
            elif 0.0 * self.max_invest < cur_position < 0.5 * self.total_invest:
                if long_price and price > tp_ratio_0_0 * long_price:
                    #self.write_log(f'take_profit {datetime.datetime.now(tz=MY_TZ)}')
                    direction = Direction.SHORT
                    volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
                    self.generate_order(price=price, volume=volume, direction=direction)
            else:
                pass
        elif long_timedelta > datetime.timedelta(minutes=120):
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
            self.generate_order(price=price, volume=volume, direction=direction)
        else:
            pass

    def chase_up(self, price: float, vol_ratio: float = 5.0):
        '''
        1. trading volume change: low to high
        2. previous price variation
        3. previous high low price bound
        '''
        # 1. check current price with previous kline: is_slip or is_climb
        # 2. check trading volume
        # 3. check holding position

        # 1. check price break
        bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        num_kline = len(bars1m)
        bars1m_data = bars1m[-180:-60]
        if len(bars1m) < 100:
            print(len(bars1m), len(bars1m_data))
            return
        low_price_sorted = np.sort(np.array([bar.low_price for bar in bars1m_data]))
        high_price_sorted = np.sort(np.array([bar.high_price for bar in bars1m_data]))
        up_line = np.max(high_price_sorted[10:-10])
        self.up_line = up_line
        down_line = np.min(low_price_sorted[10:-10])

        vol_sorted = np.sort(np.array([bar.volume for bar in bars1m_data]))
        mean_vol = np.median(vol_sorted)
        self.mean_vol = mean_vol
        cur_vol = bars1m[-1].volume

        #long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG,
        #                                                                 timedelta=datetime.timedelta(minutes=10))
        short_price, short_pos, short_timedelta = self.calc_avg_trade_price(direction=Direction.SHORT,
                                                                            timedelta=datetime.timedelta(minutes=10))

        is_price_break_up = False
        is_volume_increase = False
        is_recent_sell = False
        is_chase_up = False
        if price > up_line:
            is_price_break_up = True
        if cur_vol > vol_ratio * mean_vol:
            is_volume_increase = True
        if short_pos > 0:
            is_recent_sell = True
        if is_price_break_up and is_volume_increase and not is_recent_sell:
            is_chase_up = True
        print(up_line, cur_vol, vol_ratio*mean_vol, short_timedelta)

        if is_chase_up:
            cur_position = price * self.get_current_position(base=True, volume=True)
            #cur_position = self.balance_info.data[self.base_currency].available * price
            if cur_position < self.max_invest:
                #self.write_log(f'Chasing up {datetime.datetime.now(tz=MY_TZ)}')
                direction = Direction.LONG
                volume = self.generate_volume(price=price, direction=direction,
                                              check_position=True)
                self.generate_order(price=price, volume=volume, direction=direction)
                #self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

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
            #self.write_log(f'Killing down {datetime.datetime.now(tz=MY_TZ)}')
            # 1. price is in low position: check bars
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction,
                                          check_position=True)
            self.generate_order(price=price, volume=volume, direction=direction)
            #self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def make_decision(self, price: float):
        ''''''
        # 2. chasing up
        if True:
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
        if True:
            return
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
            #self.upper_break_count = int(self.upper_break_count)
            #self.lower_break_count = int(self.lower_break_count)
            #self.buy_prob = float(self.buy_prob)
            #self.sell_prob = float(self.sell_prob)
            self.min_invest = float(self.min_invest)
            self.cur_invest = float(self.cur_invest)
            self.max_invest = float(self.max_invest)
            self.total_invest = float(self.total_invest)
            self.vol1m = float(self.vol1m)
            self.mean_vol = float(self.mean_vol)
            self.up_line = float(self.up_line)
            #if self.buy_price:
            #    self.buy_price = float(self.buy_price)
            #if self.sell_price:
            #    self.sell_price = float(self.sell_price)
            #if self.prev_buy_price:
            #    self.prev_buy_price = float(self.prev_buy_price)
            #if self.prev_sell_price:
            #    self.prev_sell_price = float(self.prev_sell_price)
            #if self.prev_high_price:
            #    self.prev_high_price = float(self.prev_high_price)
            #if self.prev_low_price:
            #    self.prev_low_price = float(self.prev_low_price)

    def on_timer(self):
        '''
        if data init, update market trades for vline queue generator, vline generator
        '''
        #if not self.is_data_inited:
        #    return

        self.update_market_trade(time_step=1)
        self.release_trading_quota(timestep=10)
        self.update_invest_limit(update_time_period=datetime.timedelta(minutes=1))
        if self.timer_count % 1 == 0 and self.timer_count > 10:
            if self.last_trade:
                price = self.last_trade.price
                self.make_decision(price=price)

        if self.timer_count % 10 == 0 and self.timer_count > 10:
            self.update_avg_trade_price()

        if self.timer_count % 60 == 0 and self.timer_count > 10:
            print(datetime.datetime.now(tz=MY_TZ))

        if self.timer_count % 600 == 0 and self.timer_count > 10:
            self.update_invest_limit()

        if self.timer_count % 3600 == 0 and self.timer_count > 10:
            self.cancel_all()

        self.timer_count += 1
        self.update_variable()
        self.put_event()
