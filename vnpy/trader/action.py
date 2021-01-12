from typing import Callable, Dict, Tuple, Union
from vnpy.trader.constant import MarketAction
from vnpy.trader.object import TickData
from datetime import timedelta


class Action:
    def __init__(self, send_order: Callable):
        self.send_order = send_order
        self.action_list = []

    def update_balance(self):
        pass

    def define_action(self, tick: TickData):
        pass

    def define_auto_ask(self, tick: TickData):
        pass

    def define_auto_bid(self, tick: TickData):
        pass
