from .object import BarData, TickData, VlineData, TradeData, DistData, MarketEventData, Direction
from .object import AccountData, BalanceData
from .constant import Exchange, Interval, MarketEvent
import numpy as np
from datetime import timedelta


class BarFeature:
    def __init__(self):
        pass

    @staticmethod
    def spread_vol(kl: BarData):
        return (kl.close_price - kl.open_price) / kl.open_price * kl.volume

    @staticmethod
    def calc_spread_vol(klines=[],
                        start: int = 0,
                        end: int = 0,
                        interval: Interval = Interval.MINUTE):
        '''
        :param klines: list of BarData
        :param start: start index
        :param end: end index
        :param interval: BarData interval
        :return: spread_vol, total_vol
        '''
        spread_vol = 0
        total_vol = 0
        if 0 <= start < end <= len(klines):
            if not klines[0].interval == interval:
                return spread_vol, total_vol
            if start < end:
                kline_start_end = klines[start: end]
                spread_vol = np.sum([BarFeature.spread_vol(kl) for kl in kline_start_end])
                total_vol = np.sum([kl.volume for kl in kline_start_end])
                return spread_vol, total_vol
        else:
            return spread_vol, total_vol

    def detect_outlier_vol(self, klines=[], low_ratio=0.05, high_ratio=0.95):
        pass


class VlineFeature:
    def __init__(self):
        pass

    @staticmethod
    def calc_vol(vlines=[], start=None, end=None, start_td=None, end_td=None, direction=Direction.NONE) -> float:
        total_vol = 0.0
        if len(vlines) == 0:
            return total_vol
        if start_td is not None and end_td is not None:
            cur_td = timedelta(seconds=0)
            for vl in reversed(vlines):
                cur_td += vl.close_time - vl.open_time
                #print(cur_td)
                if start_td <= cur_td <= end_td:
                    if direction == Direction.LONG:
                        total_vol += vl.buy_volume
                    elif direction == Direction.SHORT:
                        total_vol += vl.sell_volume
                    else:
                        total_vol += vl.volume
                elif cur_td > end_td:
                    break
                else:
                    pass
        else:
            if not start:
                start = 0
            if not end:
                end = len(vlines)
            if start < end <= len(vlines) and start <= len(vlines):
                vlines_start_end = vlines[start: end]
                if direction == Direction.LONG:
                    total_vol = float(np.sum([vl.buy_volume for vl in vlines_start_end]))
                elif direction == Direction.SHORT:
                    total_vol = float(np.sum([vl.sell_volume for vl in vlines_start_end]))
                else:
                    total_vol = float(np.sum([vl.volume for vl in vlines_start_end]))
        return total_vol

    @staticmethod
    def spread_vol(x: VlineData, d: Direction):
        return (x.close_price - x.open_price) / x.open_price * x.volume

    @staticmethod
    def calc_spread_vline(vlines=[], start: int = None, end: int = None,
                          start_td: timedelta = None, end_td: timedelta = None,
                          direction=Direction.NONE) -> float:
        total_vol = 0
        spread_vol = 0
        avg_spread_vol = 0

        if start_td and end_td:
            cur_td = timedelta(seconds=0)
            for vl in reversed(vlines):
                cur_td += vl.close_time - vl.open_time
                if start_td < cur_td < end_td:
                    if direction == Direction.LONG:
                        spread_vol += (vl.close_price - vl.open_price) / vl.open_price * vl.buy_volume
                    elif direction == Direction.SHORT:
                        spread_vol += (vl.close_price - vl.open_price) / vl.open_price * vl.sell_volume
                    else:
                        spread_vol += (vl.close_price - vl.open_price) / vl.open_price * vl.volume
                    total_vol = VlineFeature.calc_vol(vlines=vlines,
                                                      start_td=start_td, end_td=end_td,
                                                      direction=direction)
                    if total_vol > 0:
                        avg_spread_vol = spread_vol / total_vol
                elif cur_td > end_td:
                    break
                else:
                    pass
        else:
            if not start:
                start = 0
            if not end:
                end = len(vlines)
            if start < end <= len(vlines) and start <= len(vlines):
                vlines_start_end = vlines[start: end]
                if direction == Direction.LONG:
                    sv_func = lambda x: (x.close_price - x.open_price) / x.open_price * x.buy_volume
                    spread_vol = float(np.sum([sv_func(vl) for vl in vlines_start_end]))
                elif direction == Direction.SHORT:
                    sv_func = lambda x: (x.close_price - x.open_price) / x.open_price * x.sell_volume
                    spread_vol = float(np.sum([sv_func(vl) for vl in vlines_start_end]))
                else:
                    sv_func = lambda x: (x.close_price - x.open_price) / x.open_price * x.volume
                    spread_vol = float(np.sum([sv_func(vl) for vl in vlines_start_end]))
                total_vol = VlineFeature.calc_vol(vlines=vlines, start=start, end=end, direction=direction)
                if total_vol > 0:
                    avg_spread_vol = spread_vol / total_vol
        sv_total = (spread_vol, total_vol, avg_spread_vol)
        return sv_total

    @staticmethod
    def calc_short_liquidation(vlines=[]) -> MarketEventData:
        med = MarketEventData()
        if len(vlines) > 0:
            pass
        else:
            return None


