from vnpy.trader.object import *
from vnpy.trader.utility import *


if __name__ == '__main__':
    import dl.utils as dlu

    symbol = 'BTCUSDT'
    exchange = Exchange.BINANCE
    filepath = '/home/lir0b/data/TradingData/Binance'
    sid = 100001
    eid = 200000
    suffix = 'trade'
    gateway_name = 'BINANCE'
    exchange_name = 'Binance'
    ndf = dlu.load_trades_xls(filepath=filepath, exchange=exchange_name,
                              symbol=symbol, sid=sid, eid=eid, subffix=suffix)
    ndf = dlu.datetime_tick(ndf)
    on_vline = lambda x: x
    on_multi_vline = lambda x, y: (y, x)
    vg = VlineGenerator(on_vline=on_vline, vol=5)
    vg.multi_vline_setting(on_multi_vline=on_multi_vline, vol_list=[10, 20, 50, 100, 200])
    #vd = VlineData()
    #vd100 = VlineData()
    #vlines = []
    for i, row in ndf.iterrows():
        tick = TickData(symbol=symbol, exchange=exchange,
                        last_price=row['price'], last_volume=row['qty'],
                        datetime=i, gateway_name=gateway_name)
        vg.update_tick(tick)
        #print(vg.vline)
    print(len(vg.ticks), len(vg.dists), len(vg.vlines))
    print(vg.vline_buf)
    for vb in vg.vline_buf:
        print(vb, len(vg.vline_buf[vb].ticks), vg.vline_buf[vb])
    print()
    for db in vg.dist_buf:
        print(db, vg.dist_buf[db].total_vol(), vg.dist_buf[db])
