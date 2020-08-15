from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from vnpy.app.cta_strategy.adv_backtesting import AdvBacktestingEngine
from vnpy.app.cta_strategy.strategies.atr_rsi_strategy import AtrRsiStrategy
from vnpy.app.cta_strategy.strategies.test_strategy import TestStrategy
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

parameters = {'vline_vol': 5,
              'vline_vol_list': [10, 20, 40],
              'min_vline_num': 10,
              'max_vline_num': 1000,
              'first_symbol': 'BTC',
              'second_symbol': 'USDT',
              'min_trade_vol': 0.005,
              'max_trade_vol': 0.1}

setting = {'parameters': parameters}
engine.add_strategy(TestStrategy, setting)
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
