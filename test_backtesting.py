from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from vnpy.app.cta_strategy.adv_backtesting import AdvBacktestingEngine
from vnpy.app.cta_strategy.strategies.atr_rsi_strategy import AtrRsiStrategy
#from vnpy.app.cta_strategy.strategies.test_strategy import TestStrategy
from vnpy.app.cta_strategy.strategies.grid_vline import GridVline
from datetime import datetime

engine = AdvBacktestingEngine()
engine.set_parameters(
    vt_symbol="BTCUSDT.BINANCE",
    interval="1m",
    start=datetime(2019, 1, 1),
    end=datetime(2019, 4, 30),
    rate=0.3/10000,
    slippage=0.2,
    size=300,
    pricetick=0.2,
    capital=1_000_000,
)

# self.filepath: str = '/home/lir0b/data/TradingData/Binance'
# self.exchange_name: str = 'Binance'
# self.symbol = 'BTCUSDT'
# self.symbol_list = ['BTC', 'USDT']
# self.sid = 100001
# self.eid = 2000000
# self.suffix = 'trade'
# self.ndf = None
# self.gateway_name = 'BINANCE'

parameters = {'vline_vol': 5,
              'vline_vol_list': [10, 20, 40, 80, 160, 320, 640, 1280],
              'min_vline_num': 10,
              'max_vline_num': 1000,
              'first_symbol': 'BTC',
              'second_symbol': 'USDT',
              'min_trade_vol': 0.05,
              'max_trade_vol': 0.5}

setting = {'parameters': parameters}
engine.add_strategy(GridVline, setting)
engine.load_data()
engine.run_backtesting()

# df = engine.calculate_result()
# engine.calculate_statistics()
# engine.show_chart()
#
# #%%
#
# setting = OptimizationSetting()
# setting.set_target("sharpe_ratio")
# setting.add_parameter("atr_length", 3, 39, 1)
# setting.add_parameter("atr_ma_length", 10, 30, 1)
#
# engine.run_ga_optimization(setting)
