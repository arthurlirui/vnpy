from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData
)

from time import time
from vnpy.trader.object import VlineData, BarData, PositionData
from vnpy.trader.utility import VlineGenerator
from vnpy.trader.object import Direction, Offset

import pandas as pd
from pprint import pprint
import numpy as np


class TestStrategy(CtaTemplate):
    """"""
    author = "Arthur"
    test_trigger = 10
    tick_count = 0
    test_all_done = False
    parameters = ["test_trigger"]
    variables = ["tick_count", "test_all_done"]

    default_parameters = {'vline_vol': 5,
                          'vline_vol_list': [10, 20, 40],
                          'vline_min_num': 10,
                          'vline_max_num': 1000,
                          'ttb_min_num': 10,
                          'first_symbol': 'BTC',
                          'second_symbol': 'USDT',
                          'min_trade_vol': 0.005,
                          'max_trade_vol': 0.1,
                          'total_position': 10,
                          'position_step': 0.1,
                          'min_position': 0.1,
                          'max_position': 2,
                          'init_position': 0,
                          'position_constant_decrease': 0.01}
    parameters = default_parameters

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(TestStrategy, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.test_funcs = [
            self.test_market_order,
            self.test_limit_order,
            self.test_cancel_all,
            self.test_stop_order
        ]

        # select backtest engine or real market engine
        self.cta_engine = cta_engine

        # init parameters
        parameters = setting['parameters']
        self.init_parameter(parameters=parameters)
        pprint(self.parameters)

        # vline generator
        self.vg = None
        self.vline_buf = {}
        self.init_vline_generator()

        # system variables
        self.last_tick = None
        self.last_vline = None

        # history data from market
        self.ticks = []
        self.vlines = []
        self.vline_len = 0

        #self.tick_df = None
        #self.vline_df = None

        #self.vg = VlineGenerator(on_vline=self.on_vline, vol=10)
        # init system
        #self.balance_dict = {}
        #self.first_symbol = None
        #self.second_symbol = None
        #self.symbol = None

        # init vline
        #self.vol_list = []

    def init_parameter(self, parameters: dict = {}):
        for key in parameters:
            if key in self.parameters:
                self.parameters[key] = parameters[key]

        for name in self.parameters:
            setattr(self, name, self.parameters[name])
            #print(getattr(self, name))

        # init frequently used parameter for system

        # self.first_symbol = self.parameters['system']['first_symbol']
        # self.second_symbol = self.parameters['system']['second_symbol']
        # self.symbol = self.first_symbol+self.second_symbol
        # init frequently used parameter for vline
        # self.vol_list = self.parameters['vline']['vline_vol_list']

    def init_vline_generator(self):
        # init vline
        self.vg = VlineGenerator(on_vline=self.on_vline, vol=self.vline_vol)
        self.vg.multi_vline_setting(on_multi_vline=self.on_multi_vline, vol_list=self.vline_vol_list)

        # light copy of vline_buf from vline_generator
        self.last_vline = self.vg.vline
        self.vlines = self.vg.vlines
        self.vline_buf = self.vg.vline_buf

    def print_parameter(self):
        pass

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        # init account balance here
        self.on_init_balance()
        self.on_init_position()

    def on_init_balance(self):
        self.balance_dict = self.cta_engine.init_account()

    def on_init_position(self):
        self.position_dict = {self.first_symbol: self.init_position}

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

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        if not tick.last_price:
            return

        # update tick
        self.last_tick = tick
        self.vg.update_tick(tick=tick)

        # update vline
        if not self.vline_len == len(self.vg.vlines):
            self.on_vline()

        self.tick_count += 1
        if self.tick_count >= self.test_trigger:
            self.tick_count = 0

        #self.update_market_state()
        #self.update_position_state()

        #print(len(self.vg.vlines), len(self.vlines))
        #print(len(self.vg.ticks), len(self.ticks))
        #print('TS:%.3f LenTS:%d' % (self.vg.last_teeter_signal, len(self.vg.teeter_signals)))
        #print(len(self.vg.vlines))
        #if len(self.vg.vlines) > 0:
        #    print(len(self.vg.vlines), self.vg.vlines[-1])

        # if len(self.vlines) > 0:
        #     print(len(self.vlines), self.vlines[-1])
        #     print()
        # if True:
        #     for key in self.vline_buf:
        #         if not self.vline_buf[key].is_empty():
        #             print(self.vline_buf[key])
        #     print()
        vol = self.min_trade_vol
        price = self.last_tick.last_price
        if self.check_long_cond():
            # check balance
            if not self.check_balance(Direction.LONG, price, vol):
                return
            if not self.check_position(Direction.LONG):
                return
            buy_value = price * vol
            self.cta_engine.send_order(direction=Direction.LONG, price=self.last_tick.last_price,
                                       offset=Offset.NONE, volume=vol, stop=False, lock=False)
            self.update_balance(Direction.LONG, price, vol)
            print('Order BUY: P:%.3f V:%.3f' % (self.last_tick.last_price, buy_value))
            print(self.balance_dict[self.second_symbol])
            print('Pos:%.8f' % self.position_dict[self.first_symbol])
            print()
        elif self.check_short_cond():
            if not self.check_balance(Direction.SHORT, price, vol):
                return
            if not self.check_position(Direction.SHORT):
                return
            sell_value = vol
            self.cta_engine.send_order(direction=Direction.SHORT, price=self.last_tick.last_price,
                                       offset=Offset.NONE, volume=vol, stop=False, lock=False)
            self.update_balance(Direction.SHORT, price, vol)
            print('Order SELL: P:%.3f V:%.3f' % (self.last_tick.last_price, sell_value))
            print(self.balance_dict[self.first_symbol])
            print('Pos:%.8f' % self.position_dict[self.first_symbol])
            print()
        self.put_event()

    def check_long_cond(self):
        long_cond = False
        if len(self.vg.teeter_signals) > self.ttb_min_num:
            tmp = np.array(self.vg.teeter_signals[-self.ttb_min_num:-1])
            ttb_signal = np.sum(tmp[tmp < 0])
            if ttb_signal < -0.2:
                long_cond = True
        return long_cond

    def check_short_cond(self):
        short_cond = False
        if len(self.vg.teeter_signals) > self.ttb_min_num:
            tmp = np.array(self.vg.teeter_signals[-self.ttb_min_num:-1])
            ttb_signal = np.sum(tmp[tmp > 0])
            if ttb_signal > 0.2:
                short_cond = True
        return short_cond

    def check_balance(self, direction: Direction, price: float = 0, vol: float = 0):
        is_valid = False
        if direction == Direction.SHORT:
            if self.balance_dict[self.first_symbol].available >= vol:
                is_valid = True
        elif direction == Direction.LONG:
            if self.balance_dict[self.second_symbol].available >= vol*price:
                is_valid = True
        return is_valid

    def update_balance(self, direction: Direction, price: float, vol: float):
        if direction == Direction.LONG:
            self.balance_dict[self.second_symbol].available -= price*vol
            self.balance_dict[self.second_symbol].frozen += price*vol
        elif direction == Direction.SHORT:
            self.balance_dict[self.first_symbol].available -= vol
            self.balance_dict[self.first_symbol].frozen += vol

    def update_position(self):
        '''
        1. receive multiple neg or pos teeter_signal
        2. avg price change ratio
        '''
        cur_avg_price = self.last_vline.avg_price
        strength = 0
        phase = 10
        for p in range(1, phase):
            if len(self.vlines) > p*10:
                vline_tmp = self.vlines[-p*10:-1]
                min_avg_price = min([v.avg_price for v in vline_tmp])
                if cur_avg_price < min_avg_price:
                    strength += self.position_step
        if strength > 0:
            self.position_dict[self.first_symbol] = strength
        else:
            if self.position_dict[self.first_symbol] > 0:
                self.position_dict[self.first_symbol] -= self.position_constant_decrease

        self.position_dict[self.first_symbol] = min([self.max_position,
                                                     self.position_dict[self.first_symbol]])
        self.position_dict[self.first_symbol] = max([self.min_position,
                                                     self.position_dict[self.first_symbol]])

    def check_position(self, direction: Direction):
        is_valid = False
        if direction == Direction.LONG:
            if self.balance_dict[self.first_symbol].volume < self.position_dict[self.first_symbol]:
                is_valid = True
        elif direction == Direction.SHORT:
            if self.balance_dict[self.first_symbol].volume > self.position_dict[self.first_symbol]:
                is_valid = True
        return is_valid

    def check_target_position(self):
        pass

    def on_vline(self, vline: VlineData = None):
        self.last_vline = self.vg.vline
        self.vlines = self.vg.vlines
        self.vline_buf = self.vg.vline_buf
        # update position
        self.update_position()

    def on_multi_vline(self, vline: VlineData, vol: int):
        #print(self.vline_buf[vol])
        pass

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        pass

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        # if in real market: update account info
        # if in virtual testing: manual update balance
        if True:
            if trade.direction == Direction.LONG:
                self.balance_dict[self.first_symbol].volume += trade.volume
                self.balance_dict[self.first_symbol].available += trade.volume

                self.balance_dict[self.second_symbol].volume -= trade.volume * trade.price
                self.balance_dict[self.second_symbol].frozen -= trade.volume * trade.price
            elif trade.direction == Direction.SHORT:
                self.balance_dict[self.second_symbol].volume += trade.volume * trade.price
                self.balance_dict[self.second_symbol].available += trade.volume * trade.price

                self.balance_dict[self.first_symbol].volume -= trade.volume
                self.balance_dict[self.first_symbol].frozen -= trade.volume
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        self.put_event()

    def init_market_state(self):
        pass

    def update_market_state(self):
        pass

    def init_account_state(self):
        pass

    def update_account_state(self):
        pass

    def decision_switch(self):
        pass

    def test_market_order(self):
        """"""
        self.buy(self.last_tick.limit_up, 1)
        self.write_log("执行市价单测试")

    def test_limit_order(self):
        """"""
        self.buy(self.last_tick.limit_down, 1)
        self.write_log("执行限价单测试")

    def test_stop_order(self):
        """"""
        self.buy(self.last_tick.ask_price_1, 1, True)
        self.write_log("执行停止单测试")

    def test_cancel_all(self):
        """"""
        self.cancel_all()
        self.write_log("执行全部撤单测试")

