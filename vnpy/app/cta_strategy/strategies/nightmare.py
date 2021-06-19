from vnpy.trader.constant import Direction
from vnpy.trader.engine import BaseEngine
from vnpy.app.algo_trading import AlgoTemplate
from vnpy.trader.utility import VlineGenerator, MarketEventGenerator, VlineQueueGenerator, BarQueueGenerator
from typing import Any, Callable
from scipy.signal import argrelextrema, argrelmin, argrelmax
import numpy as np
import random, math, datetime, os, time
import matplotlib.pyplot as plt
#from scipy.misc import electrocardiogram
from scipy.signal import find_peaks
from pprint import pprint
from termcolor import colored
#from vnpy.trader.calc import VlineFeature, BarFeature
from vnpy.trader.utility import load_json, save_json

from vnpy.trader.object import (
    SubscribeRequest,
    TradeData,
    OrderData,
    TickData,
    VlineData,
    BarData,
    PositionData,
    MarketEventData,
    AccountData,
    BalanceData,
    OrderBookData,
    HistoryRequest
)

from vnpy.trader.constant import (
    Direction,
    OrderType,
    Interval,
    Exchange,
    Offset,
    Status,
    MarketEvent
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

from vnpy.trader.calc import VlineFeature, BarFeature

import pytz
SAUDI_TZ = pytz.timezone("Asia/Riyadh")
MY_TZ = None


class Nightmare(CtaTemplate):
    """"""
    display_name = "Nightmare"
    author = "Arthur"
    default_setting = {'base_currency': 'btc', 'quote_currency': 'usdt',
                       'base_short_currency': 'btc3s', 'base_long_currency': 'btc3l',
                       'exchange': 'HUOBI', 'vline_vol': 1, 'total_invest': 500,
                       'trade_amount': 40, 'global_prob': 0.5, 'max_break_count': 4}
    base_currency = 'btc'
    quote_currency = 'usdt'
    base_short_currency = 'btc3s'
    base_long_currency = 'btc3l'
    exchange = 'HUOBI'
    vline_vol = 1
    total_invest = 500
    trade_amount = 20
    global_prob = 0.5
    max_break_count = 4
    has_short_liquidation = False
    has_long_liquidation = False
    parameters = ['base_currency', 'quote_currency', 'exchange', 'vline_vol', 'total_invest',
                  'spread_15s_thresh', 'spread_1m_thresh', 'spread_2m_thresh',
                  'spread_3m_thresh', 'spread_5m_thresh',
                  'vol_1m_thresh', 'vol_2m_thresh', 'vol_3m_thresh', 'vol_5m_thresh'
                  #'sv_0_3_thresh', 'sv_3_20_thresh',
                  #'sv_buy_15s_thresh', 'sv_sell_15s_thresh',
                  #'sv_buy_60s_thresh', 'sv_sell_60s_thresh',
                  #'sv_buy_120s_thresh', 'sv_buy_120s_thresh',
                  #'sv_buy_180s_thresh', 'sv_buy_180s_thresh',
                  #'trade_amount', 'global_prob', 'max_break_count',
                  #'trade_gain_thresh', 'trade_speed_thresh',
                  #'sv_t3', 'sv_t5', 'sv_t10', 'sv_t20', 's_t3', 's_t5', 's_t10', 's_t20'
                  ]

    variables = ['timer_count',
                 #'upper_break', 'lower_break', 'upper_break_count', 'lower_break_count',
                 'min_invest', 'cur_invest', 'max_invest', 'total_invest',
                 'vol_select', 'buy_speed', 'sell_speed', 'total_speed',
                 #'trade_speed', 'trade_gain', 'trading_quota',
                 'median_vol', 'median_vol_100', 'median_vol_1000',
                 #'is_price_going_down', 'is_price_going_up', 'is_high_vol', 'is_high_trade_speed',
                 #'sv_20_0', 'sv_10_0', 'sv_5_0', 'sv_3_0',
                 #'spread_20_0', 'spread_10_0', 'spread_5_0', 'spread_3_0',
                 'is_gain', 'is_slip', 'is_surge', 'is_slump', 'is_top_divergence', 'is_bottom_divergence',
                 'has_short_liquidation', 'has_long_liquidation', 'stop_loss_price', 'take_profit_price']

    #usdt_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]
    #bch3l_vol_list = [1000, 10000, 100000, 1000000]
    btc_vol_list = [10, 40, 160, 640]
    btc3s_vol_list = [5000000, 20000000, 80000000, 320000000]
    btc3l_vol_list = [200, 800, 3200, 12800]
    market_params = {
        'btcusdt': {'vline_vol': 1, 'vline_vol_list': btc_vol_list, 'bin_size': 1},
        'btc3susdt': {'vline_vol': 5000000, 'vline_vol_list': btc3s_vol_list, 'bin_size': 0.0001},
        'btc3lusdt': {'vline_vol': 100, 'vline_vol_list': btc3l_vol_list, 'bin_size': 0.1}
    }

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting=default_setting):
        """"""
        super(Nightmare, self).__init__(cta_engine, strategy_name, vt_symbol, setting=setting)
        # exchange and trading pair
        self.symbol, self.exchange = vt_symbol.split('.')
        self.exchanges = []
        self.exchanges.append(self.exchange)
        self.symbol = self.base_currency+self.quote_currency
        self.symbols = []
        self.symbols.append(self.symbol)

        if self.symbol == 'btcusdt':
            # add 3x short pair
            #self.symbols.append(self.base_short_currency+self.quote_currency)
            # add 3x long pair
            #self.symbols.append(self.base_long_currency+self.quote_currency)
            pass

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

        # subscribe other symbol
        #symbol = 'btc3susdt'
        # for symbol in self.symbols:
        #     if self.exchange == 'HUOBI':
        #         req = SubscribeRequest(symbol=symbol, exchange=Exchange.HUOBI)
        #         self.cta_engine.main_engine.subscribe(req, 'HUOBI')
        #         self.write_log(f"行情订阅{symbol}")

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # init buffer for saving trades and klines
        self.his_trade_buf = {}
        self.his_kline_buf = {}
        self.last_tick = None
        self.last_trade = None

        # init generator for kline, vline, market event
        self.init_generator()
        self.init_algo_param()
        self.init_flag()
        self.init_thresh()
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

    def init_generator(self):
        # init vline queue generator
        self.vqg = {}
        self.init_vline_queue_generator()

        # init vline generator
        self.vg = {}
        self.init_vline_generator()
        self.kqg = BarQueueGenerator()

        # market event generator
        self.meg = MarketEventGenerator(on_event=self.on_market_event)

    def init_algo_param(self):
        # init internal parameters
        self.timer_count = 0
        self.test_count = 0

        # init buy sell price for vline
        self.theta = 0.01
        self.buy_prob = 0
        self.sell_prob = 0

        # init invest position (usdt unit)
        self.min_invest = 0
        self.max_invest = 100.0
        self.cur_invest = 0
        self.total_invest = 1500.0

        # init price break count
        self.max_break_count = 4
        self.upper_break_count = self.max_break_count
        self.lower_break_count = self.max_break_count
        self.upper_break = True
        self.lower_break = True

        # trading speed
        self.total_speed = None
        self.buy_speed = None
        self.sell_speed = None

    def init_flag(self):
        # market status flags
        self.is_data_inited = False

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
        self.is_bottom_divergence = False
        self.is_top_divergence = False

        # flag for first time initial parameters
        self.first_time = True
        self.has_slow_suck_quota = True
        self.has_slow_sell_quota = True

        # trading quota
        self.trading_quota = True

        # liquidation signal
        self.has_short_liquidation = False
        self.has_long_liquidation = False
        self.short_liquidation_ts = None
        self.long_liquidation_ts = None

        self.is_price_going_down = False
        self.is_price_going_up = False
        self.is_high_vol = False
        self.is_high_trade_speed = False

    def init_thresh(self):
        # spread thresh
        self.base_spread_thresh = 0.01
        self.spread_15s_thresh = 0.025 * self.base_spread_thresh
        self.spread_1m_thresh = 0.1 * self.base_spread_thresh
        self.spread_2m_thresh = 0.2 * self.base_spread_thresh
        self.spread_3m_thresh = 0.3 * self.base_spread_thresh
        self.spread_5m_thresh = 0.5 * self.base_spread_thresh

        # volume thresh
        self.base_volume_thresh = 30
        self.vol_1m_thresh = 1 * self.base_volume_thresh
        self.vol_2m_thresh = 2 * self.base_volume_thresh
        self.vol_3m_thresh = 3 * self.base_volume_thresh
        self.vol_5m_thresh = 5 * self.base_volume_thresh

        # spread vol thresh
        self.base_spread_vol_thresh = 0.0001
        self.sv_1m_thresh = 1 * self.base_spread_vol_thresh
        self.sv_2m_thresh = 1 * self.base_spread_vol_thresh
        self.sv_3m_thresh = 1 * self.base_spread_vol_thresh
        self.sv_5m_thresh = 1 * self.base_spread_vol_thresh

        # thresh for volume
        self.vol_select = self.market_params[self.symbol]['vline_vol_list'][0]
        self.median_vol = None
        self.median_vol_100 = None
        self.median_vol_1000 = None

        # thresh for trading speed
        self.buy_price = None
        self.sell_price = None

        # sending count
        self.sending_count = 0
        self.max_sending_count = 4

        # buying or selling volume
        self.short_term_trading_vol = 0.1 * self.total_invest
        self.cur_buy_vol = 0
        self.cur_sell_vol = 0

        # position update time
        self.update_invest_limit_time = None

        # stop loss price
        self.stop_loss_price = None
        self.take_profit_price = None

        # trading speed
        self.trade_speed = -1
        self.trade_gain = -1
        self.trade_gain_thresh = 50
        self.trade_speed_thresh = 10

        # spread vol thresh: buy, sell, total
        self.sv_3_0 = 0
        self.sv_5_0 = 0
        self.sv_10_0 = 0
        self.sv_20_0 = 0
        # self.spread_3_0 = 0
        # self.spread_5_0 = 0
        # self.spread_10_0 = 0
        # self.spread_20_0 = 0

        thresh = 0.0001
        self.sv_buy_15s_thresh = 1.5*thresh
        self.sv_sell_15s_thresh = 1.5*thresh
        self.sv_buy_60s_thresh = thresh
        self.sv_sell_60s_thresh = thresh
        self.sv_buy_120s_thresh = thresh
        self.sv_sell_120s_thresh = thresh
        self.sv_buy_180s_thresh = thresh
        self.sv_sell_180s_thresh = thresh

        self.sv_3_20_thresh = thresh
        self.sv_0_3_thresh = thresh

        self.sv_t3 = 0.003
        self.sv_t5 = 0.006
        self.sv_t10 = 0.006
        self.sv_t20 = 0.01
        self.s_t3 = 0.003
        self.s_t5 = 0.006
        self.s_t10 = 0.006
        self.s_t20 = 0.01

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
        #print(self.last_tick.ask_price_1, self.last_tick.ask_price_2, self.last_tick.ask_price_3)
        #print(self.last_tick.bid_price_1, self.last_tick.bid_price_2, self.last_tick.bid_price_3)

    def on_market_event(self, med: MarketEventData):
        print(med)

    def on_order_book(self, order_book: OrderBookData):
        #print(order_book)
        if False:
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
        if False:
            if trade.direction == Direction.LONG:
                print(colored(trade, color='green'))
            else:
                print(colored(trade, color='red'))

        #self.check_price_break(price=price, direction=Direction.LONG, use_vline=True)
        #self.check_price_break(price=price, direction=Direction.SHORT, use_vline=True)

        #self.update_trade_prob(price=price)
        #self.make_decision(price=trade.price)
        #self.put_event()

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
        # update vline-based feature
        #self.update_vline_feature()

        # update price break signal
        if True:
            if vline.buy_volume > vline.sell_volume:
                print(colored(vline, color='green'))
            else:
                print(colored(vline, color='red'))

        #self.update_vline_feature()
        #res_spread_vol = self.update_spread_vol_vline(start_second=0, seconds=[15, 60, 120, 180, 600, 1200])
        #print(res_spread_vol)
        #vol = self.market_params[self.symbol]['vline_vol']
        #vlines = self.vg[self.vt_symbol].vlines[vol]
        #print(vol, vline)
        #self.vg[self.vt_symbol].update_vline(vline=vline, vol=vol)

    def on_kline(self, bar: BarData):
        self.kline_buf.append(bar)

        #self.update_volume_feature()

    def on_trade(self, trade: TradeData):
        if len(self.account_trades) > 0:
            print(trade, self.account_trades[-1])
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
        print('OnOrder', order)
        if order.status == Status.NOTTRADED or order.status == Status.SUBMITTING:
            self.orders[order.vt_orderid] = order
            print(len(self.orders))
        if order.status == Status.PARTTRADED:
            self.orders[order.vt_orderid] = order
            print(len(self.orders))
        if order.status == Status.ALLTRADED:
            if order.vt_orderid in self.orders:
                self.orders.pop(order.vt_orderid)
            print(len(self.orders))
        if order.status == Status.CANCELLED:
            if order.vt_orderid in self.orders:
                self.orders.pop(order.vt_orderid)

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
                        check_balance=True, check_position=True, precision=6) -> float:
        volume = 0.0
        if direction == Direction.LONG:
            # 1. check balance
            volume = random.uniform(0, 1) * self.trade_amount / price
            volume = volume * ratio
            if check_balance:
                #avail_volume = self.balance_info.data[self.quote_currency].available
                avail_volume = self.get_current_position(quote=True, available=True)
                volume = np.round(np.min([volume, avail_volume / price]), precision)
                #print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                #cur_position = self.balance_info.data[self.base_currency].available*price
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position > self.max_invest:
                    volume = np.round(volume * 0.0, precision)
                    #print(f'check_position {direction.value} {volume}')
        elif direction == Direction.SHORT:
            # 1. check balance
            if check_balance:
                volume = np.round(random.uniform(0, 1) * self.trade_amount / price, precision)
                volume = volume * ratio
                #avail_volume = self.balance_info.data[self.base_currency].available
                avail_volume = self.get_current_position(base=True, available=True)
                if volume > 0.9*avail_volume:
                    volume = np.round(avail_volume, precision)
                else:
                    volume = np.round(np.min([volume, avail_volume]), precision)
                #print(f'check_balance {direction.value} {volume}')
            # 2. check position
            if check_position:
                #cur_position = self.balance_info.data[self.base_currency].available*price
                cur_position = self.get_current_position(base=True, available=True)*price
                if cur_position < self.min_invest:
                    volume = np.round(volume * 0.5, precision)
                #print(f'check_position {direction.value} {volume}')
        else:
            volume = 0.0
        return volume

    def calc_market_event_feature(self):
        pass

    def calc_short_liquidation(self):
        pass

    def calc_long_liquidation(self):
        pass

    def check_probability(self, direction: Direction):
        ratio_prob = 0.0
        if direction == Direction.LONG:
            if self.buy_prob > self.sell_prob and self.sell_prob < 0.03:
                ratio_prob = 1.0
        elif direction == Direction.SHORT:
            if self.sell_prob > self.buy_prob and self.buy_prob < 0.03:
                ratio_prob = 1.0
        return ratio_prob

    # def check_lower_break(self):
    #     ratio = 0.0
    #     if self.lower_break:
    #         ratio = 1.0
    #     return ratio
    #
    # def check_upper_break(self):
    #     ratio = 0.0
    #     if self.upper_break:
    #         ratio = 1.0
    #     return ratio

    def check_quota(self):
        ratio = 0.0
        if self.trading_quota:
            ratio = 1.0
        return ratio

    # def check_fall_down(self, price: float):
    #     td30m = datetime.timedelta(minutes=30)
    #     prev_sell_price, prev_sell_pos, prev_sell_timedelta = self.calc_avg_trade_price(direction=Direction.SHORT, timedelta=td30m)
    #     ratio_fall_down = 0.0
    #     if prev_sell_pos > 0 and price > 0.98 * prev_sell_price:
    #         ratio_fall_down = min(max((0.98 - price / prev_sell_price) * 100 * 0.1, 0), 4)
    #     ratio = ratio_fall_down
    #     return ratio
    #
    # def check_price_break_vline(self, price: float, direction: Direction, num_vline: int = 10):
    #     if not self.is_data_inited:
    #         return
    #     # detect vline
    #     vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
    #     if len(vlines) < num_vline:
    #         return
    #     min_price = np.min([vl.low_price for vl in vlines[-1 * num_vline:]])
    #     max_price = np.max([vl.high_price for vl in vlines[-1 * num_vline:]])
    #     self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)
    #     if direction == Direction.LONG:
    #         if price <= min_price:
    #             self.lower_break_count = int(1.0 * self.max_break_count)
    #             self.lower_break = True
    #     elif direction == Direction.SHORT:
    #         if price >= max_price:
    #             self.upper_break_count = int(1.0 * self.max_break_count)
    #             self.upper_break = True
    #     else:
    #         pass

    # def check_price_break_kline(self, price: float, direction: Direction, num_kline: int = 20):
    #     if not self.is_data_inited:
    #         return
    #     # detect kline
    #     kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     if len(kline_1m) < num_kline:
    #         return
    #
    #     min_price = np.min([kl.low_price for kl in kline_1m[-1*num_kline:]])
    #     max_price = np.max([kl.high_price for kl in kline_1m[-1*num_kline:]])
    #     self.pos = self.vqg[self.vt_symbol].vq[self.vol_select].less_vol(price=price)
    #
    #     if direction == Direction.LONG:
    #         if price <= min_price:
    #             self.lower_break_count = int(1.0 * self.max_break_count)
    #             self.lower_break = True
    #     elif direction == Direction.SHORT:
    #         if price >= max_price:
    #             self.upper_break_count = int(1.0 * self.max_break_count)
    #             self.upper_break = True
    #     else:
    #         pass

    # def check_price_break(self, price: float, direction: Direction,
    #                       use_vline: bool = True, use_kline: bool = True,
    #                       num_kline: int = 10,
    #                       num_vline: int = 10):
    #     if not self.is_data_inited:
    #         return
    #     # detect kline
    #     if use_vline:
    #         self.check_price_break_vline(price=price, direction=direction, num_vline=num_vline)
    #     if use_kline:
    #         self.check_price_break_kline(price=price, direction=direction, num_kline=num_kline)
    #
    # def check_min_max_price(self, price: float, direction: Direction):
    #     '''check min max price in previous time duration'''
    #     bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     bars1m_data = bars1m[-360:]
    #     min_price = min([bar.low_price for bar in bars1m_data])
    #     max_price = max([bar.high_price for bar in bars1m_data])
    #     ratio = 0.0
    #     if direction == Direction.LONG:
    #         if 0.90 * max_price < price < 0.95 * max_price:
    #             ratio = 0.5
    #         elif 0.85 * max_price < price < 0.90 * max_price:
    #             ratio = 1.0
    #         elif 0.80 * max_price < price < 0.85 * max_price:
    #             ratio = 1.5
    #         elif price < 0.80 * max_price:
    #             ratio = 2.0
    #         else:
    #             ratio = 0.0
    #     elif direction == Direction.SHORT:
    #         if 1.05 * min_price < price < 1.10 * min_price:
    #             ratio = 0.5
    #         elif 1.10 * min_price < price < 1.15 * min_price:
    #             ratio = 1.0
    #         elif 1.15 * min_price < price < 1.20 * min_price:
    #             ratio = 1.5
    #         elif price > 1.20 * min_price:
    #             ratio = 2.0
    #         else:
    #             ratio = 0.0
    #     return ratio

    # def check_prev_high_low_price(self, price: float,
    #                               direction: Direction,
    #                               timedelta: datetime.timedelta = datetime.timedelta(minutes=30)):
    #     '''check previous high and low price'''
    #     ratio_base = 0.2
    #     ratio_high = 0.0
    #     ratio_low = 0.0
    #     ratio = 1.0
    #     datetime_now = datetime.datetime.now(tz=MY_TZ)
    #     if direction == Direction.LONG:
    #         if self.prev_high_price and self.prev_high_time and datetime_now > self.prev_high_time + timedelta:
    #             ratio_high = min(max((0.95-price/self.prev_high_price)*100*ratio_base, 0), 4)
    #             ratio_high = float(np.round(ratio_high, 4))
    #         if self.prev_low_price:
    #             ratio_low = min(max((1.01-price/self.prev_low_price)*100*ratio_base, 0), 4)
    #             ratio_low = float(np.round(ratio_low, 4))
    #         ratio = max(ratio_low, ratio_high)
    #     elif direction == Direction.SHORT:
    #         if self.prev_low_price and self.prev_low_time and datetime_now > self.prev_low_time + timedelta:
    #             ratio_low = min(max((price/self.prev_low_price-1.05)*100*ratio_base, 0), 4)
    #             ratio_low = float(np.round(ratio_low, 4))
    #         if self.prev_high_price:
    #             ratio_high = min(max((price/self.prev_high_price-0.99)*100*ratio_base, 0), 4)
    #             ratio_high = float(np.round(ratio_high, 4))
    #         ratio = max(ratio_high, ratio_low)
    #     return ratio

    # def check_prev_buy_sell_price(self, price: float,
    #                               direction: Direction,
    #                               timedelta: datetime.timedelta = datetime.timedelta(minutes=10)):
    #     '''check previous buy and sell price'''
    #     ratio = 1.0
    #     datetime_now = datetime.datetime.now(tz=MY_TZ)
    #     ratio_buy = 1.0
    #     ratio_sell = 1.0
    #     if direction == Direction.LONG:
    #         if self.prev_buy_price and self.prev_buy_time and datetime_now < self.prev_buy_time + timedelta:
    #             if 0.98 * self.prev_buy_price < price < 0.99 * self.prev_buy_price:
    #                 ratio_buy = 0.5
    #             elif 0.95 * self.prev_buy_price < price < 0.98 * self.prev_buy_price:
    #                 ratio_buy = 1.0
    #             elif 0.90 * self.prev_buy_price < price < 0.95 * self.prev_buy_price:
    #                 ratio_buy = 1.5
    #             elif price < 0.90 * self.prev_buy_price:
    #                 ratio_buy = 2.0
    #             else:
    #                 ratio_buy = 0.0
    #         if self.prev_buy_time and datetime_now > self.prev_buy_time + timedelta:
    #             ratio_buy = 0.4
    #         ratio = ratio_buy
    #     if direction == Direction.SHORT:
    #         if self.prev_sell_price and self.prev_sell_time and datetime_now < self.prev_sell_time + timedelta:
    #             if 0.99 * self.prev_sell_price < price < 1.01 * self.prev_sell_price:
    #                 ratio_sell = 0.5
    #             elif 1.01 * self.prev_sell_price < price < 1.05 * self.prev_sell_price:
    #                 ratio_sell = 1.0
    #             elif 1.05 * self.prev_sell_price < price < 1.10 * self.prev_sell_price:
    #                 ratio_sell = 1.5
    #             elif price > 1.10 * self.prev_sell_price:
    #                 ratio_sell = 2.0
    #             else:
    #                 ratio_sell = 0.0
    #         if self.prev_sell_time and datetime_now > self.prev_sell_time + timedelta:
    #             ratio_sell = 0.4
    #         ratio = ratio_sell
    #     return ratio

    # def check_profit(self, price: float):
    #     '''check profit'''
    #     avail_volume = self.get_current_position(base=True, available=True)
    #     prev_buy_price, prev_buy_pos, prev_buy_timedelta = self.calc_avg_trade_price(direction=Direction.LONG, vol=avail_volume, timedelta=datetime.timedelta(minutes=180))
    #     datetime_now = datetime.datetime.now(tz=MY_TZ)
    #     prev_buy_time = datetime_now - prev_buy_timedelta
    #     holding_time = datetime.timedelta(minutes=180)
    #     ratio_take_profit = 0.0
    #     if prev_buy_price > 0.1 * price:
    #         # 1. check price
    #         if 1.05*prev_buy_price < price < 1.10*prev_buy_price:
    #             ratio_take_profit = 0.5
    #         elif 1.10*prev_buy_price < price < 1.15*prev_buy_price:
    #             ratio_take_profit = 1.0
    #         elif price > 1.15*prev_buy_price:
    #             ratio_take_profit = 1.5
    #         else:
    #             ratio_take_profit = 0.25
    #         # 2. check holding time
    #         if datetime_now < prev_buy_time + holding_time:
    #             ratio_take_profit = ratio_take_profit * 2
    #         # 3. check position
    #         if prev_buy_pos > 0.7 * self.total_invest:
    #             ratio_take_profit = ratio_take_profit * 2
    #         ratio_take_profit = float(np.round(ratio_take_profit, 4))
    #     return ratio_take_profit

    def release_trading_quota(self, timestep: int = 10):
        if self.timer_count % timestep == 0:
            self.trading_quota = True

        slow_suck_step = random.randint(30, 60)
        if self.timer_count % slow_suck_step == 0:
            self.has_slow_suck_quota = True

        slow_sell_step = random.randint(30, 60)
        if self.timer_count % slow_sell_step == 0:
            self.has_slow_sell_quota = True

    # def check_rebound(self, price: float):
    #     # 1. check historical trades in 15 mins
    #     datetime_now = datetime.datetime.now(tz=MY_TZ)
    #     timedelta = datetime.timedelta(minutes=15)
    #     avg_price = 0
    #     pos = 0
    #     total_timedelta = datetime.timedelta(seconds=0)
    #     for i, at in enumerate(reversed(self.account_trades)):
    #         if at.datetime > datetime_now - timedelta:
    #             if at.direction == Direction.LONG:
    #                 avg_price += at.price * at.volume
    #                 pos += at.volume
    #                 # datetime_last = at.datetime
    #                 total_timedelta += (datetime_now - at.datetime) * at.volume
    #     if pos > 0.01:
    #         avg_price = avg_price / pos
    #     # 2. if there is profit, sell immediately
    #     ratio_fast_sell = 0.0
    #     if 1.03 * avg_price < price < 1.05 * avg_price:
    #         ratio_fast_sell = 0.5
    #     elif 1.05 * avg_price < price < 1.10 * avg_price:
    #         ratio_fast_sell = 1.0
    #     elif price > 1.10 * avg_price:
    #         ratio_fast_sell = 2.0
    #     else:
    #         ratio_fast_sell = 0.0
    #     return ratio_fast_sell

    def generate_order(self, price: float, volume: float, direction: Direction, precision: int = 4,
                       min_vol: float = 10.0, type=OrderType.LIMIT):
        if direction == Direction.LONG:
            if price:
                price = np.round(price, precision)
            else:
                rand_tmp = random.uniform(0, 1)
                if rand_tmp < 0.5:
                    price = np.round(self.last_tick.ask_price_1, precision)
                elif 0.5 < rand_tmp < 0.8:
                    price = np.round(self.last_tick.ask_price_2, precision)
                elif rand_tmp > 0.8:
                    price = np.round(self.last_tick.ask_price_3, precision)
                else:
                    price = 0
            if self.sending_count < self.max_sending_count:
                if volume * price > min_vol:
                    if type == OrderType.LIMIT or type == OrderType.IOC:
                        self.send_order(direction, price=price, volume=volume, offset=Offset.NONE, type=type)
                    elif type == OrderType.MARKET:
                        #print(np.round(volume*price, 1))
                        self.send_order(direction, price=0, volume=np.round(volume*price, 1), offset=Offset.NONE, type=OrderType.MARKET)
                    else:
                        pass
                    self.sending_count += 1
        elif direction == Direction.SHORT:
            if price:
                price = np.round(price, precision)
            else:
                rand_tmp = random.uniform(0, 1)
                if rand_tmp < 0.5:
                    price = np.round(self.last_tick.bid_price_1, precision)
                elif 0.5 < rand_tmp < 0.8:
                    price = np.round(self.last_tick.bid_price_2, precision)
                elif rand_tmp > 0.8:
                    price = np.round(self.last_tick.bid_price_3, precision)
                else:
                    pass
            if self.sending_count < self.max_sending_count:
                if volume * price > min_vol:
                    #self.send_order(direction, price=price, volume=volume, offset=Offset.NONE, type=OrderType.IOC)
                    #self.send_order(direction, price=price, volume=np.round(volume*price, 1), offset=Offset.NONE, type=OrderType.MARKET)
                    if type == OrderType.LIMIT or type == OrderType.IOC:
                        self.send_order(direction, price=price, volume=volume, offset=Offset.NONE, type=type)
                    elif type == OrderType.MARKET:
                        #print(np.round(volume*price, 1))
                        self.send_order(direction, price=0, volume=volume, offset=Offset.NONE, type=OrderType.MARKET)
                    else:
                        pass
                    self.sending_count += 1
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

    def stop_loss(self, price, sl_min: float = 0.99):
        cur_vol = self.get_current_position(base=True, volume=True)
        long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG, vol=cur_vol)
        bars = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        if len(bars) < 100:
            return
        stop_loss_price = np.min([kl.low_price for kl in bars[-3:]])
        self.stop_loss_price = sl_min*long_price
        if long_price and stop_loss_price < sl_min * long_price:
            # check 1m kline to determine
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
            self.generate_order(price=None, volume=volume, direction=direction, type=OrderType.IOC)

    def sell_quick(self, price: float, tp_min=1.01, td_quick: datetime.timedelta = datetime.timedelta(minutes=10)):
        '''
        1. quick sell if has profit
        '''
        long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG, timedelta=td_quick)
        cur_position = price * self.get_current_position(base=True, volume=True)
        direction = Direction.LONG
        # 1. if current price is higher than previous buy price and close to make deal datetime
        if cur_position < 0.5 * self.total_invest and price > tp_min * long_price and long_pos > 0.0:
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
            self.generate_order(price=None, volume=volume, direction=direction, type=OrderType.LIMIT)

    def take_profit(self, price: float, take_profit_ratio=1.10):
        ''''''
        cur_vol = self.get_current_position(base=True, volume=True)
        long_price, long_pos, long_timedelta = self.calc_avg_trade_price(direction=Direction.LONG,
                                                                         vol=cur_vol,
                                                                         timedelta=datetime.timedelta(minutes=360))

        self.take_profit_price = take_profit_ratio * long_price
        # 1. if current price is higher than previous buy price and close to make deal datetime
        if long_price > 0 and long_price > 0.5 * price and price > take_profit_ratio * long_price and long_pos > 0.0:
            direction = Direction.SHORT
            volume = self.generate_volume(price=price, direction=direction, check_balance=True, check_position=True)
            self.generate_order(price=None, volume=volume, direction=direction, type=OrderType.IOC)

    # def chase_up(self, price: float, price_buy_ratio: float = 1.02):
    #     '''
    #     1. trading volume change: low to high
    #     2. previous price variation
    #     3. previous high low price bound
    #     '''
    #     # 1. check current price with previous kline: is_slip or is_climb
    #     # 1. check current price with previous price: low or high
    #     # 2. check previous low peaks price
    #     # 3. check holding position
    #     # 4. check price break kline
    #     # 5. trading volume change: low to high
    #     # 6. price break
    #
    #     # 1. check kline
    #     bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     num_kline = len(bars1m)
    #     bars1m_data = bars1m[-360:]
    #     low_price = np.array([bar.low_price for bar in bars1m_data])
    #     high_price = np.array([bar.high_price for bar in bars1m_data])
    #     # phase 1: -20:-4, phase 2: -4:len(kline)
    #     spread_vol1, total_vol1, avg_spread_vol1 = self.calc_spread_vol_kline(start=num_kline-20, end=num_kline-4)
    #     spread_vol2, total_vol2, avg_spread_vol2 = self.calc_spread_vol_vline(start=num_kline-4, end=num_kline)
    #
    #     # 1. reverse price array to find low minimal
    #     if len(low_price) == 0:
    #         return
    #     peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
    #     if len(peaks_low) > 0:
    #         bar_low = bars1m_data[peaks_low[-1]]
    #         self.prev_low_price = bar_low.low_price
    #     else:
    #         self.prev_low_price = None
    #         return
    #     self.is_chase_up = False
    #
    #     # 1. check market crash
    #     if price < price_buy_ratio*bar_low.low_price:
    #         self.is_chase_up = True
    #
    #     # 2. check timestamp: 30min for buy low
    #     if bar_low.datetime < datetime.datetime.now(tz=MY_TZ)-datetime.timedelta(minutes=30):
    #         self.is_chase_up = False
    #
    #     # 3. check position
    #     if self.is_chase_up:
    #         '''start chasing up'''
    #         # 1. price is in low position: check bars
    #         cur_position = self.balance_info.data[self.base_currency].available*price
    #         if cur_position < 0.2 * self.max_invest:
    #             self.write_log(f'Chasing up {datetime.datetime.now(tz=MY_TZ)}')
    #             direction = Direction.LONG
    #             volume = self.generate_volume(price=price, direction=direction,
    #                                           check_position=True)
    #             self.generate_order(price=price, volume=volume, direction=direction)
    #             #self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    # def chase_rebound(self, price: float, price_buy_ratio: float = 1.03, price_sell_ratio: float = 1.05):
    #     bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     bars1m_data = bars1m[-360:]
    #     low_price = np.array([bar.low_price for bar in bars1m_data])
    #
    #     # 1. reverse price array to find low minimal
    #     if len(low_price) == 0:
    #         return
    #     peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
    #     if len(peaks_low) > 0:
    #         bar_low = bars1m_data[peaks_low[-1]]
    #         self.prev_low_price = bar_low.low_price
    #     else:
    #         self.prev_low_price = None
    #         return
    #
    #     self.is_rebound = False
    #
    #     # 1. check market crash: if price rebound
    #     if price < price_buy_ratio*bar_low.low_price:
    #         self.is_rebound = True
    #
    #     # 2. check timestamp: 30min for buy low
    #     if bar_low.datetime < datetime.datetime.now(tz=MY_TZ)-datetime.timedelta(minutes=15):
    #         self.is_rebound = False
    #
    #     if self.is_rebound:
    #         '''start chase rebound'''
    #         # 3. check current position
    #         cur_position = self.balance_info.data[self.base_currency].available*price
    #         if cur_position < 0.2 * self.max_invest:
    #             self.write_log(f'Chasing up {datetime.datetime.now(tz=MY_TZ)}')
    #             direction = Direction.LONG
    #             volume = self.generate_volume(price=price, direction=direction, check_position=True)
    #             self.generate_order(price=price, volume=volume, direction=direction)
    #             #self.send_order(direction=direction, price=price, volume=volume, offset=Offset.NONE)

    def buy_slump(self, price: float):
        # 1. don't buy in top divergence
        top_div_events = self.meg.events[MarketEvent.TOP_DIVERGENCE]
        is_top_divergence = False
        if len(top_div_events) > 0:
            last_top_div_event = top_div_events[-1]
            if datetime.datetime.now() - last_top_div_event.event_datetime > datetime.timedelta(minutes=30):
                is_top_divergence = True

        # 2. don't buy after surge
        surge_events = self.meg.events[MarketEvent.SURGE]
        is_surge = False
        if len(surge_events) > 0:
            last_surge_event = surge_events[-1]
            if datetime.datetime.now() - last_surge_event.event_datetime > datetime.timedelta(minutes=60):
                is_surge = True

        # 3. check current slump signal
        slump_events = self.meg.events[MarketEvent.SLUMP]
        is_slump = False
        if len(slump_events) > 0:
            last_slump_event = slump_events[-1]
            if datetime.datetime.now() - last_slump_event.event_datetime < datetime.timedelta(minutes=5):
                is_slump = True
        if is_slump and not is_top_divergence and not is_surge and not self.first_time:
            direction = Direction.LONG
            # 1. price is in low position: check bars
            #cur_position = self.get_current_position(quote=True, available=True)
            price = self.last_trade.price
            cur_base = self.get_current_position(base=True, volume=True) * price

            total_quote = self.get_current_position(quote=True, volume=True)
            avail_quote = self.get_current_position(quote=True, available=True)
            frozen_quote = total_quote - avail_quote
            cur_invest = cur_base + frozen_quote

            #total_usdt = 1800
            #self.total_invest
            if cur_invest < self.max_invest and self.cur_buy_vol < self.short_term_trading_vol:
                volume = self.generate_volume(price=price, direction=direction, check_position=True)
                self.generate_order(price=None, volume=volume, direction=direction, min_vol=10, type=OrderType.MARKET)
                self.cur_buy_vol += volume * price
                for i in range(3):
                    volume = self.generate_volume(price=price, direction=direction, check_position=True)
                    self.generate_order(price=price * (1.0 - 0.0005 * (i + 1)),
                                        volume=volume, direction=direction,
                                        min_vol=10, type=OrderType.LIMIT)
                    self.cur_buy_vol += volume * price

    def sell_surge(self, price: float):
        # 1. don't sell after bottom_divergence
        bottom_div_events = self.meg.events[MarketEvent.BOTTOM_DIVERGENCE]
        is_bottom_divergence = False
        if len(bottom_div_events) > 0:
            last_bottom_div_event = bottom_div_events[-1]
            if datetime.datetime.now() - last_bottom_div_event.event_datetime > datetime.timedelta(minutes=30):
                is_bottom_divergence = True
        # 2. don't sell immediately after short liquidation
        slump_events = self.meg.events[MarketEvent.SLUMP]
        is_slump = False
        if len(slump_events) > 0:
            last_slump_event = slump_events[-1]
            if datetime.datetime.now() - last_slump_event.event_datetime > datetime.timedelta(minutes=10):
                is_slump = True

        # 3. sell at surge
        surge_events = self.meg.events[MarketEvent.SURGE]
        is_surge = False
        if len(surge_events) > 0:
            last_surge_event = surge_events[-1]
            if datetime.datetime.now() - last_surge_event.event_datetime < datetime.timedelta(minutes=3):
                is_surge = True
        if is_surge and not is_bottom_divergence and not is_slump and not self.first_time:
            if self.cur_sell_vol < self.short_term_trading_vol:
                direction = Direction.SHORT
                volume = self.generate_volume(price=price, direction=direction, check_position=True)
                self.generate_order(price=None, volume=volume, direction=direction, min_vol=10, type=OrderType.MARKET)
                self.cur_sell_vol += volume * price
                for i in range(3):
                    volume = self.generate_volume(price=price, direction=direction, check_position=True)
                    self.generate_order(price=price * (1 + 0.0005 * (i + 1)), volume=volume, direction=direction,
                                        min_vol=10, type=OrderType.LIMIT)
                    self.cur_sell_vol += volume * price

    def slow_sell(self, price: float, max_ratio: float = 0.7):
        cur_position = price * self.get_current_position(base=True, volume=True)
        direction = Direction.SHORT
        if cur_position > max_ratio * self.total_invest and self.has_slow_sell_quota:
            if self.pos > 0.95:
                volume = self.generate_volume(price=price, direction=direction, check_position=True)
                self.generate_order(price=None, volume=volume, direction=direction, min_vol=10, type=OrderType.LIMIT)
                self.has_slow_sell_quota = False

    def slow_suck(self, price: float, min_ratio: float = 0.3):
        cur_position = price * self.get_current_position(base=True, volume=True)
        direction = Direction.LONG
        if cur_position < min_ratio * self.total_invest and self.has_slow_suck_quota:
            # 1. price is lower than before
            #vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
            klines_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
            #min_price = np.min([vl.close_price for vl in vlines[-100:]])
            low_price = np.min([kl.close_price for kl in klines_1m[-300:]])
            if price < 0.995*low_price and self.pos < 0.1:
                volume = self.generate_volume(price=price, direction=direction, check_position=True)
                self.generate_order(price=None, volume=volume, direction=direction, min_vol=10, type=OrderType.IOC)
                self.has_slow_suck_quota = False

    def test_trade(self):
        if self.last_tick and self.last_tick.bid_price_1 > 0 and self.last_tick.ask_price_1 > 0:
            if random.uniform(0, 1) < 0.5 and True:
                volume = self.generate_volume(price=self.last_tick.ask_price_1, direction=Direction.LONG, check_position=True)
                self.generate_order(price=None, volume=volume, direction=Direction.LONG,
                                    type=OrderType.MARKET)
            else:
                volume = self.generate_volume(price=self.last_tick.bid_price_1, direction=Direction.SHORT, check_position=True)
                self.generate_order(price=None, volume=volume, direction=Direction.SHORT,
                                    type=OrderType.MARKET)
            self.test_count += 1

        if self.timer_count % 30 == 0:
            pass

    def make_decision(self, price: float):
        ''''''
        # 1. buy at liquidation
        if True:
            self.buy_slump(price=price)

        # 2.1 buy at price rebound
        #if False:
        #    self.chase_rebound(price=price)

        # 2.2 buy at low price
        if False:
            self.slow_suck(price=price)

        if False:
            self.slow_sell(price=price)

        #if True:
        #    self.chase_up(price=price)

        # 3. sell at high volume and high price
        if True:
            self.sell_surge(price=price)

        if True:
            self.sell_quick(price=price, tp_min=1.01, td_quick=datetime.timedelta(minutes=20))

        # 4. stop loss
        if True:
            self.stop_loss(price=price, sl_min=0.97)

        # 5. take profit
        if True:
            self.take_profit(price=price)

    def update_vline_feature(self):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if len(vlines) == 0:
            return
        datetime_now = datetime.datetime.now()
        datetime_close = vlines[-1].close_time
        is_up2date = datetime_now - datetime_close < datetime.timedelta(seconds=60)
        if is_up2date:
            #res_spread_vol = self.update_spread_vol_vline(start_second=0, seconds=[15, 60, 120, 180, 300])
            res_spread_vol = None
            res_spread = self.update_spread_vline(start_second=0, seconds=[15, 60, 120, 180, 300])
            res_vol = self.update_vol_vline(start_second=0, seconds=[15, 60, 120, 180, 300])
            #print(res_spread)
            #print(res_vol)
            self.update_market_event(res_spread_vol=res_spread_vol, res_spread=res_spread, res_vol=res_vol)
            if False:
                bsv = res_spread_vol[Direction.LONG]
                ssv = res_spread_vol[Direction.SHORT]
                tsv = res_spread_vol[Direction.NONE]
                s = 'avg_sv'
                print(f'B:{bsv[15][s]} {bsv[60][s]} {bsv[120][s]} {bsv[180][s]}')
                print(f'S:{ssv[15][s]} {ssv[60][s]} {ssv[120][s]} {ssv[180][s]}')
                print(f'T:{tsv[15][s]} {tsv[60][s]} {tsv[120][s]} {tsv[180][s]}')
                print()
                for event_type in self.meg.events:
                    #print(self.meg.events[event_type])
                    events = self.meg.events[event_type]
                    if len(events) > 0:
                        event = events[-1]
                        if event.event_datetime > datetime.datetime.now()-datetime.timedelta(minutes=10):
                            print(event)
                # for event in self.meg.events[event_type]:
                #     if event.event_datetime > datetime.datetime.now()-datetime.timedelta(minutes=10):
                #         print(event)

        # self.sv_buy_15 = res_spread_vol[Direction.LONG][15][0]
        # self.sv_buy_60 = res_spread_vol[Direction.LONG][60][0]
        # self.sv_buy_120 = res_spread_vol[Direction.LONG][120][0]
        #
        # self.sv_sell_15 = res_spread_vol[Direction.SHORT][15][0]
        # self.sv_sell_60 = res_spread_vol[Direction.SHORT][60][0]
        # self.sv_sell_120 = res_spread_vol[Direction.SHORT][120][0]
        # print(res_spread_vol)

    def update_tick_feature(self):
        pass

    def update_kline_feature(self):
        pass

    def update_volume_feature(self):
        #kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
        #vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
        kl100 = kline_1m[-100:]
        kl1000 = kline_1m[-1000:]
        if len(kl100) < 100 or len(kl1000) < 1000:
            return
        self.median_vol_100 = float(np.median([kl.amount for kl in kl100]))
        self.median_vol_1000 = float(np.median([kl.amount for kl in kl1000]))
        self.median_vol = float(np.round(min(self.median_vol_100, self.median_vol_1000), 2))
        self.vol_1m_thresh = 1 * 5 * self.median_vol
        self.vol_2m_thresh = 2 * 5 * self.median_vol
        self.vol_3m_thresh = 3 * 5 * self.median_vol
        self.vol_5m_thresh = 5 * 5 * self.median_vol

        # update vol select for price distribution
        vol_list = self.market_params[self.symbol]['vline_vol_list']
        tmp = [vol for vol in vol_list if vol > self.median_vol_1000 * 20]
        if len(tmp) > 0:
            self.vol_select = min(tmp)
        else:
            self.vol_select = vol_list[-1]

    def update_market_event(self, res_spread_vol: dict = None, res_spread: dict = None, res_vol: dict = None):
        if self.last_trade is None:
            return
        is_up2date = datetime.datetime.now() - self.last_trade.datetime < datetime.timedelta(seconds=15)
        if not is_up2date:
            return
        self.check_gain_slip(res_spread_vol=res_spread_vol, res_spread=res_spread, use_vline=True)
        self.check_surge_slump(res_spread_vol=res_spread_vol, res_spread=res_spread, res_vol=res_vol, use_vline=True)
        self.check_divergence(start_ind=3, end_ind=20)
        self.check_trade_speed()

        # update market event flag
        datetime_now = datetime.datetime.now()
        datetime_last = self.last_trade.datetime
        for event_type in self.meg.events:
            events = self.meg.events[event_type]
            if len(events) == 0:
                continue
            last_event = events[-1]
            datetime_last = last_event.event_datetime
            if datetime_now - datetime_last > datetime.timedelta(seconds=60):
                if last_event.event_type == MarketEvent.SLUMP:
                    self.is_slump = False
                if last_event.event_type == MarketEvent.SURGE:
                    self.is_surge = False
                if last_event.event_type == MarketEvent.TOP_DIVERGENCE:
                    self.is_top_divergence = False
                if last_event.event_type == MarketEvent.BOTTOM_DIVERGENCE:
                    self.is_bottom_divergence = False
                if last_event.event_type == MarketEvent.GAIN:
                    self.is_gain = False
                if last_event.event_type == MarketEvent.SLIP:
                    self.is_slip = False


    # def update_high_low_price(self):
    #     bars1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     bars1m_data = bars1m[-360:]
    #     low_price = np.array([bar.low_price for bar in bars1m_data])
    #     high_price = np.array([bar.high_price for bar in bars1m_data])
    #
    #     # 1. reverse price array to find low minimal
    #     if len(low_price) > 0:
    #         peaks_low, _ = find_peaks(np.max(low_price) + 10 - low_price, distance=10, prominence=0.3, width=5)
    #         if len(peaks_low) > 0:
    #             self.prev_low_price = bars1m_data[peaks_low[-1]].low_price
    #         else:
    #             self.prev_low_price = None
    #
    #     if len(high_price) > 0:
    #         peaks_high, _ = find_peaks(high_price, distance=10, prominence=0.3, width=5)
    #         if len(peaks_high) > 0:
    #             self.prev_high_price = bars1m_data[peaks_high[-1]].high_price
    #         else:
    #             self.prev_high_price = None


    # def update_vol(self, time_step=10):
    #     if self.timer_count % time_step == 0:
    #         self.cur_buy_vol = 0
    #         self.cur_sell_vol = 0
    #
    #         events = self.meg.events
    #         for event_type in events:
    #             event_list = events[event_type]
    #             if len(event_list) > 0:
    #                 last_event = event_list[-1]
    #                 dateitme_now = datetime.datetime.now()
    #                 if dateitme_now - last_event.event_datetime > datetime.timedelta(minutes=1):
    #                     if last_event.event_type == MarketEvent.GAIN:
    #                         self.is_gain = False
    #                     if last_event.event_type == MarketEvent.SLIP:
    #                         self.is_slip = False
    #                     if last_event.event_type == MarketEvent.SLUMP:
    #                         self.is_slump = False
    #                     if last_event.event_type == MarketEvent.SURGE:
    #                         self.is_surge = False
    #                     if last_event.event_type == MarketEvent.TOP_DIVERGENCE:
    #                         self.is_top_divergence = False
    #                     if last_event.event_type == MarketEvent.BOTTOM_DIVERGENCE:
    #                         self.is_bottom_divergence = False

        # kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
        # kltmp = kline_1m[-1000:]
        # if len(kltmp) < 100:
        #     return
        # med_vol = float(np.median([kl.amount for kl in kltmp]))
        # vol_list = self.market_params[self.symbol]['vline_vol_list']
        # tmp = [vol for vol in vol_list if vol > med_vol * 20]
        # self.median_vol = med_vol
        # if len(tmp) > 0:
        #     self.vol_select = min(tmp)
        # else:
        #     self.vol_select = vol_list[-1]
        # self.buy_vol_1m = 0
        # self.buy_vol_5m = 0
        # self.buy_vol_15m = 0
        # self.sell_vol_1m = 0
        # self.sell_vol_5m = 0
        # self.sell_vol_15m = 0

        # update buyer and seller volume in real time
        # vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        # for vl in reversed(vlines):
        #     pass

    # def update_ref_price(self):
    #     '''update reference price for buy and sell'''
    #     # 1. choose proper vline to calculate ref price
    #     kline_1m = self.kqg.get_bars(self.vt_symbol, Interval.MINUTE)
    #     kltmp = kline_1m[-1000:]
    #     if len(kltmp) < 100:
    #         return
    #     avg_vol = float(np.median([kl.amount for kl in kltmp]))
    #     vol_list = self.market_params[self.symbol]['vline_vol_list']
    #     vol = min([vol for vol in vol_list if vol > avg_vol*20])
    #
    #     self.vol_select = vol
    #
    #     #self.buy_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.05), 4))
    #     #self.sell_price = float(np.round(self.vqg[self.vt_symbol].vq[vol].top_k_price(k=0.95), 4))

    def update_trade_prob(self, price: float):
        # 1. choose proper vline to calculate ref price
        # 2. update buy or sell probility
        if self.buy_price:
            self.buy_prob = self.calc_pro_buy(price=price, price_ref=self.buy_price, theta=self.theta, global_prob=self.global_prob)
        if self.sell_price:
            self.sell_prob = self.calc_pro_sell(price=price, price_ref=self.sell_price, theta=self.theta, global_prob=self.global_prob)

    # def update_position_budget(self, price: float):
    #     # check current position
    #     #cur_position = self.balance_info.data[self.base_currency].available * price
    #     cur_position = self.get_current_position(base=True, available=True)*price
    #     if cur_position > 0.9*self.max_invest:
    #         self.max_invest = min(self.total_invest, cur_position+0.1*self.total_invest)

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

        event_slump = self.meg.get_event(event_type=MarketEvent.SLUMP)
        event_surge = self.meg.get_event(event_type=MarketEvent.SURGE)
        datetime_thresh = datetime.datetime.now() - datetime.timedelta(minutes=180)
        slump_count = 0
        surge_count = 0
        if len(event_slump) > 0:
            slump_count = len([event for event in event_slump if event.event_datetime < datetime_thresh])
        if len(event_surge) > 0:
            surge_count = len([event for event in event_surge if event.event_datetime < datetime_thresh])
        if slump_count >= 1 and surge_count == 0:
            self.max_invest = min(slump_count*2, 10) * base_invest
        else:
            self.max_invest = 1.0 * base_invest

        #new_max_invest = min(max(int(self.cur_invest/base_invest+1)*base_invest, base_invest), self.total_invest)
        # if not self.update_invest_limit_time:
        #     self.max_invest = new_max_invest
        #     self.update_invest_limit_time = datetime_now
        #
        # if self.update_invest_limit_time+update_time_period < datetime_now:
        #     self.update_invest_limit_time = datetime_now
        #     self.max_invest = min(self.total_invest, new_max_invest)

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

    # def calc_spread_vol_vline(self, start: int, end: int) -> float:
    #     vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
    #     avg_spread_vol = 0
    #     spread_vol = 0
    #     total_vol = 0
    #     if not start:
    #         start = 0
    #     if not end:
    #         end = len(vlines)
    #     if start and end and start < end and start <= len(vlines) and end <= len(vlines):
    #         vline_start_end = vlines[start: end]
    #         spread_vol = np.sum([(vl.close_price - vl.open_price) / vl.open_price * vl.volume for vl in vline_start_end])
    #         total_vol = np.sum([vl.volume for vl in vline_start_end])
    #         #avg_vol = total_vol / len(vline_start_end)
    #         if total_vol > 0:
    #             avg_spread_vol = spread_vol / total_vol
    #     return spread_vol, total_vol, avg_spread_vol

    # def calc_spread_vol_kline(self, start: int, end: int, interval: Interval = Interval.MINUTE) -> float:
    #     klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
    #     #num_kline = len(klines)
    #     vol_median = np.median([kl.volume for kl in klines[-1000:-1]])
    #     avg_spread_vol = 0
    #     spread_vol = 0
    #     total_vol = 0
    #     if not start:
    #         start = 0
    #     if not end:
    #         end = len(klines)
    #     if start and end and start < end and start <= len(klines) and end <= len(klines):
    #         kline_start_end = klines[start: end]
    #         spread_vol = np.sum([(kl.close_price - kl.open_price) / kl.open_price * kl.volume/vol_median for kl in kline_start_end])
    #         total_vol = np.sum([kl.volume for kl in kline_start_end])
    #         if total_vol > 0:
    #             avg_spread_vol = spread_vol / total_vol
    #     return spread_vol, total_vol, avg_spread_vol

    # def calc_spread_kline(self, start: int, end: int, interval: Interval = Interval.MINUTE) -> float:
    #     klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
    #     spread_sum = 0
    #     total_vol = 0
    #     if not start:
    #         start = 0
    #     if not end:
    #         end = len(klines)
    #     if start and end and start < end and start <= len(klines) and end <= len(klines):
    #         kline_start_end = klines[start: end]
    #         spread_sum = np.sum([(kl.close_price - kl.open_price) / kl.open_price for kl in kline_start_end])
    #         total_vol = np.sum([kl.volume for kl in kline_start_end])
    #     return spread_sum, total_vol

    def calc_gain_speed(self, num_vline: int = 3):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        cur_vline = self.vg[self.vt_symbol].vline_buf[self.vline_vol]
        if len(vlines) < num_vline:
            return
        #print(cur_vline)
        vlines_tmp = vlines[-1*num_vline:]
        total_gain_vol = 0
        total_vol = 0
        total_time = datetime.timedelta(seconds=0)
        # add in vlines
        for vl in vlines_tmp:
            total_gain_vol += (vl.close_price - vl.open_price) * vl.volume
            total_vol += vl.volume
            total_time += (vl.close_time - vl.open_time)
        # add vline_buf
        total_gain_vol += (cur_vline.close_price - cur_vline.open_price) * cur_vline.volume
        total_vol += cur_vline.volume
        total_time += (cur_vline.close_time - cur_vline.open_time)

        if total_time.total_seconds() > 0 and total_vol > 0:
            trade_speed = total_vol / total_time.total_seconds()
            trade_gain = total_gain_vol / total_vol
        else:
            trade_speed = 0
            trade_gain = 0
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
        if self.timer_count % time_step == 0:
            self.trade_gain, self.trade_speed = self.calc_gain_speed(num_vline=num_vline)
            self.trade_gain = np.round(self.trade_gain, 4)
            self.trade_speed = np.round(self.trade_speed, 4)
        #self.check_surge_slump(thresh_gain=0.01, thresh_speed=30, num_vline=5)

    def update_spread_vline(self, start_second=0, seconds=[15, 60, 120, 300]):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        start_td = datetime.timedelta(seconds=start_second)
        # res_vol = {Direction.LONG: {}, Direction.SHORT: {}, Direction.NONE: {}}
        # res_spread_vol = {Direction.LONG: {}, Direction.SHORT: {}, Direction.NONE: {}}
        res_spread = {}
        for ss in seconds:
            end_td = datetime.timedelta(seconds=ss)
            spread = VlineFeature.calc_spread(vlines=vlines, start_td=start_td, end_td=end_td)
            res_spread[ss] = spread
        return res_spread

    def update_vol_vline(self, start_second=0, seconds=[15, 60, 120, 180, 600, 1200]):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        start_td = datetime.timedelta(seconds=start_second)
        res_vol = {Direction.LONG: {}, Direction.SHORT: {}, Direction.NONE: {}}
        for ss in seconds:
            end_td = datetime.timedelta(seconds=ss)
            vol_buy = VlineFeature.calc_vol(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.LONG)
            vol_sell = VlineFeature.calc_vol(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.SHORT)
            vol_total = VlineFeature.calc_vol(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.NONE)
            res_vol[Direction.LONG][ss] = vol_buy
            res_vol[Direction.SHORT][ss] = vol_sell
            res_vol[Direction.NONE][ss] = vol_total
        return res_vol

    def update_spread_vol_vline(self, start_second=0, seconds=[15, 60, 120, 180, 600, 1200]):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        start_td = datetime.timedelta(seconds=start_second)
        #res_vol = {Direction.LONG: {}, Direction.SHORT: {}, Direction.NONE: {}}
        res_spread_vol = {Direction.LONG: {}, Direction.SHORT: {}, Direction.NONE: {}}
        for ss in seconds:
            end_td = datetime.timedelta(seconds=ss)
            spread_vol_buy = VlineFeature.calc_spread_vol(vlines=vlines, start_td=start_td, end_td=end_td,
                                                          direction=Direction.LONG)
            spread_vol_sell = VlineFeature.calc_spread_vol(vlines=vlines, start_td=start_td, end_td=end_td,
                                                           direction=Direction.SHORT)
            spread_vol_total = VlineFeature.calc_spread_vol(vlines=vlines, start_td=start_td, end_td=end_td,
                                                            direction=Direction.SHORT)
            res_spread_vol[Direction.LONG][ss] = spread_vol_buy
            res_spread_vol[Direction.SHORT][ss] = spread_vol_sell
            res_spread_vol[Direction.NONE][ss] = spread_vol_total

        return res_spread_vol

    # def check_gain_slip_by_kline(self, count=3):
    #     kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     kline_tmp = kline_1m[-1 * count:]
    #     close_open_ratio = [bar.close_price / bar.open_price for bar in kline_tmp]
    #     high_low_ratio = [bar.high_price / bar.low_price for bar in kline_tmp]
    #     gain_count = sum(
    #         [int(close_open_ratio[i] > 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
    #     slip_count = sum(
    #         [int(close_open_ratio[i] < 1.005 | high_low_ratio[i] < 1.005) for i in range(close_open_ratio)])
    #     self.is_gain = gain_count >= count
    #     self.is_slip = slip_count >= count

    def get_spread_vol(self, res_spread_vol: dict, direction: Direction, second: int, data_type: str):
        if direction in res_spread_vol:
            if second in res_spread_vol[direction]:
                if data_type in res_spread_vol[direction][second]:
                    return res_spread_vol[direction][second][data_type]
        return None

    def get_spread(self, res_spread: dict, second: int):
        if second in res_spread:
            return res_spread[second]['spread']
        return None

    def get_vol(self, res_vol: dict, second: int, direction: Direction = Direction.NONE):
        if direction in res_vol:
            if second in res_vol[direction]:
                return res_vol[direction][second]['total_vol']
        return None

    def check_gain_slip_by_vline(self, res_spread_vol: dict = None, res_spread: dict = None):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if False or res_spread_vol is not None:
            avg_sv_buy_15s = self.get_spread_vol(res_spread_vol, direction=Direction.LONG, second=15, data_type='avg_sv')
            avg_sv_sell_15s = self.get_spread_vol(res_spread_vol, direction=Direction.SHORT, second=15, data_type='avg_sv')
            #avg_sv_15s = self.get_spread_vol(res_spread_vol, direction=Direction.NONE, second=15, data_type='total_vol')
            avg_sv_buy_60s = self.get_spread_vol(res_spread_vol, direction=Direction.LONG, second=60, data_type='avg_sv')
            avg_sv_sell_60s = self.get_spread_vol(res_spread_vol, direction=Direction.SHORT, second=60, data_type='avg_sv')
            #avg_sv_60s = self.get_spread_vol(res_spread_vol, direction=Direction.NONE, second=60, data_type='total_vol')

            # calculate gain and slip
            if avg_sv_buy_15s is not None and avg_sv_buy_60s is not None:
                if avg_sv_buy_15s > self.sv_buy_15s_thresh or avg_sv_buy_60s > self.sv_buy_60s_thresh:
                    self.is_gain = True
            #else:
            #    self.is_gain = False
            if avg_sv_sell_15s is not None and avg_sv_sell_60s is not None:
                if avg_sv_sell_15s < -1 * self.sv_sell_15s_thresh or avg_sv_sell_60s < -1 * self.sv_sell_60s_thresh:
                    self.is_slip = True
            #else:
            #    self.is_slip = True

        if res_spread is not None:
            spread_15s = self.get_spread(res_spread=res_spread, second=15)
            spread_1m = self.get_spread(res_spread=res_spread, second=60)
            self.is_gain = False
            self.is_slip = False
            if spread_15s is not None and spread_1m is not None:
                #if spread_15s > self.spread_15s_thresh and spread_1m > self.spread_1m_thresh:
                if spread_1m > self.spread_1m_thresh:
                    self.is_gain = True
                else:
                    self.is_gain = False
                #if spread_15s < -1 * self.spread_15s_thresh and spread_1m < -1 * self.spread_1m_thresh:
                if spread_1m < -1*self.spread_1m_thresh:
                    self.is_slip = True
                else:
                    self.is_slip = False

        if self.is_gain:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.GAIN, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=1))
        if self.is_slip:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.SLIP, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=1))

    def check_gain_slip(self, res_spread_vol: dict = None,
                        res_spread: dict = None,
                        use_kline=False, use_vline=False):
        if use_kline and not use_vline:
            self.check_gain_slip_by_kline()
        elif not use_kline and use_vline:
            self.check_gain_slip_by_vline(res_spread_vol=res_spread_vol, res_spread=res_spread)
        else:
            pass

    def check_surge_slump(self, res_spread_vol: dict = None, res_spread: dict = None, res_vol: dict = None,
                          use_kline=False, use_vline=False):
        if use_kline and not use_vline:
            self.check_surge_slump_by_kline()
        elif not use_kline and use_vline:
            self.check_surge_slump_by_vline(res_spread_vol=res_spread_vol, res_spread=res_spread, res_vol=res_vol)
        else:
            pass

    def check_surge_slump_by_vline(self, res_spread_vol: dict = None, res_spread: dict = None, res_vol: dict = None):
        def is_surge_func(spread, vol, spread_thresh, vol_thresh):
            return (spread > spread_thresh) & (vol > vol_thresh)

        def is_slump_func(spread, vol, spread_thresh, vol_thresh):
            return (spread < -1*spread_thresh) & (vol > vol_thresh)

        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        if res_spread_vol is not None:
            avg_sv_buy_60s = self.get_spread_vol(res_spread_vol, direction=Direction.LONG, second=60, data_type='avg_sv')
            avg_sv_sell_60s = self.get_spread_vol(res_spread_vol, direction=Direction.SHORT, second=60, data_type='avg_sv')
            total_vol_60s = self.get_spread_vol(res_spread_vol, direction=Direction.NONE, second=60, data_type='total_vol')

            avg_sv_buy_120s = self.get_spread_vol(res_spread_vol, direction=Direction.LONG, second=120, data_type='avg_sv')
            avg_sv_sell_120s = self.get_spread_vol(res_spread_vol, direction=Direction.SHORT, second=120, data_type='avg_sv')
            total_vol_120s = self.get_spread_vol(res_spread_vol, direction=Direction.NONE, second=120, data_type='total_vol')

            avg_sv_buy_180s = self.get_spread_vol(res_spread_vol, direction=Direction.LONG, second=180, data_type='avg_sv')
            avg_sv_sell_180s = self.get_spread_vol(res_spread_vol, direction=Direction.SHORT, second=180, data_type='avg_sv')
            total_vol_180s = self.get_spread_vol(res_spread_vol, direction=Direction.NONE, second=180, data_type='total_vol')

            # calculate surge and slump
            is_price_up = (avg_sv_buy_60s > self.sv_buy_60s_thresh) & (avg_sv_buy_120s > self.sv_buy_120s_thresh) & (avg_sv_buy_180s > self.sv_buy_180s_thresh)
            is_price_down = (avg_sv_sell_60s < -1*self.sv_sell_60s_thresh) & (avg_sv_sell_120s < -1*self.sv_sell_120s_thresh) & (avg_sv_sell_180s < -1*self.sv_sell_180s_thresh)
            is_high_vol = (total_vol_60s > 3*self.median_vol_100) & (total_vol_120s > 6*self.median_vol_100) & (total_vol_180s > 9*self.median_vol_100)
            if is_price_up and is_high_vol:
                self.is_surge = True
            if is_price_down and is_high_vol:
                self.is_slump = True

        if res_spread is not None:
            spread_1m = self.get_spread(res_spread=res_spread, second=60)
            spread_2m = self.get_spread(res_spread=res_spread, second=120)
            spread_3m = self.get_spread(res_spread=res_spread, second=180)
            spread_5m = self.get_spread(res_spread=res_spread, second=300)
            vol_1m = self.get_vol(res_vol=res_vol, second=60)
            vol_2m = self.get_vol(res_vol=res_vol, second=120)
            vol_3m = self.get_vol(res_vol=res_vol, second=180)
            vol_5m = self.get_vol(res_vol=res_vol, second=300)

            is_surge_1m = is_surge_func(spread_1m, vol_1m, self.spread_1m_thresh, self.vol_1m_thresh)
            is_surge_2m = is_surge_func(spread_2m, vol_2m, self.spread_2m_thresh, self.vol_2m_thresh)
            is_surge_3m = is_surge_func(spread_3m, vol_3m, self.spread_3m_thresh, self.vol_3m_thresh)
            is_surge_5m = is_surge_func(spread_5m, vol_5m, self.spread_5m_thresh, self.vol_5m_thresh)
            is_slump_1m = is_slump_func(spread_1m, vol_1m, self.spread_1m_thresh, self.vol_1m_thresh)
            is_slump_2m = is_slump_func(spread_2m, vol_2m, self.spread_2m_thresh, self.vol_2m_thresh)
            is_slump_3m = is_slump_func(spread_3m, vol_3m, self.spread_3m_thresh, self.vol_3m_thresh)
            is_slump_5m = is_slump_func(spread_5m, vol_5m, self.spread_5m_thresh, self.vol_5m_thresh)

            if is_surge_1m or is_surge_2m or is_surge_3m or is_surge_5m:
                self.is_surge = True
            else:
                self.is_surge = False

            if is_slump_1m or is_slump_2m or is_slump_3m or is_slump_5m:
                self.is_slump = True
            else:
                self.is_slump = False

        if self.is_surge:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.SURGE, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=3))

        if self.is_slump:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.SLUMP, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=3))

    def check_surge_slump_by_kline(self, thresh_gain: float = 0.01, thresh_speed: float = 10, num_vline: int = 10):
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

    def check_divergence(self, start_ind=3, end_ind=20):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
        spread_0_3 = BarFeature.calc_spread(klines=kline_1m, start=0, end=start_ind, interval=Interval.MINUTE)
        spread_3_20 = BarFeature.calc_spread(klines=kline_1m, start=start_ind, end=end_ind, interval=Interval.MINUTE)

        if spread_0_3 > self.spread_3m_thresh and spread_3_20 < -4*self.spread_5m_thresh:
            self.is_bottom_divergence = True
        else:
            self.is_bottom_divergence = False
        if spread_0_3 < -1*self.spread_3m_thresh and spread_3_20 > 4*self.spread_5m_thresh:
            self.is_top_divergence = True
        else:
            self.is_top_divergence = False

        if self.is_bottom_divergence:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.BOTTOM_DIVERGENCE, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=5))
        if self.is_top_divergence:
            event_datetime = vlines[-1].close_time
            med = MarketEventData(event_type=MarketEvent.TOP_DIVERGENCE, event_datetime=event_datetime)
            self.meg.add_event_data(market_event_data=med, timeout=datetime.timedelta(minutes=5))

    def check_trade_speed(self):
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        start_td = datetime.timedelta(seconds=0)
        end_td = datetime.timedelta(seconds=15)
        trade_total_speed = VlineFeature.calc_vol_speed(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.NONE)
        trade_buy_speed = VlineFeature.calc_vol_speed(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.LONG)
        trade_sell_speed = VlineFeature.calc_vol_speed(vlines=vlines, start_td=start_td, end_td=end_td, direction=Direction.SHORT)
        self.total_speed = float(np.round(trade_total_speed, 4))
        self.sell_speed = float(np.round(trade_sell_speed, 4))
        self.buy_speed = float(np.round(trade_buy_speed, 4))

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

    def detect_liquidation(self, lasting_thresh=datetime.timedelta(minutes=5)):
        # 1. check price is going down
        if (self.sv_3_0 < -1*self.sv_t3) & (self.sv_5_0 < -1*self.sv_t5) & (self.sv_10_0 < -1*self.sv_t10) & (self.sv_20_0 < -1*self.sv_t20):
            self.is_price_going_down = True
        else:
            self.is_price_going_down = False

        if (self.sv_3_0 > self.sv_t3) & (self.sv_5_0 > self.sv_t5) & (self.sv_10_0 > self.sv_t10) & (self.sv_20_0 > self.sv_t20):
            self.is_price_going_up = True
        else:
            self.is_price_going_up = False

        # check vlines vol in minute
        vlines = self.vg[self.vt_symbol].vlines[self.vline_vol]
        vol1m = 0
        ts1m = datetime.timedelta(seconds=0)
        vol3m = 0
        ts3m = datetime.timedelta(seconds=0)
        for vl in reversed(vlines):
            vol1m += vl.volume
            ts1m += (vl.close_time-vl.open_time)
            if ts1m > datetime.timedelta(seconds=60):
                break
        if vol1m > 3*self.median_vol:
            is_high_vol_1m = True
        else:
            is_high_vol_1m = False

        for vl in reversed(vlines):
            vol3m += vl.volume
            ts3m += (vl.close_time-vl.open_time)
            if ts3m > datetime.timedelta(seconds=180):
                break
        if vol3m > 9*self.median_vol:
            is_high_vol_3m = True
        else:
            is_high_vol_3m = False
        self.is_high_vol = is_high_vol_1m | is_high_vol_3m
        #print(vlines[-1])
        if self.trade_speed > self.trade_speed_thresh:
            self.is_high_trade_speed = True
        else:
            self.is_high_trade_speed = False

        if self.is_price_going_down and not self.is_price_going_up and self.is_high_vol and self.is_high_trade_speed:
            self.has_long_liquidation = True
            self.long_liquidation_ts = datetime.datetime.now(tz=MY_TZ)
            print('Long Liquidation:', self.long_liquidation_ts)

        if self.is_price_going_up and not self.is_price_going_down and self.is_high_vol and self.is_high_trade_speed:
            self.has_short_liquidation = True
            self.short_liquidation_ts = datetime.datetime.now(tz=MY_TZ)
            print('Short Liquidation:', self.short_liquidation_ts)

        dt_now = datetime.datetime.now(tz=MY_TZ)
        #lasting_thresh = datetime.timedelta(minutes=5)
        if self.long_liquidation_ts:
            if dt_now - self.long_liquidation_ts > lasting_thresh:
                self.has_long_liquidation = False
                self.long_liquidation_ts = None
        else:
            self.has_long_liquidation = False
            self.long_liquidation_ts = None

        if self.short_liquidation_ts:
            if dt_now - self.short_liquidation_ts > lasting_thresh:
                self.has_short_liquidation = False
                self.short_liquidation_ts = None
        else:
            self.has_short_liquidation = False
            self.short_liquidation_ts = None

    # def update_market_status(self):
    #     '''check market status'''
    #     kline_1m = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=Interval.MINUTE)
    #     if len(kline_1m) < 20:
    #         return
    #     # check bull market
    #     self.check_gain_slip(count=3)
    #     #self.is_climb = self.check_climb()
    #     #self.is_surge = self.check_surge()
    #
    #     # check bear market
    #     self.is_slip = self.check_slip()
    #     self.is_retreat = self.check_retreat()
    #     self.is_slump = self.check_slump()
    #
    #     # check hover market
    #     self.is_hover = self.check_hover()

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
                                                                              end=None, interval=interval)
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
        #klines = self.kqg.get_bars(vt_symbol=self.vt_symbol, interval=interval)
        #print(len(self.spread_vol1), spread_vol1, spread_vol2, klines[-1].open_time, klines[-1].datetime)

    def update_variable(self):
        if self.timer_count > 10:
            self.timer_count = int(self.timer_count)
            self.min_invest = float(self.min_invest)
            self.max_invest = float(self.max_invest)
            self.total_invest = float(self.total_invest)
            self.pos = float(np.round(self.pos, 3))
            #self.median_vol = float(np.round(self.median_vol, 2))
            self.median_vol_100 = float(np.round(self.median_vol_100, 2))
            self.median_vol_1000 = float(np.round(self.median_vol_1000, 2))

            if self.stop_loss_price:
                self.stop_loss_price = float(np.round(self.stop_loss_price, 2))
            if self.take_profit_price:
                self.take_profit_price = float(np.round(self.take_profit_price, 2))

    # def re_connect(self, filepath: str, gateway_name: str):
    #     setting = load_json(os.path.join(filepath, f'connect_{gateway_name.lower()}.json'))
    #     self.cta_engine.main_engine.connect(setting, gateway_name)

    def re_connect(self, timeout=20):
        if self.last_trade:
            datetime_now = datetime.datetime.now()
            datetime_last = self.last_trade.datetime
            if datetime_now - datetime_last > datetime.timedelta(seconds=timeout):
                gateway = self.cta_engine.main_engine.get_gateway(gateway_name=self.exchange)
                gateway.close()
                gateway.market_ws_api.on_disconnected()
                gateway.trade_ws_api.on_disconnected()

        # self.gateway.write_log("交易Websocket API失去连接")
        # # self.gateway.close()
        # # self.gateway.trade_ws_api.stop()
        #
        # self.disconnect_count += 1
        # time.sleep(10 * (self.disconnect_count + 1))
        # if self.disconnect_count > 5:
        #     time.sleep(300)
        #     self.disconnect_count = 0
        #
        # self.login()
        # self.connect(key=self.key, secret=self.secret, proxy_host=self.proxy_host, proxy_port=self.proxy_port)
        #
        # for symbol in self.symbols:
        #     self.gateway.write_log(f"Trade Subscribe {symbol}")
        #     req = SubscribeRequest(symbol=symbol, exchange=Exchange.HUOBI)
        #     self.subscribe(req=req)
        # self.subscribe_account_update()
        #
        # if self.last_trade:
        #     datetime_now = datetime.datetime.now()
        #     datetime_last = self.last_trade.datetime
        #     if datetime_now - datetime_last > datetime.timedelta(seconds=timeout):
        #         self.cta_engine.re_connect(self.strategy_name)

    def on_timer(self):
        '''
        if data init, update market trades for vline queue generator, vline generator
        '''
        if not self.is_data_inited:
            return

        if self.first_time:
            self.update_market_trade(time_step=1)
            self.update_invest_limit()
            #self.update_price_gain_speed_vline(num_vline=3, time_step=1)
            #self.update_spread_vol(time_step=10)
            #self.update_spread(time_step=10)
            #self.update_vol()
            #self.detect_liquidation()
            #self.update_invest_limit()
            self.update_volume_feature()
            self.update_vline_feature()
            self.first_time = False

        self.update_market_trade(time_step=1)
        self.update_volume_feature()
        self.update_vline_feature()
        #self.update_vol()
        #self.update_spread_vol_vline()
        #self.update_price_gain_speed_vline(num_vline=3, time_step=1)
        #self.update_spread_vol(time_step=10)
        #self.update_spread(time_step=10)
        self.release_trading_quota(timestep=5)

        if self.timer_count % 1 == 0 and self.timer_count > 10:
            self.sending_count = 0
            if self.last_trade:
                price = self.last_trade.price
                #self.detect_liquidation()
                self.make_decision(price=price)

        if self.timer_count % 10 == 0 and self.timer_count > 10:
            # if no market trade, re-subscribe
            self.re_connect()
            if False:
                dt_now = datetime.datetime.now()
                dt_trade = self.last_trade.datetime.replace(tzinfo=None)
                td = dt_now - dt_trade
                print(td, dt_now, dt_trade)
                if td > datetime.timedelta(minutes=1):
                    self.re_connect(filepath='/home/lir0b/.vntrader', gateway_name=self.exchange)
                    contract = self.cta_engine.main_engine.get_contract(self.vt_symbol)
                    if contract:
                        req = SubscribeRequest(symbol=contract.symbol, exchange=contract.exchange)
                        self.cta_engine.main_engine.subscribe(req, contract.gateway_name)
                        self.write_log(f"行情订阅{self.vt_symbol}")
                        self.subscribe_quota = False
                    else:
                        self.write_log(f"行情订阅失败，找不到合约{self.vt_symbol}")

            if False and self.test_count < 3:
                self.test_trade()
                #self.test_count += 1

        if self.timer_count % 60 == 0 and self.timer_count > 10:
            print(datetime.datetime.now(tz=MY_TZ))
            #self.update_volume_feature()
            #self.update_vol()
            #self.update_break_count()

        if self.timer_count % 60 == 0 and self.timer_count > 10:
            #self.update_invest_position()
            self.update_invest_limit()
            #now = datetime.datetime.now(tz=MY_TZ)
            #if now - self.last_trade.datetime > datetime.timedelta(minutes=10):
            #    self.trading = False

        if self.timer_count % 1800 == 0 and self.timer_count > 10:
            self.cancel_all()

        self.timer_count += 1
        self.update_variable()
        self.put_event()
