from vnpy.trader.object import *
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

vd = VlineData()
vd100 = VlineData()
vlines = []
for i, row in ndf.iterrows():
    tick = TickData(symbol=symbol, exchange=exchange,
                    last_price=row['price'], last_volume=row['qty'],
                    datetime=i, gateway_name=gateway_name)
    if vd.is_empty():
        vd.init_by_tick(tick)
    else:
        vd.add_tick(tick)
    if vd.volume > 10:
        #print(vd)
        vlines.append(vd)
        if vd100.is_empty():
            vd100 = vd
        else:
            vd100 = vd100 + vd
            print(vd100)
            print(len(vd100.ticks), len(vd.ticks))
        vd = VlineData()
    if vd100.volume > 100:
        print(vd100)
        dd = DistData()
        dd.calc_dist(vd100.ticks)
        print(dd.total_vol())
        break
print(vd100)
