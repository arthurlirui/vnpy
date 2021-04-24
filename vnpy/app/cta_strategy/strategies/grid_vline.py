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
    default_setting = {
        "vt_symbol": "",
        "price": 0.0,
        "step_price": 0.0,
        "step_volume": 0,
        "interval": 10,
        "test": 1000,
    }

    parameters = ['vline_vol', 'total_invest', 'trade_amount', 'global_prob', 'max_break_count']

    variables = ['timer_count', 'upper_break', 'lower_break', 'upper_break_count', 'lower_break_count',
                 'buy_prob', 'sell_prob', 'min_invest', 'max_invest', 'total_invest',
                 'buy_price', 'sell_price', 'vol_select', 'prev_buy_price', 'prev_sell_price', 'trading_quota']

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
        setting
    ):
        """"""
        super(GridVline, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.symbols = ['bch3lusdt']
        self.exchanges = ['HUOBI']

        self.base_currency = 'bch3l'
        self.quote_currency = 'usdt'
        self.symbol = self.base_currency+self.quote_currency

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
        self.timer_count = 0

        # init internal parameters
        self.max_amount = 1000
        self.max_ratio = 1.0
        self.support_min = []
        self.support_max = []
        self.max_num_vline = 100000
        self.max_local_num_extrema = 100
        self.vline_loca_order = 200
        self.theta = 0.01
        self.global_prob = 0.3
        self.buy_prob = 0
        self.sell_prob = 0
        #self.sell(price=11, volume=0.5)
        self.trade_amount = 20

        # init invest position (usdt unit)
        self.total_invest = 400.0
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

        # trading quota
        self.trading_quota = True

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

    def on_order(self, order: OrderData):
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

    def generate_volume(self, price: float, direction: Direction) -> float:
        volume = 0.0
        if direction == Direction.LONG:
            # 1. check balance
            volume = random.uniform(0, 1) * self.trade_amount / price
            avail_volume = self.balance_info.data[self.quote_currency].available
            volume = np.round(np.min([volume, avail_volume / price]), 4)
            # 2. check position
            cur_position = self.balance_info.data[self.base_currency].available*price
            if cur_position > self.max_invest:
                volume = np.round(0, 4)
            # 3. check probability
            if self.sell_prob > self.buy_prob or self.sell_prob > 0.03:
                volume = np.round(0, 4)
        elif direction == Direction.SHORT:
            # 1. check balance
            volume = np.round(random.uniform(0, 1) * self.trade_amount / price, 2)
            avail_volume = self.balance_info.data[self.base_currency].available
            volume = np.round(np.min([volume, avail_volume]), 4)
            # 2. check position
            cur_position = self.balance_info.data[self.base_currency].available*price
            if cur_position < self.min_invest:
                volume = np.round(0, 4)
            # 3. check probability
            if self.buy_prob > self.sell_prob or self.buy_prob > 0.03:
                volume = np.round(0, 4)
        else:
            volume = 0.0
        return volume

    def check_price_break(self, price: float, direction: Direction):
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        min_price = np.min([kl.low_price for kl in kline_1m[-1*self.max_break_count:-1]])
        max_price = np.max([kl.low_price for kl in kline_1m[-1*self.max_break_count:-1]])

        #vol = self.market_params[self.symbol]['vline_vol']
        #vlines = self.vg[self.vt_symbol].vlines[vol]
        #vol_list = self.market_params[self.symbol]['vline_vol_list']
        #vol = vol_list[3]

        self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)

        if direction == Direction.LONG:
            #min_price = np.min([v.low_price for v in vlines[-30:]])
            if price < min_price:
                if 0.5 < self.pos < 1.0:
                    self.lower_break_count = int(1.5 * self.max_break_count)
                elif 0.0 < self.pos < 0:
                    self.lower_break_count = int(1.0 * self.max_break_count)
                else:
                    self.lower_break_count = int(1.0 * self.max_break_count)
                self.lower_break = True
        elif direction == Direction.SHORT:
            #max_price = np.max([v.high_price for v in vlines[-30:]])
            if price > max_price:
                if 0.0 < self.pos < 0.5:
                    self.upper_break_count = int(1.5 * self.max_break_count)
                elif 0.5 < self.pos < 1.0:
                    self.upper_break_count = int(1.0 * self.max_break_count)
                else:
                    self.upper_break_count = int(1.0 * self.max_break_count)
                #self.upper_break_count = self.max_break_count
                self.upper_break = True
        else:
            pass

    def generate_order(self, price: float, volume: float, direction: Direction,
                       w1: float = 1.0, w2: float = 1.0, w3: float = 1.0):
        volume1 = volume * w1
        #volume2 = volume * w2
        #volume3 = volume * w3
        #if volume*price > 5 or volume1*price > 5 or volume2*price > 5 or volume3*price > 5:
        if direction == Direction.LONG:
            if random.uniform(0, 1) < 0.5 or True:
                price = np.round(price * (1 - random.uniform(-1, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.bids.keys())[0]+0.0001, 4)
            if volume1*price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
            # price = np.round(price * (1 - random.uniform(0, 1) * 0.002), 4)
            # if volume2 * price > 5:
            #     self.send_order(direction, price=price, volume=volume2, offset=Offset.NONE)
            # price = np.round(price * (1 - random.uniform(0, 1) * 0.003), 4)
            # if volume3 * price > 5:
            #     self.send_order(direction, price=price, volume=volume3, offset=Offset.NONE)
        elif direction == Direction.SHORT:
            if random.uniform(0, 1) < 0.5 or True:
                price = np.round(price * (1 + random.uniform(-1, 1) * 0.001), 4)
            else:
                price = np.round(list(self.order_book.asks.keys())[0]-0.0001, 4)
            if volume1 * price > 5:
                self.send_order(direction, price=price, volume=volume1, offset=Offset.NONE)
            # price = np.round(price * (1 + random.uniform(0, 1) * 0.002), 4)
            # if volume2 * price > 5:
            #     self.send_order(direction, price=price, volume=volume2, offset=Offset.NONE)
            # price = np.round(price * (1 + random.uniform(0, 1) * 0.003), 4)
            # if volume3 * price > 5:
            #     self.send_order(direction, price=price, volume=volume3, offset=Offset.NONE)
        else:
            return

    def make_decision(self, price: float):
        '''
        1. check balance, position, price
        2. historical trade, previous high, low
        3. profit
        4. price break
        '''
        if random.uniform(0, 1) < self.buy_prob:
            direction = Direction.LONG
            # 1. calc volume
            volume = self.generate_volume(price=price, direction=direction)
            # 2. price break
            #self.check_price_break(price=price, direction=direction)
            print('In BUY:', volume)
            if not self.lower_break and self.trading_quota:
                # 3. send multiple orders
                self.generate_order(price=price, volume=volume, direction=direction)
                print('Sending buy order:', price)
        if random.uniform(0, 1) < self.sell_prob:
            direction = Direction.SHORT
            # 1. calc volume
            volume = self.generate_volume(price=price, direction=direction)
            # 2. price break
            #self.check_price_break(price=price, direction=direction)
            print('In sell:', volume)
            if not self.upper_break:
                # 3. send multiple orders
                if self.prev_buy_price:
                    if self.prev_buy_price < 0.98*price:
                        self.generate_order(price=price, volume=volume, direction=direction)
                        print('Sending buy order:', price)
                else:
                    self.generate_order(price=price, volume=volume, direction=direction)
                    print('Sending buy order:', price)

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
        # bi = np.argmin(np.abs(np.array(self.buy_price) - price))
        # buy_pricei = self.buy_price[bi]
        # si = np.argmin(np.abs(np.array(self.sell_price) - price))
        # sell_pricei = self.sell_price[si]
        self.buy_prob = self.calc_pro_buy(price=price, price_ref=self.buy_price, theta=self.theta,
                                          global_prob=self.global_prob)
        self.sell_prob = self.calc_pro_sell(price=price, price_ref=self.sell_price, theta=self.theta,
                                            global_prob=self.global_prob)

        # if all(self.buy_price) and all(self.sell_price) and price:
        #     bi = np.argmin(np.abs(np.array(self.buy_price)-price))
        #     buy_pricei = self.buy_price[bi]
        #     si = np.argmin(np.abs(np.array(self.sell_price)-price))
        #     sell_pricei = self.sell_price[si]
        #     self.buy_prob = self.calc_pro_buy(price=price, price_ref=buy_pricei, theta=self.theta, global_prob=self.global_prob)
        #     self.sell_prob = self.calc_pro_sell(price=price, price_ref=sell_pricei, theta=self.theta, global_prob=self.global_prob)

    def update_invest_position(self):
        '''update invest position'''
        price = self.last_trade.price
        if not price:
            return
        self.update_trade_prob(price=price)
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        '''
        for i, vol in enumerate(vol_list):
            pos = self.vqg[self.vt_symbol].vq[vol].less_vol(price=price)
            if 0.00 < pos < 0.05:
                self.max_invest = np.round(min((0.2 + 0.3 * i), 1.0) * self.total_invest, 4)
            if 0.95 < pos < 1.0:
                self.min_invest = np.round(max((0.4 - 0.2 * i), 0.0) * self.total_invest, 4)
        '''
        '''
        vol = vol_list[3]
        pos = self.vqg[self.vt_symbol].vq[vol].less_vol(price=price)
        min_pos = 0.3
        max_pos = 0.0
        default_pos = 0.25
        if pos < min_pos:
            self.max_invest = np.round((1.0-pos/min_pos+default_pos)*self.total_invest)
        else:
            self.max_invest = default_pos*self.total_invest
        if pos > max_pos:
            self.min_invest = 0
        '''
        vol = vol_list[3]
        pos = self.vqg[self.vt_symbol].vq[vol].less_vol(price=price)
        pos_floor = np.floor(pos*10)/10
        self.max_invest = np.round((1.0 - pos_floor) * self.total_invest)
        self.min_invest = 0
        #print(f'MaxInv:{self.max_invest} MinInv:{self.min_invest}')

    def update_avg_trade_price(self):
        long_price = 0
        long_pos = 0
        short_price = 0
        short_pos = 0

        # self.balance_info.data[self.base_currency]
        for i, at in enumerate(reversed(self.account_trades)):
            if at.datetime > datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(hours=6):
                if at.direction == Direction.LONG and long_pos < self.balance_info.data[self.base_currency]:
                    long_price += at.price*at.volume
                    long_pos += at.volume
                if at.direction == Direction.SHORT:
                    short_price += at.price*at.volume
                    short_pos += at.volume

        if long_pos > 0:
            long_price = float(np.round(long_price/long_pos, 4))
            self.prev_buy_price = long_price
        if short_pos > 0:
            short_price = float(np.round(short_price/short_pos, 4))
            self.prev_sell_price = short_price

    # def update_strategy_params(self):
    #     self.update_ref_price()
    #     self.update_invest_position()

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
            for orderid in self.orders:
                order = self.orders[orderid]
                if order.datetime < datetime.datetime.now(tz=MY_TZ) - datetime.timedelta(minutes=10):
                    self.cancel_order(order.vt_orderid)
            self.trading_quota = True

        if self.timer_count % 3600 == 0 and self.timer_count > 10:
            self.cancel_all()

        self.timer_count += 1
        #if self.timer_count % 10 == 0 and self.timer_count > 10:
        self.update_variable()
        self.put_event()

