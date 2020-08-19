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

    vg = VlineGenerator()
    vd = VlineData()
    vd100 = VlineData()
    vlines = []
    for i, row in ndf.iterrows():
        tick = TickData(symbol=symbol, exchange=exchange,
                        last_price=row['price'], last_volume=row['qty'],
                        datetime=i, gateway_name=gateway_name)
        vg.update_tick(tick)
        print(vg.vline)
