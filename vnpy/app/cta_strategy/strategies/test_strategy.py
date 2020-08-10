from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData
)

from time import time
from vnpy.trader.object import VlineData, BarData
from vnpy.trader.utility import VlineGenerator
from vnpy.trader.object import Direction, Offset


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
        self.cta_engine = cta_engine
        self.last_tick = None
        self.last_vline = None
        self.vg = VlineGenerator(on_vline=self.on_vline)

        vol_list = [10, 20, 40]
        vline_buf = {}
        for v in vol_list:
            vline_buf[v] = []
        func3 = lambda x, y: vline_buf[y].append(x)
        self.vg.multi_vline_setting(on_multi_vline=func3, vol_list=vol_list)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

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

        if self.vg.vline.low_price < 4000:
            # vt_orderid = self.buy(price=self.last_tick.last_price, volume=0.01)
            # vt_orderid = self.send_order(direction=Direction.LONG,
            #                              price=self.last_tick.last_price,
            #                              volume=0.01,
            #                              offset=Offset.NONE)
            self.cta_engine.send_order(direction=Direction.LONG,
                                       price=self.last_tick.last_price,
                                       offset=Offset.NONE, volume=0.01, stop=False, lock=False)
            # print('BUY: P-%.3f V-%.3f' % (self.last_tick.last_price, 0.01))
        elif self.vg.vline.high_price > 4500:
            # vt_orderid = self.sell(price=self.last_tick.last_price, volume=0.01)
            # vt_orderid = self.send_order(direction=Direction.SHORT,
            #                              price=self.last_tick.last_price,
            #                              volume=0.01,
            #                              offset=Offset.NONE)
            self.cta_engine.send_order(direction=Direction.SHORT,
                                       price=self.last_tick.last_price,
                                       offset=Offset.NONE, volume=0.01, stop=False, lock=False)

        #print('SELL: P-%.3f V-%.3f' % (self.last_tick.last_price, 0.01))
        self.put_event()

    def on_vline(self, vline: VlineData):
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
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        self.put_event()

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

    def send_order(
        self,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False
    ):
        '''
        if is in real environment then directly submit order to market,
        '''

        if self.trading:
            # send order to market
            vt_orderid = super(TestStrategy, self).send_order(direction=direction, offset=offset,
                                                              price=price, volume=volume,
                                                              stop=stop, lock=lock)
        else:
            # send order to back testing
            pass
