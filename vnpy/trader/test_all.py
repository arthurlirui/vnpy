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
    ndf = ndf[:50000]

    gateway_name = 'HUOBI'

    buf = []
    func = lambda x: buf.append(x)
    bar_buf = []
    func2 = lambda x: bar_buf.append(x)

    vline_buf = {10: [], 20: [], 40: []}
    func3 = lambda x, y: vline_buf[y].append(x)

    vg = VlineGenerator(on_vline=func, vol=1, on_bar=func2, interval=Interval.MINUTE)
    vg.multi_vline_setting(on_multi_vline=func3, vol_list=[10, 20, 40])
    for i, row in ndf.iterrows():
        #print(row)
        tick = TickData(symbol=symbol, exchange=Exchange.HUOBI,
                        last_price=row['price'], last_volume=row['qty'],
                        datetime=i, gateway_name=gateway_name)
        #print(tick)
        #print('Tick', tick)
        vg.update_tick(tick)
        #print(len(buf))
        #if len(buf) > 0:
        #    print('Vline', vg.vline)
        #print('Vline', vg.vline)
        for k in vg.vline_buf:
            if not vg.vline_buf[k].is_empty():
                print(k, vg.vline_buf[k])
        #print('Vline20', vg.vline_buf[20])
        #print(len(bar_buf))
        #if len(bar_buf) > 0:
        #print('Bar', vg.bar)
        #print()


if __name__ == '__main__':
    test_vline_generator()