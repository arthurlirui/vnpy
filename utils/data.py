import os
import pandas as pd
import numpy as np


def load_trade_xls(filepath: str, exchange: str, symbol: str, sid: int, eid: int, subffix='trade'):
    filename = f'{exchange}-{symbol}-{str(sid)}-{str(eid)}-{subffix}.xlsx'
    print(filename)
    ndf = pd.read_excel(os.path.join(filepath, str(symbol), filename))
    return ndf


def load_trades_xls(filepath: str, exchange: str, symbol: str, sid: int, eid: int, subffix='trade', step=100000):
    buf = []
    sid = int(np.floor(sid / step) * step)
    eid = int(np.floor(eid / step) * step)
    idlist = list(range(sid, eid, step))
    for id in idlist:
        ndf = load_trade_xls(filepath, exchange, symbol, id+1, id+step, subffix)
        buf.append(ndf)
    alldf = pd.DataFrame(columns=buf[0].columns)
    alldf = alldf.append(buf, ignore_index=True, )
    return alldf


def datetime_tick(tick: pd.DataFrame):
    tick['Date'] = pd.to_datetime(tick['time'], unit='ms', utc=True)
    tick.set_index('Date', inplace=True)
    return tick


if __name__ == '__main__':
    from pprint import pprint
    filepath = '/home/lir0b/data/TradingData/Binance'
    exchange = 'Binance'
    symbol = 'BTCUSDT'
    sid = 100001
    eid = 400000
    subffix = 'trade'
    from dl.utils.data import load_trade_xls
    ndf = load_trades_xls(filepath=filepath, exchange=exchange, symbol=symbol, sid=sid, eid=eid, subffix=subffix)
    print(ndf)
    data_list = ndf.values.tolist()
    qty = ndf['qty']
    #pprint(data_list)
    ndf['cumqty'] = qty.cumsum().round(-1).astype('int32')
    pprint(ndf.groupby('cumqty').groups)