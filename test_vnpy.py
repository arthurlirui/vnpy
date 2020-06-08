# flake8: noqa
from vnpy.event import EventEngine

from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

# from vnpy.gateway.binance import BinanceGateway
# from vnpy.gateway.bitmex import BitmexGateway
# from vnpy.gateway.futu import FutuGateway
# from vnpy.gateway.ib import IbGateway
# from vnpy.gateway.ctp import CtpGateway
# from vnpy.gateway.ctptest import CtptestGateway
# from vnpy.gateway.mini import MiniGateway
# from vnpy.gateway.sopt import SoptGateway
# from vnpy.gateway.minitest import MinitestGateway
# from vnpy.gateway.femas import FemasGateway
# from vnpy.gateway.tiger import TigerGateway
# from vnpy.gateway.oes import OesGateway
# from vnpy.gateway.okex import OkexGateway
# from vnpy.gateway.huobi import HuobiGateway
# from vnpy.gateway.bitfinex import BitfinexGateway
# from vnpy.gateway.onetoken import OnetokenGateway
# from vnpy.gateway.okexf import OkexfGateway
# from vnpy.gateway.okexs import OkexsGateway
#from vnpy.gateway.xtp import XtpGateway
# from vnpy.gateway.huobif import HuobifGateway
#from vnpy.gateway.tap import TapGateway
# from vnpy.gateway.tora import ToraGateway
# from vnpy.gateway.alpaca import AlpacaGateway
# from vnpy.gateway.da import DaGateway
# from vnpy.gateway.coinbase import CoinbaseGateway
# from vnpy.gateway.bitstamp import BitstampGateway
# from vnpy.gateway.gateios import GateiosGateway
# from vnpy.gateway.bybit import BybitGateway
# from vnpy.gateway.deribit import DeribitGateway
#from vnpy.gateway.uft import UftGateway
# from vnpy.gateway.okexo import OkexoGateway
# from vnpy.gateway.binancef import BinancefGateway

# from vnpy.app.cta_strategy import CtaStrategyApp
# from vnpy.app.csv_loader import CsvLoaderApp
# from vnpy.app.algo_trading import AlgoTradingApp
# from vnpy.app.cta_backtester import CtaBacktesterApp
# from vnpy.app.data_recorder import DataRecorderApp
# from vnpy.app.risk_manager import RiskManagerApp
# from vnpy.app.script_trader import ScriptTraderApp
# from vnpy.app.rpc_service import RpcServiceApp
# from vnpy.app.spread_trading import SpreadTradingApp
# from vnpy.app.portfolio_manager import PortfolioManagerApp
# from vnpy.app.option_master import OptionMasterApp
# from vnpy.app.chart_wizard import ChartWizardApp
# from vnpy.app.excel_rtd import ExcelRtdApp
# from vnpy.app.data_manager import DataManagerApp
#from vnpy.app.portfolio_strategy import PortfolioStrategyApp

from pprint import pprint
import time
from vnpy.trader.constant import OrderType

from typing import Sequence, Type

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.event import EVENT_LOG
from vnpy.app.algo_trading.algos import TestAlgo


def main():
    """"""
    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)

    # main_engine.add_gateway(BinanceGateway)
    # main_engine.add_gateway(CtpGateway)
    # main_engine.add_gateway(CtptestGateway)
    # main_engine.add_gateway(MiniGateway)
    # main_engine.add_gateway(SoptGateway)
    # main_engine.add_gateway(MinitestGateway)
    # main_engine.add_gateway(FemasGateway)
    main_engine.add_gateway(UftGateway)
    # main_engine.add_gateway(IbGateway)
    # main_engine.add_gateway(FutuGateway)
    # main_engine.add_gateway(BitmexGateway)
    # main_engine.add_gateway(TigerGateway)
    # main_engine.add_gateway(OesGateway)
    # main_engine.add_gateway(OkexGateway)
    # main_engine.add_gateway(HuobiGateway)
    # main_engine.add_gateway(BitfinexGateway)
    # main_engine.add_gateway(OnetokenGateway)
    # main_engine.add_gateway(OkexfGateway)
    # main_engine.add_gateway(HuobifGateway)
    main_engine.add_gateway(XtpGateway)
    main_engine.add_gateway(TapGateway)
    # main_engine.add_gateway(ToraGateway)
    # main_engine.add_gateway(AlpacaGateway)
    # main_engine.add_gateway(OkexsGateway)
    # main_engine.add_gateway(DaGateway)
    # main_engine.add_gateway(CoinbaseGateway)
    # main_engine.add_gateway(BitstampGateway)
    # main_engine.add_gateway(GateiosGateway)
    # main_engine.add_gateway(BybitGateway)
    # main_engine.add_gateway(DeribitGateway)
    # main_engine.add_gateway(OkexoGateway)
    # main_engine.add_gateway(BinancefGateway)

    # main_engine.add_app(CtaStrategyApp)
    # main_engine.add_app(CtaBacktesterApp)
    # main_engine.add_app(CsvLoaderApp)
    # main_engine.add_app(AlgoTradingApp)
    # main_engine.add_app(DataRecorderApp)
    # main_engine.add_app(RiskManagerApp)
    # main_engine.add_app(ScriptTraderApp)
    # main_engine.add_app(RpcServiceApp)
    # main_engine.add_app(SpreadTradingApp)
    # main_engine.add_app(PortfolioManagerApp)
    # main_engine.add_app(OptionMasterApp)
    # main_engine.add_app(ChartWizardApp)
    # main_engine.add_app(ExcelRtdApp)
    # main_engine.add_app(DataManagerApp)
    main_engine.add_app(PortfolioStrategyApp)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


def test_cmd():
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(HuobiGateway)
    print(main_engine.engines)
    for gw in main_engine.exchanges:
        print(gw)
    default_setting = main_engine.get_default_setting('HUOBI')
    pprint(default_setting)


def test_restapi():
    from vnpy.trader.object import SubscribeRequest
    from vnpy.trader.constant import Exchange
    #from vnpy.api.rest import RestClient
    #from vnpy.gateway.huobi import HuobiRestApi
    event_engine = EventEngine()
    #main_engine = MainEngine(event_engine)
    #main_engine.add_gateway(HuobiGateway)

    sreq = SubscribeRequest(symbol='btcusdt', exchange=Exchange.HUOBI)
    pprint(sreq)

    #resclient = RestClient()
    huobi_gateway = HuobiGateway(event_engine=event_engine)
    print(huobi_gateway)
    huobi_gateway.subscribe(sreq)


# def run(engine, vt_symbols, algo):
#     """"""
#     #vt_symbols = ["IF1912.CFFEX", "rb2001.SHFE"]
#
#     # 订阅行情
#     for vt_symbol in vt_symbols:
#         engine.subscribe(algo, vt_symbol)
#
#     default_setting = {
#         "template_name": "TestAlgo",
#         "vt_symbol": "btcusdt.HUOBI",
#         "interval": 5000
#     }
#     #engine.start_algo(default_setting)
#
#     # 获取合约信息
#     for vt_symbol in vt_symbols:
#         #print(vt_symbol)
#         contract = engine.get_contract(algo, vt_symbol)
#         msg = f"合约信息，{contract}"
#         engine.write_log(msg)
#
#     #for od in orders:
#     #    od.print_object()
#     #orders = engine.get_all_active_orders()
#     #print(orders)
#     #accounts = engine.get_all_accounts()
#     #for acc in accounts:
#     #    print(acc)
#     engine.strategy_active = True
#     # 持续运行，使用strategy_active来判断是否要退出程序
#     last_tick = None
#     count = 0
#     last_ticks = {}
#     for vt_symbol in vt_symbols:
#         init_tick = True
#         while init_tick:
#             tick = engine.get_tick(algo, vt_symbol)
#             if tick is not None:
#                 last_ticks[vt_symbol] = tick
#                 init_tick = False
#     while engine.strategy_active:
#         # 轮询获取行情
#         for vt_symbol in vt_symbols:
#             tick = engine.get_tick(algo, vt_symbol)
#             #print(tick.symbol)
#             msg = f"最新行情, {tick}"
#             engine.write_log(msg)
#
#             if tick is not None:
#                 if last_ticks[vt_symbol].last_price != tick.last_price:
#                     msg = f"{tick.gateway_name} {tick.symbol} LP:{tick.last_price} B1:{tick.bid_price_1} A1:{tick.ask_price_1}"
#                     engine.write_log(msg)
#                     last_ticks[vt_symbol] = tick
#
#                 if count == 10:
#                     pass
#                     #vt_orderid_1 = engine.buy(vt_symbol, tick.last_price-100, 0.1, OrderType.LIMIT)
#                     #print(vt_orderid_1)
#                 if count == 100:
#                     #engine.cancel_order(vt_orderid_1)
#                     engine.strategy_active = False
#                     #pass
#
#                 #if count % 150 == 0:
#                 #    engine.ca
#                 count = count + 1
#
#         # 等待3秒进入下一轮
#         time.sleep(0.01)


def test_run():
    from time import sleep
    from vnpy.app.script_trader import ScriptEngine, init_cli_trading
    from vnpy.gateway.huobi import HuobiGateway
    from vnpy.gateway.binance import BinanceGateway

    #event_engine = EventEngine()
    #main_engine = MainEngine(event_engine)
    #main_engine.add_gateway(HuobiGateway)

    default_setting = HuobiGateway.default_setting

    huobi_setting = {
        "API Key": "19a98640-nbtycf4rw2-39356103-11fd8",
        "Secret Key": "1f2eb44a-59175994-b1774ffd-30396",
        "会话数": 3,
        "代理地址": "",
        "代理端口": "",
    }

    binance_setting = {
        "key": "1Cbdpi2fnuIuE23vep16BvGZSqpz7mdWKX1SXYDxlpjaJr4JmLqzV94ys0hzxPk2",
        "secret": "ON7vSxctdJiet46JgqXN3DZHfNnpXYyv2BOBCnqS1usXdndoCxW3ry9MaJWnwzKt",
        "session_number": 3,
        "proxy_host": "",
        "proxy_port": 0,
    }

    script_engine = init_cli_trading([HuobiGateway, BinanceGateway])
    script_engine.connect_gateway(huobi_setting, 'HUOBI')
    #script_engine.connect_gateway(binance_setting, 'BINANCE')

    #script_engine = ScriptEngine(main_engine=main_engine, event_engine=event_engine)
    #ArbitrageAlgo(algo_engine=)

    vt_symbols = ['btcusdt.HUOBI']
    #script_engine.subscribe(vt_symbols=vt_symbols)
    # need time to connect to gateway
    time.sleep(10)
    run(engine=script_engine, vt_symbols=vt_symbols)


# def process_log_event(event: Event):
#     """"""
#     log = event.data
#     print(f"{log.time}\t{log.msg}")


def run2(engine, vt_symbols):
    # 订阅行情
    #for vt_symbol in vt_symbols:
    engine.subscribe(vt_symbols)

    # 获取合约信息
    for vt_symbol in vt_symbols:
        contract = engine.get_contract(vt_symbol)
        msg = f"合约信息，{contract}"
        engine.write_log(msg)

    # print order information
    #orders = engine.get_all_active_orders()
    #for od in orders:
    #    print(od)

    # print account information
    accounts = engine.get_all_accounts()
    for acc in accounts:
        msg = f"Account，{acc}"
        engine.write_log(msg)

    #engine.start_strategy(script_path='/home/lir0b/Code/Trading/vnpy/vnpy/app/algo_trading/algos/test_algo.py')

    engine.strategy_active = True
    # 持续运行，使用strategy_active来判断是否要退出程序
    #last_tick = None
    count = 0
    last_ticks = {}
    for vt_symbol in vt_symbols:
        init_tick = True
        while init_tick:
            tick = engine.get_tick(vt_symbol)
            msg = f"tick，{tick}"
            engine.write_log(msg)
            #print(tick)
            if tick is not None:
                last_ticks[vt_symbol] = tick
                init_tick = False
            time.sleep(3)

    while engine.strategy_active:
        # 轮询获取行情
        for vt_symbol in vt_symbols:
            tick = engine.get_tick(vt_symbol)
            #print(tick.symbol)
            msg = f"最新行情, {tick}"
            engine.write_log(msg)

            if tick is not None:
                if last_ticks[vt_symbol].last_price != tick.last_price:
                    msg = f"{tick.gateway_name} {tick.symbol} LP:{tick.last_price} B1:{tick.bid_price_1} A1:{tick.ask_price_1}"
                    engine.write_log(msg)
                    last_ticks[vt_symbol] = tick

                if count == 10:
                    vt_orderid_1 = engine.buy(vt_symbol, tick.last_price-100, 0.1, OrderType.LIMIT)
                    print(vt_orderid_1)
                if count == 100:
                    engine.cancel_order(vt_orderid_1)
                    engine.strategy_active = False
                count = count + 1

        # 等待3秒进入下一轮
        time.sleep(0.01)

from time import sleep
from vnpy.app.script_trader import ScriptEngine, init_cli_trading
from vnpy.gateway.huobi import HuobiGateway
from vnpy.gateway.binance import BinanceGateway


def run(engine: ScriptEngine):
    """"""
    vt_symbols = ['btcusdt.HUOBI', 'ethusdt.HUOBI']

    # 订阅行情
    engine.subscribe(vt_symbols)

    # 获取合约信息
    for vt_symbol in vt_symbols:
        contract = engine.get_contract(vt_symbol)
        msg = f"合约信息，{contract}"
        engine.write_log(msg)

    # 持续运行，使用strategy_active来判断是否要退出程序
    engine.strategy_active = True
    while engine.strategy_active:
        # 轮询获取行情
        for vt_symbol in vt_symbols:
            tick = engine.get_tick(vt_symbol)
            msg = f"最新行情, {tick}"
            engine.write_log(msg)

        # 等待3秒进入下一轮
        time.sleep(3)


def test_script_engine():
    from time import sleep
    from vnpy.app.script_trader import ScriptEngine, init_cli_trading
    from vnpy.gateway.huobi import HuobiGateway
    from vnpy.gateway.binance import BinanceGateway

    #event_engine = EventEngine()
    #main_engine = MainEngine(event_engine)
    #main_engine.add_gateway(HuobiGateway)

    #default_setting = HuobiGateway.default_setting

    huobi_setting = {
        "API Key": "0a1df25b-120e62af-frbghq7rnm-7128e",
        "Secret Key": "bc005f19-033581fa-8a140bba-323ed",
        "会话数": 3,
        "代理地址": "",
        "代理端口": "",
    }

    binance_setting = {
        "key": "1Cbdpi2fnuIuE23vep16BvGZSqpz7mdWKX1SXYDxlpjaJr4JmLqzV94ys0hzxPk2",
        "secret": "ON7vSxctdJiet46JgqXN3DZHfNnpXYyv2BOBCnqS1usXdndoCxW3ry9MaJWnwzKt",
        "session_number": 3,
        "proxy_host": "",
        "proxy_port": 0,
    }

    script_engine = init_cli_trading([HuobiGateway])
    script_engine.connect_gateway(huobi_setting, 'HUOBI')
    #script_engine.connect_gateway(binance_setting, 'BINANCE')

    #script_engine = ScriptEngine(main_engine=main_engine, event_engine=event_engine)
    #ArbitrageAlgo(algo_engine=)

    vt_symbols = ['btcusdt.HUOBI', 'ethusdt.HUOBI']
    #script_engine.subscribe(vt_symbols=vt_symbols)
    # need time to connect to gateway
    time.sleep(10)
    run2(engine=script_engine, vt_symbols=vt_symbols)
    #run(engine=script_engine)


def test_algo():
    from time import sleep
    from vnpy.app.script_trader import ScriptEngine, init_cli_trading
    from vnpy.app.algo_trading import AlgoEngine
    from vnpy.gateway.huobi import HuobiGateway
    from vnpy.gateway.binance import BinanceGateway
    #from .algos.test_algo import TestAlgo

    default_setting = HuobiGateway.default_setting
    gateways = [HuobiGateway]

    huobi_setting = {
        "API Key": "0a1df25b-120e62af-frbghq7rnm-7128e",
        "Secret Key": "bc005f19-033581fa-8a140bba-323ed",
        "会话数": 3,
        "代理地址": "",
        "代理端口": "",
    }

    binance_setting = {
        "key": "1Cbdpi2fnuIuE23vep16BvGZSqpz7mdWKX1SXYDxlpjaJr4JmLqzV94ys0hzxPk2",
        "secret": "ON7vSxctdJiet46JgqXN3DZHfNnpXYyv2BOBCnqS1usXdndoCxW3ry9MaJWnwzKt",
        "session_number": 3,
        "proxy_host": "",
        "proxy_port": 0,
    }

    def process_log_event(event: Event):
        """"""
        log = event.data
        print(f"{log.time}\t{log.msg}")

    event_engine = EventEngine()
    event_engine.register(EVENT_LOG, process_log_event)

    main_engine = MainEngine(event_engine)
    for gateway in gateways:
        main_engine.add_gateway(gateway)

    main_engine.connect(huobi_setting, 'HUOBI')

    time.sleep(10)

    algo_engine = main_engine.add_engine(AlgoEngine)

    print(main_engine.engines)
    test_algo_setting = {"template_name": 'TestAlgo', "vt_symbol": "btcusdt.HUOBI", "interval": 5000}

    #test_algo_1 = TestAlgo(algo_engine, 'test_algo_1', test_algo_setting)

    algo_engine.add_algo_template(TestAlgo)

    #test_algo = TestAlgo()

    print(algo_engine.algo_templates)
    #algo_engine.algo_templates['TestAlgo'].active = True
    print(test_algo_setting)
    #algo_name = algo_engine.start_algo(test_algo_setting)
    #test_algo_01 = algo_engine.algos[algo_name]
    #print(TestAlgo.__name__)
    #print(algo_name)
    vt_symbol = "btcusdt.HUOBI"
    algo_engine.subscribe(TestAlgo, vt_symbol)
    while True:
        sleep(1)

    # contract = algo_engine.get_contract(TestAlgo, vt_symbol)
    # msg = f"合约信息，{contract}"
    # print(contract)
    # algo_engine.write_log(msg)

    # algo_engine.strategy_active = True
    # while algo_engine.strategy_active:
    #     tick = algo_engine.get_tick(TestAlgo, vt_symbol)
    #     msg = f"最新行情, {tick}"
    #     print(tick)
    #     algo_engine.write_log(msg)

    #algo_engine.connect_gateway(huobi_setting, 'HUOBI')

    #time.sleep(10)

    # default_setting = {
    #     "template_name": "TestAlgo",
    #     "vt_symbol": "btcusdt.HUOBI",
    #     "interval": 5000
    # }
    # test_algo = TestAlgo(algo_engine=algo_engine, algo_name='TestAlgo', setting=default_setting)
    #
    # algo_engine.add_algo_template(TestAlgo)
    #
    # algo_engine.start_algo(default_setting)

    #vt_symbols = ['btcusdt.HUOBI', 'ethusdt.HUOBI']
    #vt_symbols = ['btcusdt.HUOBI']
    #script_engine.subscribe(vt_symbols=vt_symbols)
    # need time to connect to gateway
    #time.sleep(3)
    #run(engine=algo_engine, vt_symbols=vt_symbols)
    #run(engine=algo_engine, vt_symbols=vt_symbols, algo=test_algo)


    # 订阅行情
    # for vt_symbol in vt_symbols:
    #     print(vt_symbol)
    #     algo_engine.subscribe(test_algo, vt_symbol)

    # default_setting = {
    #     "template_name": "TestAlgo",
    #     "vt_symbol": "btcusdt.HUOBI",
    #     "interval": 5000
    # }
    # #engine.start_algo(default_setting)
    #
    # # 获取合约信息
    # for vt_symbol in vt_symbols:
    #     #print(vt_symbol)
    #     contract = algo_engine.get_contract(test_algo, vt_symbol)
    #     msg = f"合约信息，{contract}"
    #     print(contract)
    #     algo_engine.write_log(msg)
    #
    # algo_engine.strategy_active = True
    # while algo_engine.strategy_active:
    #     # 轮询获取行情
    #     for vt_symbol in vt_symbols:
    #         tick = algo_engine.get_tick(test_algo, vt_symbol)
    #         #print(tick.symbol)
    #         msg = f"最新行情, {tick}"
    #         print(tick)
    #         algo_engine.write_log(msg)
    #
    #     # 等待3秒进入下一轮
    #     time.sleep(0.1)


if __name__ == "__main__":
    print('Start')
    #test_script_engine()
    test_algo()
    print('End')
