from .object import BarData, TickData, VlineData, TradeData, DistData, MarketEventData, Direction
from .object import AccountData, BalanceData
from .constant import Exchange, Interval, MarketEvent
import numpy as np


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


