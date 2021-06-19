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
    def spread(kl: BarData):
        return (kl.close_price - kl.open_price) / kl.open_price

    @staticmethod
    def calc_spread(klines=[], start: int = 0, end: int = 0, interval: Interval = Interval.MINUTE):
        total_spread = 0
        if 0 <= start < end <= len(klines):
            if not klines[0].interval == interval:
                return total_spread
            if start < end:
                kline_start_end = list(reversed(klines))[start: end]
                total_spread = np.sum([BarFeature.spread(kl) for kl in kline_start_end])
        return total_spread

    @staticmethod
    def calc_spread_vol(klines=[], start: int = 0, end: int = 0, interval: Interval = Interval.MINUTE):
        '''
        :param klines: list of BarData
        :param start: start index
        :param end: end index
        :param interval: BarData interval
        :return: spread_vol, total_vol
        '''
        spread_vol = 0
        total_vol = 0
        avg_spread_vol = 0
        res_spread_vol = {'spread_vol': spread_vol, 'total_vol': total_vol, 'avg_sv': avg_spread_vol}
        if 0 <= start < end <= len(klines):
            if not klines[0].interval == interval:
                return res_spread_vol
            if start < end:
                kline_start_end = list(reversed(klines))[start: end]
                spread_vol = np.sum([BarFeature.spread_vol(kl) for kl in kline_start_end])
                total_vol = np.sum([kl.volume for kl in kline_start_end])
                res_spread_vol['spread_vol'] = spread_vol
                res_spread_vol['total_vol'] = total_vol
                if total_vol > 0:
                    res_spread_vol['avg_sv'] = spread_vol / total_vol
                return res_spread_vol
        else:
            return res_spread_vol


class VlineFeature:
    def __init__(self):
        pass

    @staticmethod
    def calc_vol(vlines=[], start=None, end=None, start_td=None, end_td=None, direction=Direction.NONE) -> float:
        total_vol = 0.0
        if len(vlines) == 0:
            return total_vol

        def vol_func(x):
            if direction == Direction.LONG:
                return x.buy_volume
            elif direction == Direction.SHORT:
                return x.sell_volume
            else:
                return x.volume

        if start_td is not None and end_td is not None:
            cur_td = timedelta(seconds=0)
            for vl in reversed(vlines):
                cur_td += vl.close_time - vl.open_time
                if start_td <= cur_td <= end_td:
                    total_vol += vol_func(vl)
                if cur_td > end_td:
                    break
        else:
            if start is None:
                start = 0
            if end is None:
                end = len(vlines)
            if start < end <= len(vlines):
                vlines_start_end = vlines[start: end]
                total_vol = float(np.sum([vol_func(vl) for vl in vlines_start_end]))
        res = {'total_vol': total_vol}
        return res

    @staticmethod
    def spread_vol(x: VlineData, d: Direction):
        return (x.close_price - x.open_price) / x.open_price * x.volume

    @staticmethod
    def calc_spread(vlines=[], start: int = None, end: int = None, start_td: timedelta = None, end_td: timedelta = None) -> float:
        spread = 0
        def spread_func(x): return (x.close_price - x.open_price) / x.open_price
        if start_td is not None and end_td is not None:
            cur_td = timedelta(seconds=0)
            for vl in reversed(vlines):
                cur_td += vl.close_time - vl.open_time
                if start_td <= cur_td <= end_td:
                    spread += spread_func(vl)
                if cur_td > end_td:
                    break
        else:
            if start is None:
                start = 0
            if end is None:
                end = len(vlines)
            if start < end <= len(vlines):
                vlines_start_end = vlines[start: end]
                spread = np.sum(spread_func(vl) for vl in vlines_start_end)
        res = {'spread': float(spread)}
        return res

    @staticmethod
    def calc_spread_vol(vlines=[], start: int = None, end: int = None,
                        start_td: timedelta = None, end_td: timedelta = None,
                        direction=Direction.NONE) -> float:
        total_vol = 0
        spread_vol = 0
        avg_spread_vol = 0

        def sv_func(x):
            if direction == Direction.LONG:
                return (x.close_price - x.open_price) / x.open_price * x.buy_volume
            elif direction == Direction.SHORT:
                return (x.close_price - x.open_price) / x.open_price * x.sell_volume
            else:
                return (x.close_price - x.open_price) / x.open_price * x.volume

        def vol_func(x):
            if direction == Direction.LONG:
                return x.buy_volume
            elif direction == Direction.SHORT:
                return x.sell_volume
            else:
                return x.volume

        if start_td is not None and end_td is not None:
            cur_td = timedelta(seconds=0)
            for vl in reversed(vlines):
                cur_td += vl.close_time - vl.open_time
                if start_td <= cur_td <= end_td:
                    spread_vol += sv_func(vl)
                    total_vol += vol_func(vl)
            if total_vol > 0:
                avg_spread_vol = spread_vol / total_vol
        else:
            if start is None:
                start = 0
            if end is None:
                end = len(vlines)
            if start < end <= len(vlines):
                vlines_start_end = vlines[start: end]
                spread_vol = float(np.sum([sv_func(vl) for vl in vlines_start_end]))
                total_vol = float(np.sum([vol_func(vl) for vl in vlines_start_end]))
                if total_vol > 0:
                    avg_spread_vol = spread_vol / total_vol
        res = {'spread_vol': float(spread_vol), 'total_vol': float(total_vol), 'avg_sv': float(avg_spread_vol)}
        return res

    @staticmethod
    def calc_vol_speed(vlines=[], start_td=timedelta(seconds=0), end_td=timedelta(seconds=10),
                       direction=Direction.NONE):
        start_td = start_td
        end_td = end_td
        td = end_td - start_td
        res = VlineFeature.calc_vol(vlines=vlines, start_td=start_td, end_td=end_td, direction=direction)
        speed = res['total_vol'] / td.total_seconds()
        #res = {'speed': float(speed)}
        res = float(speed)
        return res


class MarketEventFeature:
    def __init__(self):
        pass

    @staticmethod
    def check_gain():
        pass
