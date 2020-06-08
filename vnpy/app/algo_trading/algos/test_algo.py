from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData, BarData
from vnpy.trader.engine import BaseEngine

from vnpy.app.algo_trading import AlgoTemplate
from pprint import pprint
import numpy as np
#from vnpy.app.event import Event
#from vnpy.trader.event import EVENT_KLINE


class TestAlgo(AlgoTemplate):
    """"""

    display_name = "Test Algo"
    algo_name = "TestAlgo"

    default_setting = {
        "vt_symbol": "",
        "interval": int(10),
    }

    variables = [
        "timer_count",
        "active_vt_orderid",
        "passive_vt_orderid",
        "active_pos",
        "passive_pos"
    ]

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        setting: dict
    ):
        """"""
        super().__init__(algo_engine, algo_name, setting)

        # Parameters
        self.vt_symbol = setting["vt_symbol"]
        self.interval = setting["interval"]

        # Variables
        self.active_vt_orderid = ""
        self.passive_vt_orderid = ""
        self.active_pos = 0
        self.passive_pos = 0
        self.timer_count = 0

        self.subscribe(self.vt_symbol)

        self.tick_list = []
        self.tick = None

        self.klines = {self.vt_symbol: []}
        self.kline = None

        self.event_engine = algo_engine.event_engine

        self.put_parameters_event()
        self.put_variables_event()

    def on_start(self):
        msg = f"Start Test Algo"
        self.write_log(msg)

    def on_stop(self):
        """"""
        self.write_log("停止算法")

    def on_order(self, order: OrderData):
        """"""
        msg = f'{order.vt_symbol}-{order.orderid}: P:{order.price} V:{order.volume}'
        self.write_log(msg)
        #if order.vt_symbol == self.vt_symbol:
        #    self.write_log("Receiving Order")
        self.put_variables_event()

    def on_trade(self, trade: TradeData):
        """"""
        # Update pos
        if trade.vt_symbol == self.vt_symbol:
            msg = f'S:{trade.vt_symbol} Oid:{trade.vt_orderid} Tid:{trade.vt_tradeid}'
            self.write_log(msg)
        self.put_variables_event()

    def on_timer(self):
        """"""
        # Run algo by fixed interval
        self.timer_count += 1
        #msg = f'Count:{self.timer_count}'
        #self.write_log(msg)

        if self.timer_count == 20:
            self.buy(vt_symbol=self.vt_symbol,
                     price=self.tick.last_price-300,
                     volume=0.01)
        if self.timer_count == 40:
            self.sell(vt_symbol=self.vt_symbol,
                      price=self.tick.last_price+300,
                      volume=0.01)
        if self.timer_count == 100:
            self.cancel_all()

        # Update GUI
        self.put_variables_event()

    def calc_mean_price(self):
        price = 0
        vol = 0
        for ti in self.tick_list:
            price += ti.last_price
            vol += ti.last_volume
        avg_price = price / vol
        return avg_price

    def on_tick(self, tick: TickData):
        self.tick_list.append(tick)
        if len(self.tick_list) > 100:
            avg_price = np.mean([ti.last_price for ti in self.tick_list])
            msg = f'MP: {avg_price} HP: {tick.high_price} CP: {tick.last_price} LP: {tick.low_price}'
            self.tick_list = []
            self.write_log(msg)

        self.tick = tick
        #print(tick)

        self.put_variables_event()

    def update_tick(self, tick: TickData):
        """"""
        if self.active:
            self.on_tick(tick)

    def update_kline(self, bar: BarData):
        if self.active:
            self.on_kline(bar)

    def on_kline(self, bar: BarData):
        #self.klines[bar.symbol].append(bar)
        #self.kline = bar
        msg = f'KL-{bar.interval}: {bar.symbol} OP: {bar.open_price} CP: {bar.close_price} HP: {bar.high_price} LP: {bar.low_price}'
        self.write_log(msg)



