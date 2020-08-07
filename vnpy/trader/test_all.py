from vnpy.trader.utility import *


def test_vline_generator():
    import dl.utils as dlu
    import pandas as pd
    from kmeans_pytorch import kmeans
    import numpy as np
    from pprint import pprint
    import torch
    from vnpy.trader.utility import TickData, VlineData, TradeData

    filepath = '/home/lir0b/data/TradingData/Binance'
    exchange = 'Binance'
    symbol = 'BTCUSDT'
    sid = 100001
    eid = 200000
    subffix = 'trade'
    # from dl.utils.data import load_trade_xls
    ndf = dlu.load_trades_xls(filepath=filepath, exchange=exchange, symbol=symbol, sid=sid, eid=eid, subffix=subffix)
    ndf = dlu.datetime_tick(ndf)
    ndf.head()
    gateway_name = 'HUOBI'

    buf = []
    func = lambda x: buf.append(x)
    bar_buf = []
    func2 = lambda  x: bar_buf.append(x)
    vg = VlineGenerator(on_vline=func, vol=10, on_bar=func2, interval=Interval.MINUTE)
    for i, row in ndf.iterrows():
        #print(row)
        tick = TickData(symbol=symbol, exchange=Exchange.HUOBI,
                        last_price=row['price'], last_volume=row['qty'],
                        datetime=i, gateway_name=gateway_name)
        #print(tick)
        vg.update_tick(tick)
        #print(len(buf))
        if len(buf) > 0:
            print(vg.vline)
        #print(len(bar_buf))
        #if len(bar_buf) > 0:
        #    print(bar_buf[-1])


if __name__ == '__main__':
    test_vline_generator()