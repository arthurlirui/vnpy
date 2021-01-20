from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.object import VlineData, BarData, PositionData, MarketEventData
from vnpy.trader.engine import BaseEngine
from vnpy.app.algo_trading import AlgoTemplate
import math
from vnpy.trader.utility import VlineGenerator, MarketEventGenerator, VlineQueueGenerator
from pprint import pprint
from vnpy.trader.object import HistoryRequest
from typing import Any, Callable

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
    market_params = {'btcusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0},
                     'ethusdt': {'vline_vol': 10, 'vline_vol_list': usdt_vol_list, 'bin_size': 1.0}}

    parameters = ['vline_vol', 'vline_num', 'vline_vol_list']
    vline_vol = 10
    vline_num = 5
    vline_vol_list = [10, 40, 160, 640, 2560, 10240, 40960]
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

        self.symbols = ['btcusdt']
        self.exchanges = ['HUOBI']

        #self.is_vline_inited = False
        self.on_init()
        #self.is_vline_inited = True

        # init setting
        #pprint(setting)
        #self.init_setting(setting=setting)

        # init parameters
        #self.init_parameter(parameters=self.parameters)
        # could load parameters from xml files
        #self.init_parameter(parameters=self.parameters)

        # Variables
        #self.timer_count = 0
        #self.vt_orderid = ""
        #self.pos = 0
        #self.last_tick = None

        if False:
            # init all market data
            for s in self.symbols:
                for ex in self.exchanges:
                    self.subscribe(s+'.'+ex)

        # init vline generator
        if False:
            self.vg = {}
            self.vline_buf = {}
            self.init_vline_generator()

        if False:
            pass


        # inti market event generator
        #self.meg = None
        #self.init_market_event_generator()

        # system variables
        #self.last_tick = None
        #self.last_vline = None
        #self.last_market_event = None

        # cache data from market
        #self.ticks = []
        #self.vlines = []
        #self.market_events = []
        #self.vline_len = 0

        # init local balance and order from market
        #self.put_parameters_event()
        #self.put_variables_event()


    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        #self.load_bar(10)

        self.vqg = {}
        self.init_vline_queue_generator()

        self.is_vline_inited = False
        self.init_data()
        self.is_vline_inited = True

        for vts in self.vqg:
            for vol in self.vqg[vts].vol_list:
                print(vts, vol, self.vqg[vts].get_vq(vol).dist)

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
        #self.load_tick(2, callback=self.on_init_tick)
        self.load_market_trade(callback=self.on_init_market_trade)
        self.load_bar(2, interval=Interval.MINUTE, callback=self.on_init_vline_queue)

    def load_tick(self, days: int, callback: Callable):
        """
        Load historical tick data for initializing strategy.
        """
        self.cta_engine.load_tick(self.vt_symbol, days, callback=callback)

    def load_market_trade(self, callback: Callable):
        self.cta_engine.load_market_trade(self.vt_symbol, callback=callback)

    def on_init_tick(self, tick: TickData):
        print(tick)

    def on_init_market_trade(self, trade: TradeData):
        for vt_symbol in self.vqg:
            if trade.vt_symbol == vt_symbol:
                self.vqg[vt_symbol].init_by_trade(trade=trade)

    def on_init_vline_queue(self, bar: BarData):
        # init load_bar data is from reversed order
        for vt_symbol in self.vqg:
            if bar.vt_symbol == vt_symbol:
                self.vqg[vt_symbol].init_by_kline(bar=bar)

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
                #vline_vol = self.market_params[s]['vline_vol']
                vline_vol_list = self.market_params[s]['vline_vol_list']
                bin_size = self.market_params[s]['bin_size']
                self.vqg[vt_sym] = VlineQueueGenerator(vol_list=vline_vol_list, bin_size=bin_size, save_data=True)

    def init_vline_generator(self):
        for s in self.symbols:
            for ex in self.exchanges:
                vt_sym = s+'.'+ex
                vline_vol = self.market_params[s]['vline_vol']
                vline_vol_list = self.market_params[s]['vline_vol_list']
                self.vg[vt_sym] = VlineGenerator(on_vline=self.on_vline, vol_list=vline_vol_list)
                #self.vg[vt_sym].multi_vline_setting(on_multi_vline=self.on_multi_vline, vol_list=vline_vol_list)

        #self.vg = VlineGenerator(on_vline=self.on_vline, vol=self.vline_vol)
        #self.vg.multi_vline_setting(on_multi_vline=self.on_multi_vline, vol_list=self.vline_vol_list)

        # light copy of vline_buf from vline generator
        #self.last_vline = self.vg[self.vt_symbol].vline
        #self.vlines = self.vg[self.vt_symbol].vlines
        #self.vline_buf = self.vg[self.vt_symbol].vline_buf

    def init_market_event_generator(self):
        #self.meg = MarketEventGenerator(on_event=self.on_event)
        pass

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        update list:
        1. update tick: last_tick, vline_buf
        2. update vline: (1) new vline (2) multi vline
        """
        if not self.is_vline_inited:
            pass



        if not tick.last_price:
            return

        # update tick
        #print(tick)
        self.last_tick = tick

        # update vline for different pairs
        #self.vg[tick.vt_symbol].update_tick(tick=tick)
        #print(tick)
        #print(self.vg[tick.vt_symbol].vline)

        #self.last_vline = self.vg[self.vt_symbol].vline

        #for v in self.vg.vline_buf:
        #    if self.vg.vline_buf[v].volume < 0.9*v:
        #        return

        """"""
        #self.last_tick = tick
        #self.write_log(f"Tick: {tick.last_price} TS: {tick.datetime}")

    def on_market_trade(self, trade: TradeData):
        if self.is_vline_inited:
            #self.vg[trade.vt_symbol].update_market_trades(trade=trade)
            self.vqg[trade.vt_symbol].update_market_trades(trade=trade)
            for vb in self.vqg[trade.vt_symbol].vol_list:
                print(vb, self.vqg[trade.vt_symbol].get_vq(vb).vol)
                pass

            if False and trade.vt_symbol == 'btcusdt.HUOBI':
                #print(len(self.vg[trade.vt_symbol].trades), trade)
                #print(self.vg[trade.vt_symbol].vline)
                for vb in self.vqg[trade.vt_symbol].vq:
                    print(vb, self.vqg[trade.vt_symbol].vq[vb].vol)
                    #if not self.vqg[trade.vt_symbol].vline_buf[vb].is_empty():
                        #print(vb, len(self.vqg[trade.vt_symbol].vlines[vb]), self.vqg[trade.vt_symbol].vline_buf[vb])
                        #print(f'Size:{len(self.vg[trade.vt_symbol].vlines[vb])} Vol:{vb}')
                print()

    def on_kline(self, bar: BarData):
        self.vqg[bar.vt_symbol].update_kline(bar=bar)

    def on_vline(self, vline: VlineData, vol: int):
        '''
        1. update vline and vline_buf
        2. update market event
        3. update market action
        4. update account
        '''
        #self.last_vline = self.vg[self.vt_symbol].vline
        #self.vlines = self.vg.vlines
        #self.vline_buf = self.vg.vline_buf
        #print(self.last_vline)

        print(vol, vline)
        #if len(self.vg[self.vt_symbol].vlines) > 0:
        #    print(len(self.vg[self.vt_symbol].vlines), self.vg[self.vt_symbol].vlines[-1])

        # update market event
        #self.update_event()

        # update position
        #self.update_position()

    def on_multi_vline(self, vline: VlineData, vol: int):
        pass

    def on_timer(self):
        """"""
        if not self.last_tick:
            return

        self.timer_count += 1
        if self.timer_count < self.interval:
            self.put_variables_event()
            return
        self.timer_count = 0
        self.pos += 1
        #print(self.last_vline)

        #if self.vt_orderid:
        #    self.cancel_all()

        # # Calculate target volume to buy and sell
        # target_buy_distance = (
        #     self.price - self.last_tick.ask_price_1) / self.step_price
        # target_buy_position = math.floor(
        #     target_buy_distance) * self.step_volume
        # target_buy_volume = target_buy_position - self.pos
        #
        # # Calculate target volume to sell
        # target_sell_distance = (
        #     self.price - self.last_tick.bid_price_1) / self.step_price
        # target_sell_position = math.ceil(
        #     target_sell_distance) * self.step_volume
        # target_sell_volume = self.pos - target_sell_position
        #
        # # Buy when price dropping
        # if target_buy_volume > 0 and False:
        #     self.vt_orderid = self.buy(
        #         self.vt_symbol,
        #         self.last_tick.ask_price_1,
        #         min(target_buy_volume, self.last_tick.ask_volume_1)
        #     )
        # # Sell when price rising
        # elif target_sell_volume > 0 and False:
        #     self.vt_orderid = self.sell(
        #         self.vt_symbol,
        #         self.last_tick.bid_price_1,
        #         min(target_sell_volume, self.last_tick.bid_volume_1)
        #     )

        # Update UI
        self.put_variables_event()

    def on_order(self, order: OrderData):
        """"""
        if not order.is_active():
            self.vt_orderid = ""
            self.put_variables_event()

    def on_trade(self, trade: TradeData):
        """"""
        if trade.direction == Direction.LONG:
            self.pos += trade.volume
        else:
            self.pos -= trade.volume

        self.put_variables_event()
