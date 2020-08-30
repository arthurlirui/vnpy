from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData
)

from time import time
from vnpy.trader.object import VlineData, BarData, PositionData, MarketEventData
from vnpy.trader.utility import VlineGenerator, MarketEventGenerator
from vnpy.trader.object import Direction, Offset

import pandas as pd
from pprint import pprint
import numpy as np
from datetime import date, datetime, timedelta


class TestStrategy(CtaTemplate):
    """"""
    author = "Arthur"
    test_trigger = 10
    tick_count = 0
    test_all_done = False
    parameters = ["test_trigger"]
    variables = ["tick_count", "test_all_done"]

    default_parameters = {'vline_vol': 5,
                          'vline_vol_list': [10, 20, 40, 80, 160, 320],
                          'vline_min_num': 10,
                          'vline_max_num': 1000,
                          'ttb_min_num': 10,
                          'first_symbol': 'BTC',
                          'second_symbol': 'USDT',
                          'min_trade_vol': 0.01,
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

        # market event generator
        self.meg = None
        self.init_market_event_generator()

        # system variables
        self.last_tick = None
        self.last_vline = None
        self.last_market_event = None

        # history data from market
        self.ticks = []
        self.vlines = []
        self.market_events = []
        self.vline_len = 0

    def init_parameter(self, parameters: dict = {}):
        for key in parameters:
            if key in self.parameters:
                self.parameters[key] = parameters[key]

        for name in self.parameters:
            setattr(self, name, self.parameters[name])

    def init_vline_generator(self):
        # init vline
        self.vg = VlineGenerator(on_vline=self.on_vline, vol=self.vline_vol)
        self.vg.multi_vline_setting(on_multi_vline=self.on_multi_vline,
                                    vol_list=self.vline_vol_list)

        # light copy of vline_buf from vline generator
        self.last_vline = self.vg.vline
        self.vlines = self.vg.vlines
        self.vline_buf = self.vg.vline_buf

    def init_market_event_generator(self):
        self.meg = MarketEventGenerator(on_event=self.on_event)

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
        update list:
        1. update tick: last_tick, vline_buf
        2. update vline: (1) new vline (2) multi vline
        """
        if not tick.last_price:
            return

        # update tick
        self.last_tick = tick
        self.vg.update_tick(tick=tick)
        for v in self.vg.vline_buf:
            if self.vg.vline_buf[v].volume < 0.9*v:
                return

        # update vline
        if not self.vline_len == len(self.vg.vlines):
            self.on_vline()
            self.vline_len = len(self.vg.vlines)

        # update market event

        # update market action


        vol = self.min_trade_vol
        price = self.last_tick.last_price

        state = self.check_breaking()
        if state['high_break'] >= 4:
            pass
        if state['low_break'] >= 4:
            pass

        # give trading parameters
        params = self.generate_trade_parameter()
        direction, price, vol = params['direction'], params['price'], params['vol']
        if not direction:
            return

        # avoid place order frequently
        place_new_order = self.check_order()
        if not place_new_order:
            return

        # if has enough balance
        if not self.check_balance(direction=direction, price=price, vol=vol):
            return

        # if enough position
        if not self.check_position(direction=direction):
            return

        # everything is ready send order to engine
        self.cta_engine.send_order(direction=direction, price=price, offset=Offset.NONE, volume=vol, stop=False, lock=False)

        if False:
            print('Order %s: P:%.3f V:%.3f Pos:%.3f N:%d' % (direction,
                                                             self.last_tick.last_price,
                                                             vol,
                                                             self.position_dict[self.first_symbol],
                                                             len(self.cta_engine.active_limit_orders)))
            print(self.last_vline)
            for v in self.vg.vline_buf:
                print(self.vg.vline_buf[v])
            pprint(params)
            print()
        self.update_balance(direction=direction, price=price, vol=vol)
        # print('Pos:%.8f' % self.position_dict[self.first_symbol],
        #      'OrderN:', len(self.cta_engine.active_limit_orders))



        # if direction == Direction.LONG:
        #
        #     # buy_value = price * vol
        #     #vol = params[Direction.LONG]['vol']
        #     #price = params[Direction.LONG]['price']
        #
        #     self.cta_engine.send_order(direction=Direction.LONG, price=price,
        #                                offset=Offset.NONE, volume=vol, stop=False, lock=False)
        #
        #     print(self.last_vline)
        #     print(self.vg.vline_buf[640])
        #     print('Order BUY: P:%.3f V:%.3f Pos:%.3f N:%d' % (self.last_tick.last_price+10, vol,
        #                                                       self.position_dict[self.first_symbol],
        #                                                       len(self.cta_engine.active_limit_orders)))
        #     self.update_balance(Direction.LONG, price, vol)
        #     # print('Pos:%.8f' % self.position_dict[self.first_symbol],
        #     #      'OrderN:', len(self.cta_engine.active_limit_orders))
        #     print()
        #
        # if direction == Direction.SHORT:
        #     if not self.check_balance(Direction.SHORT, price, vol):
        #         return
        #     if not self.check_position(Direction.SHORT):
        #         return
        #     #vol = params[Direction.SHORT]['vol']
        #     #price = params[Direction.SHORT]['price']
        #
        #     self.cta_engine.send_order(direction=Direction.SHORT, price=price,
        #                                offset=Offset.NONE, volume=vol, stop=False, lock=False)
        #
        #     print(self.last_vline)
        #     print(self.vg.vline_buf[640])
        #     print('Order SELL: P:%.3f V:%.3f Pos:%.3f N:%d' % (self.last_tick.last_price-10, vol,
        #                                                        self.position_dict[self.first_symbol],
        #                                                        len(self.cta_engine.active_limit_orders)))
        #     self.update_balance(Direction.SHORT, price, vol)
        #     # print('Pos:%.8f' % self.position_dict[self.first_symbol],
        #     #      'OrderN:', len(self.cta_engine.active_limit_orders))
        #     print()

        self.put_event()

    def check_trade_cond(self):
        '''
        1. check price dist
        2. check short term teeterboard feature
        '''
        direction = None
        last_price = self.last_tick.last_price
        buy_rank = 0
        sell_rank = 0

        # main parameters
        weights = [0.1, 0.1, 0.2, 0.2, 0.3, 0.3, 0.4, 0.4]
        low_price_thresh = 0.05
        high_price_thresh = 0.95
        ratio_thresh = 0.1

        for i, v in enumerate(self.vg.dist_buf):
            less_vol = self.vg.dist_buf[v].less_vol(price=last_price)
            total_vol = self.vg.dist_buf[v].total_vol()
            if total_vol > 5:
                ratio = less_vol / total_vol
                if ratio > high_price_thresh:
                    sell_rank += weights[i]
                if ratio < low_price_thresh:
                    buy_rank += weights[i]

        if sell_rank > ratio_thresh and sell_rank > buy_rank:
            direction = Direction.SHORT
        if buy_rank > ratio_thresh and buy_rank > sell_rank:
            direction = Direction.LONG
        # if sell_rank > ratio_thresh:
        #     direction = Direction.SHORT
        # if buy_rank > ratio_thresh:
        #     direction = Direction.LONG
        return direction

    def check_long_cond(self):
        long_cond = False
        # check price dist
        #if len(self.vg.teeter_signals) > self.ttb_min_num:
        tmp = np.array(self.vg.teeter_signals[-self.ttb_min_num:])
        ttb_strength = np.sum(tmp[tmp < 0])
        #print(ttb_strength)
        if ttb_strength < -0.1:
            long_cond = True
        return long_cond

    def check_short_cond(self):
        short_cond = False
        #if len(self.vg.teeter_signals) > self.ttb_min_num:
        tmp = np.array(self.vg.teeter_signals[-self.ttb_min_num:])
        ttb_strength = np.sum(tmp[tmp > 0])
        #print(ttb_strength)
        if ttb_strength > 0.1:
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
        #print(self.balance_dict[self.first_symbol])
        #print(self.balance_dict[self.second_symbol])

    def update_position(self):
        '''
        1. teeterboard feature: receive multiple neg or pos teeter_signal
        2. price distribution:
        '''
        #last_price = self.last_tick.last_price
        #buy_rank = 0
        #sell_rank = 0

        low_price_thresh = 0.1
        #high_price_thresh = 0.9
        #ratio_thresh = 0.05

        # main parameters
        pos_weights = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1]
        price = self.last_vline.avg_price
        max_pos = self.max_position
        pos = 0
        for i, v in enumerate(self.vg.dist_buf):
            less_vol = self.vg.dist_buf[v].less_vol(price=price)
            total_vol = self.vg.dist_buf[v].total_vol()
            if total_vol > 0:
                ratio = less_vol / total_vol
                if ratio < low_price_thresh and total_vol >= 10:
                    pos = pos_weights[i]

        if pos > 0:
            self.position_dict[self.first_symbol] = pos * max_pos
        else:
            if self.position_dict[self.first_symbol] > 0:
                self.position_dict[self.first_symbol] -= self.position_constant_decrease

        # position limit
        self.position_dict[self.first_symbol] = min([self.max_position, self.position_dict[self.first_symbol]])
        self.position_dict[self.first_symbol] = max([self.min_position, self.position_dict[self.first_symbol]])

    def check_order(self, price_thresh=20, time_thresh=timedelta(minutes=3)):
        price = self.last_tick.last_price
        datetime = self.last_tick.datetime
        place_new_order = True
        count = 0
        for id in self.cta_engine.active_limit_orders:
            order = self.cta_engine.active_limit_orders[id]
            if order.symbol == self.last_tick.symbol and order.exchange == self.last_tick.exchange:
                if abs(order.price-price) < price_thresh:
                    place_new_order = False
                    break
                if datetime - order.datetime < time_thresh:
                    place_new_order = False
        return place_new_order

    def update_event(self):
        self.meg.update_event(self.vlines)
        # if not self.meg.gain.is_empty():
        #     print(self.meg.gain)
        # if not self.meg.slip.is_empty():
        #     print(self.meg.slip)
        # print()

    def update_action(self):
        pass

    def generate_trade_parameter(self, setting={}):
        last_price = self.last_tick.last_price
        params = {'direction': None, 'price': None, 'vol': None}
        default_setting = {'high_price_thresh': 0.99, 'low_price_thresh': 0.01}
        high_price_thresh = default_setting['high_price_thresh']
        low_price_thresh = default_setting['low_price_thresh']

        direction = None
        vol = 0
        price = None
        vol_step = self.min_trade_vol

        for i, v in enumerate(self.vg.dist_buf):
            less_vol = self.vg.dist_buf[v].less_vol(price=last_price)
            total_vol = self.vg.dist_buf[v].total_vol()
            if total_vol > v*0.9:
                ratio = less_vol / total_vol
                if ratio > high_price_thresh:
                    direction = Direction.SHORT
                    vol += vol_step
                    price = last_price

                if ratio < low_price_thresh:
                    direction = Direction.LONG
                    vol += vol_step
                    price = last_price

        params['direction'] = direction
        params['price'] = price
        params['vol'] = vol
        return params

    def check_position(self, direction: Direction):
        is_valid = False
        if direction == Direction.LONG:
            if self.balance_dict[self.first_symbol].volume < self.position_dict[self.first_symbol]:
                is_valid = True
        elif direction == Direction.SHORT:
            if self.balance_dict[self.first_symbol].volume > self.position_dict[self.first_symbol]:
                is_valid = True
        return is_valid

    def on_vline(self, vline: VlineData = None):
        '''
        1. update vline and vline_buf
        2. update market event
        3. update market action
        4. update account
        '''
        self.last_vline = self.vg.vline
        self.vlines = self.vg.vlines
        self.vline_buf = self.vg.vline_buf

        # update market event
        self.update_event()

        # update position
        self.update_position()

    def on_event(self, me: MarketEventData):
        nme = MarketEventData(symbol=me.symbol,
                              exchange=me.exchange,
                              gateway_name=me.gateway_name,
                              open_time=me.open_time,
                              close_time=me.close_time)
        nme.event = me.event
        self.market_events.append(nme)

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

    def update_market_event(self):
        med = MarketEventData(symbol=v.symbol, exchange=v.exchange, gateway_name=v.gateway_name, open_time=v.open_time,
                              close_time=v.close_time)
        dp_avg = v.avg_price - pv.avg_price
        dp_high = v.high_price - pv.high_price
        dp_low = v.low_price - pv.low_price

        if dp_avg >= 0 and dp_high >= 0 and dp_low >= 0:
            med.event = MarketEvent.GAIN
        elif dp_avg <= 0 and dp_high <= 0 and dp_low <= 0:
            med.event = MarketEvent.SLIP
        else:
            med.event = MarketEvent.HOVER
        print(med)
        mel.append(med)

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

    def check_breaking(self):
        price = self.last_tick.last_price
        high_price_thresh = 1
        low_price_thresh = 0
        state = {'high_break': 0, 'low_break': 0}
        for i, v in enumerate(self.vg.dist_buf):
            max_price = max(self.vg.dist_buf[v].dist.keys())
            min_price = min(self.vg.dist_buf[v].dist.keys())
            if price <= min_price+1:
                state['low_break'] += 1
            if price >= max_price-1:
                state['high_break'] += 1
        return state

