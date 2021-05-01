"""
General utility functions.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Tuple, Union
from decimal import Decimal
from math import floor, ceil

import numpy as np
import talib

from .object import BarData, TickData, VlineData, TradeData, DistData, MarketEventData, Direction
from .object import AccountData, BalanceData
from .constant import Exchange, Interval, MarketEvent


log_formatter = logging.Formatter('[%(asctime)s] %(message)s')


def extract_vt_symbol(vt_symbol: str) -> Tuple[str, Exchange]:
    """
    :return: (symbol, exchange)
    """
    symbol, exchange_str = vt_symbol.split(".")
    return symbol, Exchange(exchange_str)


def generate_vt_symbol(symbol: str, exchange: Exchange) -> str:
    """
    return vt_symbol
    """
    return f"{symbol}.{exchange.value}"


def _get_trader_dir(temp_name: str) -> Tuple[Path, Path]:
    """
    Get path where trader is running in.
    """
    cwd = Path.cwd()
    temp_path = cwd.joinpath(temp_name)

    # If .vntrader folder exists in current working directory,
    # then use it as trader running path.
    if temp_path.exists():
        return cwd, temp_path

    # Otherwise use home path of system.
    home_path = Path.home()
    temp_path = home_path.joinpath(temp_name)

    # Create .vntrader folder under home path if not exist.
    if not temp_path.exists():
        temp_path.mkdir()

    return home_path, temp_path


TRADER_DIR, TEMP_DIR = _get_trader_dir(".vntrader")
sys.path.append(str(TRADER_DIR))


def get_file_path(filename: str) -> Path:
    """
    Get path for temp file with filename.
    """
    return TEMP_DIR.joinpath(filename)


def get_folder_path(folder_name: str) -> Path:
    """
    Get path for temp folder with folder name.
    """
    folder_path = TEMP_DIR.joinpath(folder_name)
    if not folder_path.exists():
        folder_path.mkdir()
    return folder_path


def get_icon_path(filepath: str, ico_name: str) -> str:
    """
    Get path for icon file with ico name.
    """
    ui_path = Path(filepath).parent
    icon_path = ui_path.joinpath("ico", ico_name)
    return str(icon_path)


def load_json(filename: str) -> dict:
    """
    Load data from json file in temp path.
    """
    filepath = get_file_path(filename)

    if filepath.exists():
        with open(filepath, mode="r", encoding="UTF-8") as f:
            data = json.load(f)
        return data
    else:
        save_json(filename, {})
        return {}


def save_json(filename: str, data: dict) -> None:
    """
    Save data into json file in temp path.
    """
    filepath = get_file_path(filename)
    with open(filepath, mode="w+", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def round_to(value: float, target: float) -> float:
    """
    Round price to price tick value.
    """
    value = Decimal(str(value))
    target = Decimal(str(target))
    rounded = float(int(round(value / target)) * target)
    return rounded


def floor_to(value: float, target: float) -> float:
    """
    Similar to math.floor function, but to target float number.
    """
    value = Decimal(str(value))
    target = Decimal(str(target))
    result = float(int(floor(value / target)) * target)
    return result


def ceil_to(value: float, target: float) -> float:
    """
    Similar to math.ceil function, but to target float number.
    """
    value = Decimal(str(value))
    target = Decimal(str(target))
    result = float(int(ceil(value / target)) * target)
    return result


def get_digits(value: float) -> int:
    """
    Get number of digits after decimal point.
    """
    value_str = str(value)

    if "." not in value_str:
        return 0
    else:
        _, buf = value_str.split(".")
        return len(buf)


class MarketActionGenerator:
    default_params = {}

    def __init__(self):
        pass


class MarketEventGenerator:
    default_params = {'gain_thresh': 0, 'slip_thresh': 0,
                      'climb_thresh': 0, 'retreat_thresh': 0,
                      'climb_count': 5, 'retreat_count': 5,
                      'hover_count': 5, 'hover_thresh': 10}

    def __init__(self, on_event: Callable):
        '''
        current market event and timestamp
        '''
        # event list
        self.on_event = on_event
        self.market_event_list = []
        self.last_event = MarketEventData()

        # parameters for calculating market event

        # market gain symbol
        self.gain = MarketEventData()
        self.climb = MarketEventData()
        self.surge = MarketEventData()
        self.inflow = MarketEventData()

        # market hover
        self.hover = MarketEventData()

        # market slip symbol
        self.slip = MarketEventData()
        self.retreat = MarketEventData()
        self.slump = MarketEventData()
        self.outflow = MarketEventData()

        self.top_divergence = MarketEventData()
        self.bottom_divergence = MarketEventData()

        # self.event_func_list = [(self.gain, self.update_gain),
        #                         (self.slip, self.update_slip),
        #                         (self.climb, self.update_climb),
        #                         (self.retreat, self.update_retreat),
        #                         (self.surge, self.update_surge),
        #                         (self.slump, self.update_slump),
        #                         (self.inflow, self.update_inflow),
        #                         (self.outflow, self.update_outflow),
        #                         (self.hover, self.update_hover),
        #                         (self.top_divergence, self.update_top_divergence),
        #                         (self.bottom_divergence, self.update_bottom_divergence)]
        self.event_list = [self.gain, self.slip,
                           self.climb, self.retreat,
                           self.surge, self.slump,
                           self.inflow, self.outflow,
                           self.hover,
                           self.top_divergence, self.bottom_divergence]
        self.func_list = [self.update_gain, self.update_slip,
                          self.update_climb, self.update_retreat,
                          self.update_surge, self.update_slump,
                          self.update_inflow, self.update_outflow,
                          self.update_hover,
                          self.update_top_divergence, self.update_bottom_divergence]

        self.params = {}
        self.update_params(params=self.default_params)

    def update_params(self, params={}):
        for key in params:
            if key in self.default_params:
                self.params[key] = params[key]

    def init_event(self, vline: VlineData):
        for event in self.event_list:
            event.init_by_vlines(vlines=[vline])

    def update_event(self, vlines: list = []):
        if len(vlines) == 0:
            return

        for i, func in enumerate(self.func_list):
            is_event = func(vlines=vlines)
            if is_event:
                self.on_event(self.event_list[i])
                #print(i, self.event_list[i])
                #print()

    def update_gain(self, vlines: list = []):
        is_event = False
        if len(vlines) < 2:
            return
        v0 = vlines[-2]
        v1 = vlines[-1]
        dp_avg = v1.avg_price - v0.avg_price
        dp_high = v1.high_price - v0.high_price
        dp_low = v1.low_price - v0.low_price
        if dp_avg >= self.params['gain_thresh'] \
                and dp_high >= self.params['gain_thresh'] \
                and dp_low >= self.params['gain_thresh']:
            self.gain.event = MarketEvent.GAIN
            self.gain.symbol = v0.symbol
            self.gain.exchange = v0.exchange
            self.gain.gateway_name = v0.gateway_name
            self.gain.open_time = v0.open_time
            self.gain.close_time = v1.close_time
            is_event = True
        return is_event

    def update_slip(self, vlines: list = []):
        is_event = False
        if len(vlines) < 2:
            return
        v0 = vlines[-2]
        v1 = vlines[-1]
        dp_avg = v1.avg_price - v0.avg_price
        dp_high = v1.high_price - v0.high_price
        dp_low = v1.low_price - v0.low_price
        if dp_avg <= self.params['slip_thresh'] \
                and dp_high <= self.params['slip_thresh'] \
                and dp_low <= self.params['slip_thresh']:
            self.slip.event = MarketEvent.SLIP
            self.slip.symbol = v0.symbol
            self.slip.exchange = v0.exchange
            self.slip.gateway_name = v0.gateway_name
            self.slip.open_time = v0.open_time
            self.slip.close_time = v1.close_time
            is_event = True
        return is_event

    def update_climb(self, vlines: list = []):
        is_event = False
        pv = None
        count = 0
        for v in reversed(vlines):
            if not pv:
                pv = v
                continue
            dp = pv.avg_price - v.avg_price
            if dp >= self.params['climb_thresh']:
                count += 1
                if count >= self.params['climb_count']:
                    self.climb.open_time = v.open_time
                    is_event = True
            else:
                break
        if is_event:
            self.climb.symbol = pv.symbol
            self.climb.exchange = pv.exchange
            self.climb.gateway_name = pv.gateway_name
            self.climb.close_time = vlines[-1].close_time
            self.climb.event = MarketEvent.CLIMB

        return is_event

    def update_retreat(self, vlines: list = []):
        is_event = False
        pv = None
        count = 0
        for v in reversed(vlines):
            if not pv:
                pv = v
                continue
            dp = pv.avg_price - v.avg_price
            if dp <= self.params['retreat_thresh']:
                count += 1
                if count >= self.params['retreat_count']:
                    self.retreat.open_time = v.open_time
                    is_event = True
            else:
                break
        if is_event:
            self.retreat.symbol = pv.symbol
            self.retreat.exchange = pv.exchange
            self.retreat.gateway_name = pv.gateway_name
            self.retreat.close_time = vlines[-1].close_time
            self.retreat.event = MarketEvent.RETREAT
        return is_event

    def update_surge(self, vlines: list = []):
        is_event = False
        return is_event

    def update_slump(self, vlines: list = []):
        is_event = False
        return is_event

    def update_inflow(self, vlines: list = []):
        is_event = False
        return is_event

    def update_outflow(self, vlines: list = []):
        is_event = False
        return is_event

    def update_top_divergence(self, vlines: list = []):
        is_event = False
        return is_event

    def update_bottom_divergence(self, vlines: list = []):
        is_event = False
        return is_event

    def update_hover(self, vlines: list = []):
        is_event = False
        max_price = vlines[-1].avg_price
        min_price = vlines[-1].avg_price
        cc = 0
        for v in reversed(vlines):
            max_price = max(max_price, v.avg_price)
            min_price = min(min_price, v.avg_price)
            if max_price - min_price < self.params['hover_thresh']:
                cc += 1
                open_time = v.open_time
            else:
                break
        if cc >= self.params['hover_count']:
            is_event = True
            v0 = vlines[-1]
            self.hover.symbol = v0.symbol
            self.hover.exchange = v0.exchange
            self.hover.gateway_name = v0.gateway_name
            self.hover.open_time = open_time
            self.hover.close_time = v0.close_time
            self.hover.event = MarketEvent.HOVER
        return is_event


class VlineGenerator:
    '''
    For
    1. Generate 1 volume vline from tick data
    2. Merge vol_list volume size for vline
    '''
    def __init__(self, on_vline: Callable, vol_list: list = []):
        self.on_vline: Callable = on_vline

        self.vol_list = vol_list
        self.vline_buf = {}
        self.dist_buf = {}
        self.vlines = {}
        self.dists = {}
        for vol in self.vol_list:
            self.vline_buf[vol] = VlineData()
            self.dist_buf[vol] = DistData()
            self.vlines[vol] = []
            self.dists[vol] = []

        self.last_trade: TradeData = None

        # buffer for saving ticks in vline
        self.ticks = []
        self.trades = []

    def get_vline(self, vol: int):
        return self.vline_buf[vol]

    def get_dist(self, vol: int):
        return self.dist_buf[vol]

    def check_valid(self, trade: TradeData) -> bool:
        is_valid = True
        # filter trade data with 0 volume
        if trade.volume <= 0:
            is_valid = False
        # filter trade data with older timestamp
        if self.last_trade and trade.datetime < self.last_trade.datetime:
            is_valid = False
        # filter trade data with different vt_symbol
        if self.last_trade and trade.vt_symbol != self.last_trade.vt_symbol:
            is_valid = False
        return is_valid

    def update_market_trades(self, trade: TradeData) -> None:
        new_vline = False
        if not self.check_valid(trade=trade):
            return

        # for each different volume vline
        for vol in self.vol_list:
            if self.vline_buf[vol].is_empty():
                new_vline = True
            elif self.vline_buf[vol].volume >= vol:
                self.on_vline(self.vline_buf[vol], vol)
                self.update_vline(vline=self.vline_buf[vol], vol=vol)
                self.update_dist(dist=self.dist_buf[vol], vol=vol)
                new_vline = True
            else:
                new_vline = False

            if new_vline:
                # init empty vline here
                self.vline_buf[vol] = VlineData()
                self.vline_buf[vol].init_by_trade(trade)
                self.dist_buf[vol] = DistData()
                self.dist_buf[vol].calc_dist_trades(self.vline_buf[vol].trades)
            else:
                self.vline_buf[vol].add_trade(trade)
                self.dist_buf[vol].add_trade(trade)
        self.last_trade = trade

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        1. udpate vline
        2. update dist for each vline
        3. update long term tick
        """
        new_vline = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        # Filter tick data with older timestamp
        if self.last_tick and tick.datetime < self.last_tick.datetime:
            return

        if self.vline.is_empty():
            new_vline = True
        elif self.vline.volume > self.vol:
            self.on_vline(self.vline)
            # update vline for multiple vlines
            self.update_vline(vline=self.vline)

            # update dist
            self.update_dist(dist=self.dist)
            new_vline = True

        if new_vline:
            # init empty vline here
            self.vline = VlineData()
            self.vline.init_by_tick(tick)

            self.dist = DistData()
            self.dist.calc_dist(self.vline.ticks)
        else:
            self.vline.add_tick(tick)
            self.dist.add_tick(tick)

        self.last_tick = tick

    def multi_vline_setting(self, on_multi_vline: Callable, vol_list=[10, 20, 40]):
        '''
        setting multiple vlines
        :return:
        '''
        self.vol_list = vol_list
        self.on_multi_vline = on_multi_vline

        # multi vline buffer
        self.vline_buf = {}
        self.dist_buf = {}
        for v in self.vol_list:
            self.vline_buf[v] = VlineData()
            self.dist_buf[v] = DistData()

    def update_vline(self, vline: VlineData, vol: int) -> None:
        """
        Update new vline data into generator.
        """
        # 1. process None last tick and None last vline
        # 2. update last vline for each trade
        # 3. check volume to update other all vline in list
        if vol in self.vlines:
            self.vlines[vol].append(vline)

    def update_dist(self, dist: DistData, vol: int):
        if vol in self.dists:
            self.dists[vol].append(dist)

    def init_by_kline(self, bar: BarData):
        trade = bar2trade(bar=bar)
        self.update_market_trades(trade=trade)

    def init_by_trade(self, trade: TradeData):
        self.update_market_trades(trade=trade)


class VlineQueueGenerator:
    def __init__(self, vol_list: list, vt_symbol: str, bin_size: float = 1.0, init_thresh_vol: float = 50):
        """Constructor"""
        self.vol_list = vol_list
        self.bin_size = bin_size
        self.vt_symbol = vt_symbol

        self.vq = {}
        for vol in self.vol_list:
            self.vq[vol] = VlineQueue(max_vol=vol, vt_symbol=self.vt_symbol, bin_size=self.bin_size)

        self.init_thresh_vol = init_thresh_vol
        self.last_trade = None

    def get_vq(self, vol):
        if vol in self.vol_list:
            return self.vq[vol]
        else:
            return None

    def check_valid(self, trade: TradeData) -> bool:
        is_valid = True
        # filter trade data with 0 volume
        if trade.volume <= 0:
            is_valid = False
        # filter trade data with older timestamp
        if self.last_trade and trade.datetime < self.last_trade.datetime:
            is_valid = False
        # filter trade data with different vt_symbol
        if self.last_trade and trade.vt_symbol != self.last_trade.vt_symbol:
            is_valid = False
        return is_valid

    def update_market_trades(self, trade: TradeData) -> None:
        if not self.check_valid(trade=trade):
            return

        # for each different volume vline
        for vol in self.vol_list:
            self.vq[vol].update_trade(trade=trade)

    def init_by_trade(self, trade: TradeData):
        for vol in self.vol_list:
            #if vol <= self.init_thresh_vol:
            self.vq[vol].init_trade(trade=trade)

    def init_by_kline(self, bar: BarData):
        for vol in self.vol_list:
            #if vol > self.init_thresh_vol:
            self.vq[vol].init_kline(bar=bar)


class VlineQueue:
    def __init__(self, max_vol: float = 10.0, vt_symbol: str = None, bin_size: float = 1.0, save_trade: bool = True):
        self.max_vol = max_vol
        self.bin_size = bin_size
        self.save_trade = save_trade
        self.trades = []
        self.vol = 0
        self.dist = {}
        self.vt_symbol = vt_symbol
        self.last_trade = None

    def update_trade(self, trade: TradeData):
        self.last_trade = trade
        self.push(trade=trade)
        while self.size() > self.max_vol:
            self.pop()

    def init_kline(self, bar: BarData):
        trade = bar2trade(bar)
        self.init_trade(trade=trade)

    def init_trade(self, trade: TradeData):
        self.last_trade = trade
        self.push(trade=trade)
        while self.size() > self.max_vol:
            self.pop()

    def update_kline(self, bar: BarData):
        trade = bar2trade(bar)
        self.last_trade = trade
        self.push(trade=trade)
        while self.size() > self.max_vol:
            self.pop()

    def push(self, trade: TradeData):
        if len(self.trades) > 0 and trade.datetime >= self.trades[-1].datetime:
            self.trades.append(trade)
            self.vol = self.vol + trade.volume
            self.push_dist(trade=trade)
        elif len(self.trades) == 0:
            self.trades.append(trade)
            self.vol = self.vol + trade.volume
            self.push_dist(trade=trade)
        else:
            return

    def push_front(self, trade: TradeData):
        if self.save_trade:
            self.trades.insert(0, trade)
        self.vol = self.vol + trade.volume
        self.push_dist(trade=trade)

    def pop(self) -> TradeData:
        if len(self.trades) > 0:
            t0 = self.trades.pop(0)
            self.vol = self.vol - t0.volume
            self.pop_dist(trade=t0)
            return t0
        else:
            return None

    def push_dist(self, trade: TradeData):
        price_key = int(trade.price/self.bin_size)
        if price_key in self.dist:
            self.dist[price_key] += trade.volume
        else:
            self.dist[price_key] = trade.volume

    def pop_dist(self, trade: TradeData):
        price_key = int(trade.price/self.bin_size)
        if price_key in self.dist:
            self.dist[price_key] -= trade.volume

    def size(self):
        return self.vol

    def less_vol(self, price):
        ltvol = sum([self.dist[k] for k in self.dist if k*self.bin_size < price])
        pc = np.round(ltvol / self.vol, 8)
        return pc

    def top_k_price(self, k: float):
        price_vol_list = [p for p in sorted(self.dist.items(), key=lambda x: x[0])]
        total_vol = 0
        for pv in price_vol_list:
            price = pv[0]*self.bin_size
            vol = pv[1]
            total_vol += vol
            p = total_vol/self.vol
            if p > k:
                return price
        return None

    def __str__(self):
        outstr = ''
        for d in self.dist:
            if not self.dist[d] > 0.01:
                continue
            outstr += '%.3f:%.3f ' % (d*self.bin_size, self.dist[d])
        if len(self.trades) > 0:
            outstr += f'\n{len(self.trades)} {self.trades[0]} {self.trades[-1]}\n'
        return outstr


class DistGenerator:
    '''
    For
    1. generate and update dist by tick data
    '''
    def __init__(self, on_dist: Callable, vol: float = 1.0):
        pass

    def update_tick(self, tick: TickData):
        pass


class SimpleVlineGenerator:
    '''
    For
    1. Generate 1 volume vline from tick data
    2. Merge vol_list volume size for vline
    '''
    def __init__(
        self,
        on_vline: Callable,
        vol: float = 1.0,
    ):
        """Constructor"""
        self.vline: VlineData = VlineData()
        self.dist: DistData = DistData()
        self.on_vline: Callable = on_vline
        self.vol: float = vol

        self.ticks = []
        self.vlines = []
        self.dists = []
        self.last_tick = None

        # self.last_tick: TickData = None
        # self.last_vline: VlineData = VlineData()
        # self.last_dist: DistData = DistData()
        # self.dist: DistData = DistData()
        #
        # self.all_dist: DistData = DistData()
        # self.last_teeter_signal = 0.0
        #
        # # buffer for saving ticks in vline
        # self.ticks = []
        #
        # # all running vline, dist, and teeter_signal
        # self.vlines = []
        # self.dists = []
        # self.teeter_signals = []

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        1. udpate vline
        2. update dist for each vline
        3. update long term tick
        """
        new_vline = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        # Filter tick data with older timestamp
        if self.last_tick and tick.datetime < self.last_tick.datetime:
            return

        if self.vline.is_empty():
            new_vline = True
        if self.vline.volume > self.vol:
            self.on_vline(self.vline)

            # update vline
            self.update_vline(vline=self.vline)

            # update dist
            self.update_dist(dist=self.dist)
            new_vline = True

        if new_vline:
            # init empty vline here
            self.vline = VlineData()
            self.vline.init_by_tick(tick)

            self.dist = DistData()
            self.dist.calc_dist(self.vline.ticks)
        else:
            self.vline.add_tick(tick)
            self.dist.add_tick(tick)
        self.last_tick = tick

    def multi_vline_setting(self, on_multi_vline, vol_list=[10, 20, 40]):
        '''
        setting multiple vlines
        :return:
        '''
        self.vol_list = vol_list
        self.on_multi_vline = on_multi_vline

        # multi vline buffer
        self.vline_buf = {}
        self.dist_buf = {}
        for v in self.vol_list:
            self.vline_buf[v] = VlineData()
            self.dist_buf[v] = DistData()

    def update_vline(self, vline: VlineData) -> None:
        """
        Update new vline data into generator.
        """
        # 1. process None last tick and None last vline
        # 2. update last vline for each trade
        # 3. check volume to update other all vline in list
        self.vlines.append(vline)
        for v in self.vol_list:
            n = round(v / self.vol)
            vn = self.vlines[-n:]
            for i, d in enumerate(vn):
                if i == 0:
                    self.vline_buf[v].init_by_vline(vline=d)
                else:
                    self.vline_buf[v] = self.vline_buf[v] + d

    def update_dist(self, dist: DistData):
        self.dists.append(dist)
        #print(len(self.dists), self.dists[-1].total_vol())
        for v in self.vol_list:
            n = round(v / self.vol)
            dn = self.dists[-n:]
            for i, d in enumerate(dn):
                if i == 0:
                    self.dist_buf[v].init_by_dist(d)
                else:
                    self.dist_buf[v] = self.dist_buf[v] + d
            #print(v, self.dist_buf[v].total_vol())
        #print()

    def generate(self) -> None:
        """
        Generate the bar data and call callback immediately.
        """
        bar = self.bar

        if self.bar:
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)
            self.on_bar(bar)

        self.bar = None
        return bar


class BarQueueGenerator:
    def __init__(self):
        self.barq = {}

    def update_bar(self, bar: BarData):
        if bar.vt_symbol not in self.barq:
            self.barq[bar.vt_symbol] = {}
        if bar.interval not in self.barq[bar.vt_symbol]:
            self.barq[bar.vt_symbol][bar.interval] = BarQueue(interval=bar.interval, vt_symbol=bar.vt_symbol)

        self.barq[bar.vt_symbol][bar.interval].update_bar(bar=bar)

    def get_bars(self, vt_symbol: str, interval: Interval):
        if vt_symbol in self.barq:
            if interval in self.barq[vt_symbol]:
                return self.barq[vt_symbol][interval].bars
        return []


class BarQueue:
    def __init__(self, interval: Interval, vt_symbol: str):
        self.vt_symbol = vt_symbol
        self.interval = interval
        self.bars = []
        self.last_bar = None

    def update_bar(self, bar: BarData):
        if bar.vt_symbol == self.vt_symbol and bar.interval == self.interval:
            self.last_bar = bar
            if len(self.bars) == 0:
                self.bars.append(self.last_bar)
            else:
                if self.last_bar.open_time > self.bars[-1].open_time:
                    self.bars.append(self.last_bar)
                elif self.last_bar.open_time == self.bars[-1].open_time:
                    self.bars[-1] = self.last_bar
                else:
                    return
        else:
            return

    def __len__(self):
        return len(self.bars)


class BalanceManager:
    def __init__(self, accound_id: str):
        self.accound_id = None
        self.balance = {}

    def update_balance(self, balance_data: BalanceData):
        if balance_data.accountid == self.accound_id:
            accdata.v
            self.balance[accid]


class BarGenerator:
    """
    For:
    1. generating 1 minute bar data from tick data
    2. generateing x minute bar/x hour bar data from 1 minute data

    Notice:
    1. for x minute bar, x must be able to divide 60: 2, 3, 5, 6, 10, 15, 20, 30
    2. for x hour bar, x can be any number
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable = None,
        interval: Interval = Interval.MINUTE
    ):
        """Constructor"""
        self.bar: BarData = None
        self.on_bar: Callable = on_bar

        self.interval: Interval = interval
        self.interval_count: int = 0

        self.window: int = window
        self.window_bar: BarData = None
        self.on_window_bar: Callable = on_window_bar

        self.last_tick: TickData = None
        self.last_bar: BarData = None

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        """
        new_minute = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        # Filter tick data with older timestamp
        if self.last_tick and tick.datetime < self.last_tick.datetime:
            return

        if not self.bar:
            new_minute = True
        elif self.bar.datetime.minute != tick.datetime.minute:
            self.bar.datetime = self.bar.datetime.replace(
                second=0, microsecond=0
            )
            self.on_bar(self.bar)

            new_minute = True

        if new_minute:
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        else:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest
            self.bar.datetime = tick.datetime

        if self.last_tick:
            volume_change = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

        self.last_tick = tick

    def update_bar(self, bar: BarData) -> None:
        """
        Update 1 minute bar into generator
        """
        # If not inited, creaate window bar object
        if not self.window_bar:
            # Generate timestamp for bar data
            if self.interval == Interval.MINUTE:
                dt = bar.datetime.replace(second=0, microsecond=0)
            else:
                dt = bar.datetime.replace(minute=0, second=0, microsecond=0)

            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into window bar
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price, bar.high_price)
            self.window_bar.low_price = min(
                self.window_bar.low_price, bar.low_price)

        # Update close price/volume into window bar
        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += int(bar.volume)
        self.window_bar.open_interest = bar.open_interest

        # Check if window bar completed
        finished = False

        if self.interval == Interval.MINUTE:
            # x-minute bar
            if not (bar.datetime.minute + 1) % self.window:
                finished = True
        elif self.interval == Interval.HOUR:
            if self.last_bar and bar.datetime.hour != self.last_bar.datetime.hour:
                # 1-hour bar
                if self.window == 1:
                    finished = True
                # x-hour bar
                else:
                    self.interval_count += 1

                    if not self.interval_count % self.window:
                        finished = True
                        self.interval_count = 0

        if finished:
            self.on_window_bar(self.window_bar)
            self.window_bar = None

        # Cache last bar object
        self.last_bar = bar

    def generate(self) -> None:
        """
        Generate the bar data and call callback immediately.
        """
        bar = self.bar

        if self.bar:
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)
            self.on_bar(bar)

        self.bar = None
        return bar


class ArrayManager(object):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, size: int = 100):
        """Constructor"""
        self.count: int = 0
        self.size: int = size
        self.inited: bool = False

        self.open_array: np.ndarray = np.zeros(size)
        self.high_array: np.ndarray = np.zeros(size)
        self.low_array: np.ndarray = np.zeros(size)
        self.close_array: np.ndarray = np.zeros(size)
        self.volume_array: np.ndarray = np.zeros(size)
        self.open_interest_array: np.ndarray = np.zeros(size)

    def update_bar(self, bar: BarData) -> None:
        """
        Update new bar data into array manager.
        """
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True

        self.open_array[:-1] = self.open_array[1:]
        self.high_array[:-1] = self.high_array[1:]
        self.low_array[:-1] = self.low_array[1:]
        self.close_array[:-1] = self.close_array[1:]
        self.volume_array[:-1] = self.volume_array[1:]
        self.open_interest_array[:-1] = self.open_interest_array[1:]

        self.open_array[-1] = bar.open_price
        self.high_array[-1] = bar.high_price
        self.low_array[-1] = bar.low_price
        self.close_array[-1] = bar.close_price
        self.volume_array[-1] = bar.volume
        self.open_interest_array[-1] = bar.open_interest

    @property
    def open(self) -> np.ndarray:
        """
        Get open price time series.
        """
        return self.open_array

    @property
    def high(self) -> np.ndarray:
        """
        Get high price time series.
        """
        return self.high_array

    @property
    def low(self) -> np.ndarray:
        """
        Get low price time series.
        """
        return self.low_array

    @property
    def close(self) -> np.ndarray:
        """
        Get close price time series.
        """
        return self.close_array

    @property
    def volume(self) -> np.ndarray:
        """
        Get trading volume time series.
        """
        return self.volume_array

    @property
    def open_interest(self) -> np.ndarray:
        """
        Get trading volume time series.
        """
        return self.open_interest_array

    def sma(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Simple moving average.
        """
        result = talib.SMA(self.close, n)
        if array:
            return result
        return result[-1]

    def ema(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Exponential moving average.
        """
        result = talib.EMA(self.close, n)
        if array:
            return result
        return result[-1]

    def kama(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        KAMA.
        """
        result = talib.KAMA(self.close, n)
        if array:
            return result
        return result[-1]

    def wma(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        WMA.
        """
        result = talib.WMA(self.close, n)
        if array:
            return result
        return result[-1]

    def apo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        APO.
        """
        result = talib.APO(self.close, n)
        if array:
            return result
        return result[-1]

    def cmo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        CMO.
        """
        result = talib.CMO(self.close, n)
        if array:
            return result
        return result[-1]

    def mom(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MOM.
        """
        result = talib.MOM(self.close, n)
        if array:
            return result
        return result[-1]

    def ppo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PPO.
        """
        result = talib.PPO(self.close, n)
        if array:
            return result
        return result[-1]

    def roc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROC.
        """
        result = talib.ROC(self.close, n)
        if array:
            return result
        return result[-1]

    def rocr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCR.
        """
        result = talib.ROCR(self.close, n)
        if array:
            return result
        return result[-1]

    def rocp(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCP.
        """
        result = talib.ROCP(self.close, n)
        if array:
            return result
        return result[-1]

    def rocr_100(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCR100.
        """
        result = talib.ROCR100(self.close, n)
        if array:
            return result
        return result[-1]

    def trix(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        TRIX.
        """
        result = talib.TRIX(self.close, n)
        if array:
            return result
        return result[-1]

    def std(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Standard deviation.
        """
        result = talib.STDDEV(self.close, n)
        if array:
            return result
        return result[-1]

    def obv(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        OBV.
        """
        result = talib.OBV(self.close, self.volume)
        if array:
            return result
        return result[-1]

    def cci(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Commodity Channel Index (CCI).
        """
        result = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def atr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Average True Range (ATR).
        """
        result = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def natr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        NATR.
        """
        result = talib.NATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def rsi(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Relative Strenght Index (RSI).
        """
        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]

    def macd(
        self,
        fast_period: int,
        slow_period: int,
        signal_period: int,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray, np.ndarray],
        Tuple[float, float, float]
    ]:
        """
        MACD.
        """
        macd, signal, hist = talib.MACD(
            self.close, fast_period, slow_period, signal_period
        )
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]

    def adx(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADX.
        """
        result = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def adxr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADXR.
        """
        result = talib.ADXR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def dx(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        DX.
        """
        result = talib.DX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def minus_di(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MINUS_DI.
        """
        result = talib.MINUS_DI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def plus_di(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PLUS_DI.
        """
        result = talib.PLUS_DI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def willr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        WILLR.
        """
        result = talib.WILLR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def ultosc(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        Ultimate Oscillator.
        """
        result = talib.ULTOSC(self.high, self.low, self.close)
        if array:
            return result
        return result[-1]

    def trange(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        TRANGE.
        """
        result = talib.TRANGE(self.high, self.low, self.close)
        if array:
            return result
        return result[-1]

    def boll(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Bollinger Channel.
        """
        mid = self.sma(n, array)
        std = self.std(n, array)

        up = mid + std * dev
        down = mid - std * dev

        return up, down

    def keltner(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Keltner Channel.
        """
        mid = self.sma(n, array)
        atr = self.atr(n, array)

        up = mid + atr * dev
        down = mid - atr * dev

        return up, down

    def donchian(
        self, n: int, array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Donchian Channel.
        """
        up = talib.MAX(self.high, n)
        down = talib.MIN(self.low, n)

        if array:
            return up, down
        return up[-1], down[-1]

    def aroon(
        self,
        n: int,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Aroon indicator.
        """
        aroon_up, aroon_down = talib.AROON(self.high, self.low, n)

        if array:
            return aroon_up, aroon_down
        return aroon_up[-1], aroon_down[-1]

    def aroonosc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Aroon Oscillator.
        """
        result = talib.AROONOSC(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def minus_dm(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MINUS_DM.
        """
        result = talib.MINUS_DM(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def plus_dm(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PLUS_DM.
        """
        result = talib.PLUS_DM(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def mfi(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Money Flow Index.
        """
        result = talib.MFI(self.high, self.low, self.close, self.volume, n)
        if array:
            return result
        return result[-1]

    def ad(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        AD.
        """
        result = talib.AD(self.high, self.low, self.close, self.volume, n)
        if array:
            return result
        return result[-1]

    def adosc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADOSC.
        """
        result = talib.ADOSC(self.high, self.low, self.close, self.volume, n)
        if array:
            return result
        return result[-1]

    def bop(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        BOP.
        """
        result = talib.BOP(self.open, self.high, self.low, self.close)

        if array:
            return result
        return result[-1]


def virtual(func: Callable) -> Callable:
    """
    mark a function as "virtual", which means that this function can be override.
    any base class should use this or @abstractmethod to decorate all functions
    that can be (re)implemented by subclasses.
    """
    return func


file_handlers: Dict[str, logging.FileHandler] = {}


def _get_file_logger_handler(filename: str) -> logging.FileHandler:
    handler = file_handlers.get(filename, None)
    if handler is None:
        handler = logging.FileHandler(filename)
        file_handlers[filename] = handler  # Am i need a lock?
    return handler


def get_file_logger(filename: str) -> logging.Logger:
    """
    return a logger that writes records into a file.
    """
    logger = logging.getLogger(filename)
    handler = _get_file_logger_handler(filename)  # get singleton handler.
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)  # each handler will be added only once.
    return logger


def bar2trade(bar: BarData) -> TradeData:
    trade = TradeData(gateway_name=bar.gateway_name, symbol=bar.symbol, exchange=bar.exchange, orderid='kline', tradeid='kline')
    trade.vt_symbol = bar.vt_symbol
    trade.datetime = bar.datetime
    trade.price = round(0.25 * (bar.open_price + bar.close_price + bar.high_price + bar.close_price), 8)
    trade.volume = round(bar.volume / trade.price, 8)
    trade.direction = Direction.NONE
    return trade
