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


class TestStrategy(CtaTemplate):
    """"""
    author = "Arthur"

    test_trigger = 10

    tick_count = 0
    test_all_done = False

    parameters = ["test_trigger"]
    variables = ["tick_count", "test_all_done"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(TestStrategy, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.test_funcs = [
            self.test_market_order,
            self.test_limit_order,
            self.test_cancel_all,
            self.test_stop_order
        ]
        # engine is backtesting or cta_engine
        self.cta_engine = cta_engine

        self.last_tick = None
        self.last_vline = None

        # history data from market
        #self.ticks = []
        self.vlines = []

        self.tick_df = None
        self.vline_df = None

        self.vg = VlineGenerator(on_vline=self.on_vline, vol=10)

        vol_list = [10, 20, 40]
        vline_buf = {}
        for v in vol_list:
            vline_buf[v] = []
        func3 = lambda x, y: vline_buf[y].append(x)
        self.vg.multi_vline_setting(on_multi_vline=func3, vol_list=vol_list)

        # init position data here
        self.balance_dict = {}
        self.first_symbol = 'BTC'
        self.second_symbol = 'USDT'

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        # init account balance here
        self.on_init_balance()

    def on_init_balance(self):
        rec_dict = self.cta_engine.init_account()
        self.balance_dict = rec_dict

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
        else:
            self.last_tick = tick

        # update tick here
        self.vg.update_tick(tick=tick)

        self.tick_count += 1
        if self.tick_count >= self.test_trigger:
            self.tick_count = 0

        #self.update_market_state()
        #self.update_position_state()
        vol = 0.1
        #print(len(self.vg.vlines), len(self.vlines))
        #print(len(self.vg.ticks), len(self.ticks))
        print('TS:%.3f LenTS:%d' % (self.vg.last_teeter_signal, len(self.vg.teeter_signals)))
        if self.check_long_cond():
            # check balance
            buy_value = vol * self.last_tick.last_price
            if self.balance_dict[self.second_symbol].available >= buy_value:
                # check position limit
                self.cta_engine.send_order(direction=Direction.LONG, price=self.last_tick.last_price,
                                           offset=Offset.NONE, volume=vol, stop=False, lock=False)
                self.balance_dict[self.second_symbol].available -= buy_value
                self.balance_dict[self.second_symbol].frozen += buy_value
                print('Order BUY: P:%.3f V:%.3f' % (self.last_tick.last_price, buy_value))
                print(self.balance_dict[self.second_symbol])
                print()
        elif self.check_short_cond():
            sell_value = vol
            if self.balance_dict[self.first_symbol].available >= sell_value:
                self.cta_engine.send_order(direction=Direction.SHORT, price=self.last_tick.last_price,
                                           offset=Offset.NONE, volume=vol, stop=False, lock=False)
                self.balance_dict[self.first_symbol].available -= sell_value
                self.balance_dict[self.first_symbol].frozen += sell_value
                print('Order SELL: P:%.3f V:%.3f' % (self.last_tick.last_price, sell_value))
                print(self.balance_dict[self.first_symbol])
                print()
        self.put_event()

    def check_long_cond(self):
        long_cond = False
        if len(self.vlines) > 10:
            pass
        #if self.last_tick.last_price < 4500:
        #    long_cond = True
        return long_cond

    def check_short_cond(self):
        short_cond = False
        if self.last_tick.last_price > 6000:
            short_cond = True
        return short_cond

    def check_balance(self):
        pass

    def check_target_position(self):
        pass

    def on_vline(self, vline: VlineData):
        """
        Callback of new vline update
        1. update current position
        :param vline:
        :return:
        """
        self.vlines.append(vline)

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

