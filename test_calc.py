import talib
import pandas as pd
import os
import numpy as np
import matplotlib
from datetime import datetime
import pytz

from vnpy.trader.object import BarData
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.calc import BarFeature
import matplotlib.pyplot as plt


if __name__ == '__main__':
    SAUDI_TZ = pytz.timezone("Asia/Qatar")
    Singapore_TZ = pytz.timezone("Asia/Singapore")
    MY_TZ = SAUDI_TZ

    filepath = '/home/lir0b/data/TradingData/BinanceKline/BTCUSDT'
    filename = 'Binance-BTCUSDT-1m-1-Jan-2018-1-Feb-2018-kline.xlsx'
    datadf = pd.read_excel(os.path.join(filepath, filename))

    gateway_name = filename.split('-')[0]
    symbol = filename.split('-')[1]
    exchange = Exchange.BINANCE
    interval = Interval.MINUTE

    open_price = datadf['Open'].to_numpy()
    close_price = datadf['Close'].to_numpy()
    high_price = datadf['High'].to_numpy()
    low_price = datadf['Low'].to_numpy()
    volume = datadf['Volume'].to_numpy()
    open_time = datadf['OpenTime'].to_numpy()
    count = datadf['Number of Trades'].to_numpy()
    amount = datadf['QuoteAssetVolume'].to_numpy()

    klines = []
    for i in range(len(open_price)):
        dti = datetime.fromtimestamp(open_time[i]/1000)
        dti = dti.replace(tzinfo=MY_TZ)

        bar = BarData(symbol=symbol, exchange=exchange, datetime=dti, gateway_name=gateway_name)
        bar.interval = interval
        bar.volume = volume[i]
        bar.open_time = dti
        bar.open_price = open_price[i]
        bar.close_price = close_price[i]
        bar.high_price = high_price[i]
        bar.low_price = low_price[i]
        bar.count = count[i]
        bar.amount = amount[i]
        bar.open_time = dti

        klines.append(bar)

    start = 11000
    end = 16000
    print(len(klines))
    print(klines[start])
    print(klines[end])
    spread_vol, total_vol = BarFeature.calc_spread_vol(klines=klines, start=start, end=end, interval=interval)

    print(spread_vol, total_vol)

    spread_vol_20 = []
    spread_vol_3 = []
    for i in range(len(klines)):
        spread_vol, total_vol = BarFeature.calc_spread_vol(klines=klines, start=i - 20, end=i, interval=interval)
        spread_vol_20.append(spread_vol)
        spread_vol, total_vol = BarFeature.calc_spread_vol(klines=klines, start=i - 3, end=i, interval=interval)
        spread_vol_3.append(spread_vol)
    #print(spread_vol_20)

    fig, ax1 = plt.subplots(3)
    plt.style.use('seaborn-whitegrid')

    # ax2.plot(spread_vol100[s1-3:s2-3], 'm-')
    ax1[0].plot(spread_vol_20, 'g--')
    ax1[1].plot(spread_vol_3, 'r--')
    #ax1[0].plot(spread_vol20_s, 'm--')
    # ax1.plot(volume_s, 'm-')
    ax2 = ax1[2].twinx()
    ax2.plot(close_price, 'y--')
    #ax2.plot(rebound_ind, rebound_point, 'g+')
    # ax2.plot(chase_ind, chase_point, 'ro')

    ax2.set_xlabel('X data')
    ax2.set_ylabel('Price', color='k')
    ax1[0].set_ylabel('SpreadVol', color='b')

    plt.show()