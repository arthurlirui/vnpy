"""
火币交易接口
"""

import re
import urllib
import base64
import json
import zlib
import hashlib
import hmac
import sys
from copy import copy
from datetime import datetime
import pytz
from typing import Dict, List, Any
import time

from vnpy.api.rest import RestClient, Request
from vnpy.api.websocket import WebsocketClient
from vnpy.trader.constant import (
    Direction,
    Exchange,
    Product,
    Status,
    OrderType,
    Interval
)
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    OrderBookData,
    TradeData,
    AccountData,
    BalanceData,
    AccountInfo,
    BalanceInfo,
    BalanceRequest,
    ContractData,
    BarData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    HistoryRequest,
    BalanceData,
    AccountTradeRequest
)


REST_HOST = "https://api.huobipro.com"
WEBSOCKET_DATA_HOST = "wss://api.huobi.pro/ws"       # Market Data
WEBSOCKET_TRADE_HOST = "wss://api.huobi.pro/ws/v2"     # Account and Order

REST_HOST_AWS = "https://api-aws.huobi.pro"
WEBSOCKET_DATA_HOST_AWS = "wss://api-aws.huobi.pro/ws"
WEBSOCKET_DATA_HOST_FEED_AWS = "wss://api-aws.huobi.pro/feed"
WEBSOCKET_TRADE_HOST_AWS = "wss://api-aws.huobi.pro/ws/v1"

STATUS_HUOBI2VT = {
    "submitted": Status.NOTTRADED,
    "partial-filled": Status.PARTTRADED,
    "filled": Status.ALLTRADED,
    "cancelling": Status.CANCELLED,
    "partial-canceled": Status.CANCELLED,
    "canceled": Status.CANCELLED,
}

ORDERTYPE_VT2HUOBI = {
    (Direction.LONG, OrderType.MARKET): "buy-market",
    (Direction.SHORT, OrderType.MARKET): "sell-market",
    (Direction.LONG, OrderType.LIMIT): "buy-limit",
    (Direction.SHORT, OrderType.LIMIT): "sell-limit",
    (Direction.LONG, OrderType.FOK): "buy-limit-fok",
    (Direction.SHORT, OrderType.FOK): "sell-limit-fok",
    (Direction.LONG, OrderType.IOC): "buy-ioc",
    (Direction.SHORT, OrderType.IOC): "sell-ioc",
}

ORDERTYPE_HUOBI2VT = {v: k for k, v in ORDERTYPE_VT2HUOBI.items()}

INTERVAL_VT2HUOBI = {
    Interval.MINUTE: "1min",
    Interval.MINUTE_5: "5min",
    Interval.MINUTE_15: "15min",
    Interval.MINUTE_30: "30min",
    Interval.HOUR: "60min",
    Interval.HOUR_4: "4hour",
    Interval.DAILY: "1day",
    Interval.WEEKLY: "1week",
    Interval.MONTHLY: "1mon",
    Interval.YEARLY: "1year",
}

HUOBI2INTERVAL_VT = {
    "1min": Interval.MINUTE,
    "60min": Interval.HOUR,
    "1day": Interval.DAILY,
    "5min": Interval.MINUTE_5,
    "15min": Interval.MINUTE_15,
    "30min": Interval.MINUTE_30,
    "4hour": Interval.HOUR_4,
    "1week": Interval.WEEKLY,
    "1mon": Interval.MONTHLY,
    "1year": Interval.YEARLY,
}

CHINA_TZ = pytz.timezone("Asia/Shanghai")
SAUDI_TZ = pytz.timezone("Asia/Riyadh")
Singapore_TZ = pytz.timezone("Asia/Singapore")
MY_TZ = None

huobi_symbols: set = set()
symbol_name_map: Dict[str, str] = {}
currency_balance: Dict[str, float] = {}


class HuobiGateway(BaseGateway):
    """
    VN Trader Gateway for Huobi connection.
    """

    default_setting: Dict[str, Any] = {
        "API Key": "",
        "Secret Key": "",
        "会话数": 3,
        "代理地址": "",
        "代理端口": "",
    }

    exchanges: List[Exchange] = [Exchange.HUOBI]

    default_kline_intervals: List[Interval] = [Interval.MINUTE, Interval.MINUTE_5, Interval.MINUTE_30, Interval.HOUR, Interval.HOUR_4]

    def __init__(self, event_engine):
        """Constructor"""
        super().__init__(event_engine, "HUOBI")

        self.rest_api = HuobiRestApi(self)
        self.trade_ws_api = HuobiTradeWebsocketApi(self)
        self.market_ws_api = HuobiDataWebsocketApi(self)
        self.setting = self.default_setting
        self.orders: Dict[str, OrderData] = {}
        self.disconnect_count = 0

    def get_market_status(self):
        return self

    def get_order(self, orderid: str) -> OrderData:
        """"""
        return self.orders.get(orderid, None)

    def on_order(self, order: OrderData) -> None:
        """"""
        #print(self.orders)
        self.orders[order.orderid] = order
        super().on_order(order)

    def connect(self, setting: dict) -> None:
        """"""
        key = setting["API Key"]
        secret = setting["Secret Key"]
        session_number = setting["会话数"]
        proxy_host = setting["代理地址"]
        proxy_port = setting["代理端口"]
        self.setting = setting
        if proxy_port.isdigit():
            proxy_port = int(proxy_port)
        else:
            proxy_port = 0

        self.rest_api.connect(key, secret, session_number, proxy_host, proxy_port)
        self.trade_ws_api.connect(key, secret, proxy_host, proxy_port)
        self.market_ws_api.connect(key, secret, proxy_host, proxy_port)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        self.market_ws_api.subscribe(req)
        self.trade_ws_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """"""
        return self.rest_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        self.rest_api.cancel_order(req)

    def query_account(self) -> None:
        """"""
        return self.rest_api.query_account()

    def query_account_trade(self, req: AccountTradeRequest):
        return self.rest_api.query_account_trade(req)

    def query_balance(self, req: BalanceRequest):
        return self.rest_api.query_balance(req=req)

    def query_position(self) -> None:
        """"""
        pass

    def query_history(self, req: HistoryRequest):
        """"""
        return self.rest_api.query_history(req)

    def query_market_trade(self, req: HistoryRequest):
        return self.rest_api.query_market_trade(req=req)

    def close(self) -> None:
        """"""
        self.rest_api.stop()
        self.trade_ws_api.stop()
        self.market_ws_api.stop()


class HuobiRestApi(RestClient):
    """
    HUOBI REST API
    """

    def __init__(self, gateway: BaseGateway):
        """"""
        super().__init__()

        self.gateway: HuobiGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.host: str = ""
        self.key: str = ""
        self.secret: str = ""
        self.account_id: str = ""
        self.accounts = {}  # account_id: account_info

        self.order_count = 0
        self.rate_limit = 20
        self.rate_limit_expire = 0

    def new_orderid(self):
        """"""
        prefix = datetime.now().strftime("%Y%m%d-%H%M%S-")

        self.order_count += 1
        suffix = str(self.order_count).rjust(8, "0")

        orderid = prefix + suffix
        return orderid

    def sign(self, request: Request) -> Request:
        """
        Generate HUOBI signature.
        """
        request.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36"
        }
        params_with_signature = create_signature(
            self.key,
            request.method,
            self.host,
            request.path,
            self.secret,
            request.params
        )
        request.params = params_with_signature

        if request.method == "POST":
            request.headers["Content-Type"] = "application/json"

            if request.data:
                request.data = json.dumps(request.data)

        return request

    def connect(
        self,
        key: str,
        secret: str,
        session_number: int,
        proxy_host: str,
        proxy_port: int
    ) -> None:
        """
        Initialize connection to REST server.
        """
        self.key = key
        self.secret = secret

        self.host, _ = _split_url(REST_HOST)

        self.init(REST_HOST, proxy_host, proxy_port)
        self.start(session_number)

        self.gateway.write_log("REST API启动成功")

        self.query_contract()

        self.query_order()
        self.query_market_status()
        #self.query_account()

        tmp = self.query_account()
        for t in tmp:
            print(t)
            self.accounts[t.account_id] = t
            if t.account_type == 'spot':
                self.account_id = t.account_id

    def query_account_trade(self, req: AccountTradeRequest):
        '''
        {'status': 'ok',
        'data': [{'id': 261488992259212, 'symbol': 'bch3lusdt', 'account-id': 13712814, 'client-order-id': '', 'amount': '0.300000000000000000', 'price': '21.963500000000000000', 'created-at': 1619126929252, 'type': 'buy-limit', 'field-amount': '0.300000000000000000', 'field-cash-amount': '6.578160000000000000', 'field-fees': '0.000600000000000000', 'finished-at': 1619126929271, 'source': 'spot-web', 'state': 'filled', 'canceled-at': 0},
        {'id': 261493271038807, 'symbol': 'bch3lusdt', 'account-id': 13712814, 'client-order-id': '', 'amount': '0.300000000000000000', 'price': '21.660600000000000000', 'created-at': 1619126907193, 'type': 'buy-limit', 'field-amount': '0.0', 'field-cash-amount': '0.0', 'field-fees': '0.0', 'finished-at': 1619126920622, 'source': 'spot-web', 'state': 'canceled', 'canceled-at': 1619126920616}]}
        '''
        params = {}
        if req.symbol:
            params['symbol'] = req.symbol
        if req.start_time:
            params['start_time'] = req.start_time
        if req.end_time:
            params['end_time'] = req.end_time
        if req.size:
            params['size'] = req.size
        else:
            params['size'] = 1000

        # Get response from server
        resp = self.request("GET", "/v1/order/history", params=params)
        rawdata = resp.json()
        if rawdata['status'] == 'ok':
            data = rawdata['data']
            trades = []
            for d in data:
                #print(d)
                if d['state'] != 'filled':
                    continue
                if 'buy' in d['type']:
                    direction = Direction.LONG
                elif 'sell' in d['type']:
                    direction = Direction.SHORT
                else:
                    direction = Direction.NONE
                symbol = d['symbol']
                if 'market' in d['type']:
                    price = round(float(d['field-cash-amount'])/float(d['field-amount']), 8)
                    volume = round(float(d['field-amount']), 8)
                elif 'limit' in d['type']:
                    price = round(float(d['price']), 8)
                    volume = round(float(d['field-amount']), 8)
                else:
                    price = round(float(d['price']), 8)
                    volume = round(float(d['field-amount']), 8)

                #dt = generate_datetime(timestamp=d['created-at'] / 1000.0, tzinfo=MY_TZ)
                dt = generate_datetime(timestamp=d['created-at'] / 1000.0)
                # offset = Offset.NONE
                trade = TradeData(symbol=symbol,
                                  exchange=req.exchange,
                                  orderid=int(d['id']),
                                  direction=direction,
                                  price=price,
                                  volume=volume,
                                  datetime=dt,
                                  gateway_name=self.gateway_name)
                trades.append(trade)
            return trades
        else:
            print(rawdata)
            return []

    def query_market_status(self):
        self.add_request(
            method="GET",
            path="/v2/market-status",
            callback=self.on_query_market_status
        )

    def query_market_summary(self):
        self.add_request(
            method="GET",
            path="/v1/common/symbols",
            callback=self.on_query_market_summary
        )

    def query_account(self) -> List[AccountInfo]:
        """"""
        #self.add_request(method="GET", path="/v1/account/accounts", callback=self.on_query_account)
        #params = {"symbol": req.symbol, "size": 2000}
        # Get response from server
        resp = self.request("GET", "/v1/account/accounts")
        accounts = []
        rawdata = resp.json()
        if rawdata['status'] == 'ok':
            data = rawdata['data']
            for d in data:
                accinfo = AccountInfo(exchange=Exchange.HUOBI,
                                      gateway_name=self.gateway_name,
                                      account_state=d['state'],
                                      account_type=d['type'],
                                      account_subtype=d['subtype'],
                                      account_id=d['id'])
                accounts.append(accinfo)
        return accounts

    def query_balance(self, req: BalanceRequest) -> BalanceInfo:
        """"""
        account_id = req.account_id
        resp = self.request("GET", f'/v1/account/accounts/{account_id}/balance')

        rawdata = resp.json()
        if rawdata['status'] == 'ok':
            data = rawdata['data']
            account_id = data['id']
            account_type = data['type']
            account_state = data['state']
            balance_info = BalanceInfo(exchange=req.exchange,
                                       gateway_name=self.gateway_name,
                                       account_id=data['id'],
                                       account_type=data['type'],
                                       account_state=data['state'])
            # {'currency': 'lun', 'type': 'trade', 'balance': '0'}
            bdict = {}
            for d in data['list']:
                if d['currency'] not in bdict:
                    bdict[d['currency']] = {}
                bdict[d['currency']][d['type']] = float(d['balance'])

            # translate dict to BalanceData
            for cur in bdict:
                #print(bdict[cur])
                bd = BalanceData(exchange=req.exchange,
                                 gateway_name=self.gateway_name,
                                 account_id=data['id'],
                                 account_type=data['type'],
                                 account_state=data['state'],
                                 currency=cur,
                                 frozen=bdict[cur]['frozen'],
                                 available=bdict[cur]['trade'])

                balance_info.data[cur] = bd
        return balance_info

    def query_order(self) -> None:
        """"""
        self.add_request(
            method="GET",
            path="/v1/order/openOrders",
            callback=self.on_query_order
        )

    def query_contract(self) -> None:
        """"""
        self.add_request(
            method="GET",
            path="/v1/common/symbols",
            callback=self.on_query_contract
        )

    def query_market_trade(self, req: HistoryRequest) -> List[TradeData]:
        '''
        Author: Arthur
        '''
        params = {"symbol": req.symbol, "size": 2000}
        # Get response from server
        resp = self.request("GET", "/market/history/trade", params=params)
        trades = []
        if resp.status_code // 100 != 2:
            msg = f"获取历史数据失败，状态码：{resp.status_code}，信息：{resp.text}"
            self.gateway.write_log(msg)
        else:
            data = resp.json()
            if not data:
                msg = f"获取历史数据为空"
                self.gateway.write_log(msg)
            ts = data['ts']
            ch = data['ch']
            symbol = ch.split('.')[1]

            raw_trade = data['data']
            for rt in raw_trade:
                for d in rt['data']:
                    symbol = req.symbol
                    if d['direction'] == 'buy':
                        direction = Direction.LONG
                    elif d['direction'] == 'sell':
                        direction = Direction.SHORT
                    price = round(float(d['price']), 8)
                    volume = round(float(d['amount']), 8)
                    #dt = generate_datetime(timestamp=d['ts']/1000.0, tzinfo=MY_TZ)
                    dt = generate_datetime(timestamp=d['ts'] / 1000.0)
                    #offset = Offset.NONE
                    trade = TradeData(symbol=symbol,
                                      exchange=req.exchange,
                                      orderid=int(d['id']),
                                      tradeid=int(d['trade-id']),
                                      direction=direction,
                                      price=price,
                                      volume=volume,
                                      datetime=dt,
                                      gateway_name=self.gateway_name)
                    trades.append(trade)

            msg = f"Loading history trades {req.symbol}, total trades: {len(trades)}"
            self.gateway.write_log(msg)
        trades = sorted(trades, key=lambda x: x.datetime)
        #print(trades)
        return trades

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """"""
        # Create query params
        params = {
            "symbol": req.symbol,
            "period": INTERVAL_VT2HUOBI[req.interval],
            "size": 2000
        }

        # Get response from server
        resp = self.request(
            "GET",
            "/market/history/kline",
            params=params
        )

        # Break if request failed with other status code
        history = []

        if resp.status_code // 100 != 2:
            msg = f"获取历史数据失败，状态码：{resp.status_code}，信息：{resp.text}"
            self.gateway.write_log(msg)
        else:
            data = resp.json()
            if not data:
                msg = f"获取历史数据为空"
                self.gateway.write_log(msg)
            else:
                for d in data["data"]:
                    dt = generate_datetime(d["id"])

                    bar = BarData(
                        symbol=req.symbol,
                        exchange=req.exchange,
                        datetime=dt,
                        open_time=dt,
                        interval=req.interval,
                        volume=d["vol"],
                        open_price=d["open"],
                        high_price=d["high"],
                        low_price=d["low"],
                        close_price=d["close"],
                        amount=d["amount"],
                        gateway_name=self.gateway_name
                    )
                    history.append(bar)

                begin = history[0].datetime
                end = history[-1].datetime
                msg = f"获取历史数据成功，{req.symbol} - {req.interval.value}，{begin} - {end}"
                self.gateway.write_log(msg)

        history = sorted(history, key=lambda x: x.open_time)
        return history

    def send_order(self, req: OrderRequest) -> str:
        """"""
        huobi_type = ORDERTYPE_VT2HUOBI.get((req.direction, req.type), "")

        orderid = self.new_orderid()
        order = req.create_order_data(orderid, self.gateway_name)
        order.datetime = datetime.now(MY_TZ)

        data = {
            "account-id": self.account_id,
            "amount": str(req.volume),
            "symbol": req.symbol,
            "type": huobi_type,
            "price": str(req.price),
            "source": "spot-api",
            "client-order-id": orderid
        }

        #if self.rate_limit > 3 or time.time() > self.rate_limit_expire/1000.0:
        self.add_request(
            method="POST",
            path="/v1/order/orders/place",
            callback=self.on_send_order,
            data=data,
            extra=order,
            on_error=self.on_send_order_error,
            on_failed=self.on_send_order_failed
        )

        self.gateway.on_order(order)
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        data = {"client-order-id": req.orderid}

        self.add_request(
            method="POST",
            path="/v1/order/orders/submitCancelClientOrder",
            data=data,
            callback=self.on_cancel_order,
            extra=req
        )

    def on_query_market_status(self, data: dict, request: Request):
        """"""
        '''
        {
            "code": 200,
            "message": "success",
            "data": {
                "marketStatus": 1
            }
        }
        '''
        # 市场状态（1=normal, 2=halted, 3=cancel-only）
        market_status = data["data"]["marketStatus"]
        if market_status == 1:
            self.gateway.write_log(f"Market Status: normal")
        elif market_status == 2:
            self.gateway.write_log(f"Market Status: halted")
        elif market_status == 3:
            self.gateway.write_log(f"Market Status: cancel-only")
        else:
            self.gateway.write_log(f"Market Status: Unknown")

    def on_query_account_trade(self, data: dict, request: Request = None) -> None:
        pass

    def on_query_account(self, data: dict, request: Request = None) -> None:
        """"""
        if self.check_error(data, "查询账户"):
            return
        accounts = []
        for d in data["data"]:
            account_id = d["id"]
            account_state = d["state"]
            account_type = d["type"]
            account_subtype = d["subtype"]
            ad = AccountData(gateway_name=self.gateway_name,
                             exchange=Exchange.HUOBI,
                             account_id=account_id,
                             account_state=account_state,
                             account_type=account_type,
                             account_subtype=account_subtype)
            self.accounts[ad.account_id] = ad
            #print('huobi_gateway:', ad)
            #self.gateway.on_account(ad)
            accounts.append(ad)
        return accounts

    def on_query_balance(self, data: dict) -> None:
        if self.check_error(data, "Query Balance"):
            return
        rawdata = data['data']
        accid = rawdata['id']
        acctype = rawdata['type']
        accstatus = rawdata['status']
        ballist = rawdata['list']
        for bal in ballist:
            currency = bal['currency']
            exchange = Exchange.HUOBI
            baltype = bal['type']
            if baltype == 'frozen':
                frozen = float(bal['balance'])
                available = None
            elif baltype == 'trade':
                frozen = None
                available = float(bal['balance'])

            bd = BalanceData(currency=currency, exchange=exchange,
                             account_type=acctype, account_id=accid, account_state=accstatus,
                             frozen=frozen, available=available)
            #self.accounts[accid].update_balance(balance_data=bd)
            #self.gateway.on_account(account=self.accounts[accid])
            self.gateway.on_balance(balance_data=bd)

    def on_query_order(self, data: dict, request: Request) -> None:
        """"""
        if self.check_error(data, "查询委托"):
            return

        for d in data["data"]:
            direction, order_type = ORDERTYPE_HUOBI2VT[d["type"]]
            dt = generate_datetime(d["created-at"] / 1000)

            order = OrderData(
                orderid=d["client-order-id"],
                symbol=d["symbol"],
                exchange=Exchange.HUOBI,
                price=float(d["price"]),
                volume=float(d["amount"]),
                type=order_type,
                direction=direction,
                traded=float(d["filled-amount"]),
                status=STATUS_HUOBI2VT.get(d["state"], None),
                datetime=dt,
                gateway_name=self.gateway_name,
            )

            self.gateway.on_order(order)

        self.gateway.write_log("委托信息查询成功")

    def on_query_contract(self, data: dict, request: Request) -> None:
        """"""
        if self.check_error(data, "查询合约"):
            return

        for d in data["data"]:
            base_currency = d["base-currency"]
            quote_currency = d["quote-currency"]
            name = f"{base_currency.upper()}/{quote_currency.upper()}"
            pricetick = 1 / pow(10, d["price-precision"])
            min_volume = 1 / pow(10, d["amount-precision"])

            contract = ContractData(
                symbol=d["symbol"],
                exchange=Exchange.HUOBI,
                name=name,
                pricetick=pricetick,
                size=1,
                min_volume=min_volume,
                product=Product.SPOT,
                history_data=True,
                gateway_name=self.gateway_name,
            )
            self.gateway.on_contract(contract)

            huobi_symbols.add(contract.symbol)
            symbol_name_map[contract.symbol] = contract.name

        self.gateway.write_log("合约信息查询成功")

    def on_send_order(self, data: dict, request: Request) -> None:
        """"""
        order = request.extra

        #print(request.headers)
        #self.rate_limit = request.headers['X-HB-RateLimit-Requests-Remain']
        #self.rate_limit_expire = request.headers['X-HB-RateLimit-Requests-Expire']

        if self.check_error(data, "委托"):
            order.status = Status.REJECTED
            self.gateway.on_order(order)

    def on_send_order_failed(self, status_code: str, request: Request) -> None:
        """
        Callback when sending order failed on server.
        """
        order = request.extra
        order.status = Status.REJECTED
        self.gateway.on_order(order)

        msg = f"委托失败，状态码：{status_code}，信息：{request.response.text}"
        self.gateway.write_log(msg)

    def on_send_order_error(
        self,
        exception_type: type,
        exception_value: Exception,
        tb,
        request: Request
    ) -> None:
        """
        Callback when sending order caused exception.
        """
        order = request.extra
        order.status = Status.REJECTED
        self.gateway.on_order(order)

        # Record exception if not ConnectionError
        if not issubclass(exception_type, ConnectionError):
            self.on_error(exception_type, exception_value, tb, request)

    def on_cancel_order(self, data: dict, request: Request) -> None:
        """"""
        cancel_request = request.extra
        order = self.gateway.get_order(cancel_request.orderid)
        if not order:
            return

        if self.check_error(data, "撤单"):
            order.status = Status.REJECTED
        else:
            order.status = Status.CANCELLED
            self.gateway.write_log(f"委托撤单成功：{order.orderid}")

        self.gateway.on_order(order)

    def on_error(
        self,
        exception_type: type,
        exception_value: Exception,
        tb,
        request: Request
    ) -> None:
        """
        Callback to handler request exception.
        """
        msg = f"触发异常，状态码：{exception_type}，信息：{exception_value}"
        self.gateway.write_log(msg)

        sys.stderr.write(
            self.exception_detail(exception_type, exception_value, tb, request)
        )

    def check_error(self, data: dict, func: str = "") -> bool:
        """"""
        if data["status"] != "error":
            return False

        error_code = data["err-code"]
        error_msg = data["err-msg"]

        self.gateway.write_log(f"{func}请求出错，代码：{error_code}，信息：{error_msg}")
        return True


class HuobiWebsocketApiBase(WebsocketClient):
    """"""

    def __init__(self, gateway):
        """"""
        super().__init__()

        self.gateway: HuobiGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.key: str = ""
        self.secret: str = ""
        self.sign_host: str = ""
        self.path: str = ""
        self.disconnect_count = 0

    def connect(
        self,
        key: str,
        secret: str,
        url: str,
        proxy_host: str,
        proxy_port: int
    ) -> None:
        """"""
        self.key = key
        self.secret = secret

        host, path = _split_url(url)
        self.sign_host = host
        self.path = path

        #print(self.gateway.setting)

        self.init(url, proxy_host, proxy_port)
        self.start()

    def login(self) -> int:
        """"""
        params = create_signature_v2(
            self.key,
            "GET",
            self.sign_host,
            self.path,
            self.secret
        )
        print(params)
        req = {
            "action": "req",
            "ch": "auth",
            "params": params
        }

        return self.send_packet(req)

    def on_login(self, packet: dict) -> None:
        """"""
        pass

    @staticmethod
    def unpack_data(data):
        """"""
        if isinstance(data, bytes):
            buf = zlib.decompress(data, 31)
        else:
            buf = data

        return json.loads(buf)

    def on_packet(self, packet: dict):
        """"""
        #print(packet)
        if "ping" in packet:
            req = {"pong": packet["ping"]}
            self.send_packet(req)
        elif "action" in packet and packet["action"] == "ping":
            req = {
                "action": "pong",
                "ts": packet["data"]["ts"]
            }
            self.send_packet(req)
        elif "err-msg" in packet:
            return self.on_error_msg(packet)
        elif "action" in packet and packet["action"] == "req":
            return self.on_login(packet)
        else:
            self.on_data(packet)

    def on_data(self, packet: dict) -> None:
        """"""
        print("data : {}".format(packet))

    def on_error_msg(self, packet: dict) -> None:
        """"""
        msg = packet["err-msg"]
        if msg == "invalid pong":
            return

        self.gateway.write_log(packet["err-msg"])


class HuobiTradeWebsocketApi(HuobiWebsocketApiBase):
    """"""
    def __init__(self, gateway):
        """"""
        super().__init__(gateway)

        self.req_id: int = 0
        self.symbols = []

    def connect(
        self,
        key: str,
        secret: str,
        proxy_host: str,
        proxy_port: int
    ):
        """"""
        super().connect(
            key,
            secret,
            WEBSOCKET_TRADE_HOST,
            proxy_host,
            proxy_port
        )

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        self.req_id += 1
        if req.symbol not in self.symbols:
            self.symbols.append(req.symbol)
        req = {
            "action": "sub",
            "ch": f"orders#{req.symbol}"
        }
        self.send_packet(req)

    def subscribe_order_update(self, req: SubscribeRequest) -> None:
        """"""
        self.req_id += 1
        req = {
            "action": "sub",
            "ch": f"orders#{req.symbol}"
        }
        self.send_packet(req)

    def subscribe_account_update(self) -> None:
        """"""
        req = {
            "action": "sub",
            "ch": "accounts.update#2"
        }
        self.send_packet(req)

    def on_connected(self) -> None:
        """"""
        self.gateway.write_log("交易Websocket API连接成功")
        self.login()

    def on_disconnected(self) -> None:
        """"""
        self.gateway.write_log("交易Websocket API失去连接")
        #self.gateway.close()
        #self.gateway.trade_ws_api.stop()

        self.disconnect_count += 1
        time.sleep(10 * (self.disconnect_count + 1))
        if self.disconnect_count > 5:
            time.sleep(300)
            self.disconnect_count = 0

        self.login()
        self.connect(key=self.key, secret=self.secret, proxy_host=self.proxy_host, proxy_port=self.proxy_port)

        for symbol in self.symbols:
            self.gateway.write_log(f"Trade Subscribe {symbol}")
            req = SubscribeRequest(symbol=symbol, exchange=Exchange.HUOBI)
            self.subscribe(req=req)
        self.subscribe_account_update()

        #self.join()

    def on_login(self, packet: dict) -> None:
        """"""
        print('交易', packet)
        if "data" in packet and not packet["data"]:
            self.gateway.write_log("交易Websocket API登录成功")
            self.subscribe_account_update()
        else:
            msg = packet["message"]
            error_msg = f"交易Websocket API登录失败，原因：{msg}"
            self.gateway.write_log(error_msg)

    def on_data(self, packet: dict) -> None:
        """"""
        #print(packet)
        if "sub" in packet["action"]:
            return

        ch = packet["ch"]
        if "orders" in ch:
            #print(packet["data"])
            self.on_order(packet["data"])
        elif "accounts" in ch:
            self.on_account(packet["data"])
        else:
            pass

    def on_balance(self, data: dict) -> None:
        pass

    def on_account(self, data: dict) -> None:
        """"""
        if not data:
            return

        #print(data)
        currency = data["currency"]
        accound_id = data["accountId"]
        change_type = data["changeType"]
        account_type = data["accountType"]
        change_time = data["changeTime"]
        # {'currency': 'usdt', 'accountId': 263903, 'balance': '1159.027494073183439048', 'changeType': 'order.match', 'accountType': 'trade', 'changeTime': 1613386265650}
        ad = AccountData(
            exchange=Exchange.HUOBI,
            account_id=accound_id,
            currency=currency,
            accountid=currency,
            account_type=account_type,
            gateway_name=self.gateway_name,
        )
        if change_type:
            if 'balance' in data:
                balance = float(data['balance'])
                ad.balance = balance
            if 'available' in data:
                available = float(data['available'])
                ad.available = available
        self.gateway.on_account(ad)

    def parse_trigger(self, data):
        '''
        {
            "orderSide":"buy",
            "lastActTime":1583853365586,
            "clientOrderId":"abc123",
            "orderStatus":"rejected",
            "symbol":"btcusdt",
            "eventType":"trigger",
            "errCode": 2002,
            "errMessage":"invalid.client.order.id (NT)"
        }
        '''
        order_side = data['orderSize']
        #order_time = generate_datetime(data['lastActTime'], tzinfo=MY_TZ)
        order_time = generate_datetime(data['lastActTime'])
        order_status = STATUS_HUOBI2VT[data['orderStatus']]
        #print(data)

    def parse_deletion(self, data):
        '''
        {'execAmt': '0',
        'lastActTime': 1613997683048,
        'orderPrice': '40',
        'orderSize': '1',
        'remainAmt': '1',
        'orderSource': 'spot-android',
        'clientOrderId': '', 'orderId': 218594525426735,
        'orderStatus': 'canceled', 'eventType': 'cancellation',
         'symbol': 'bch3lusdt', 'type': 'sell-limit'}
        '''
        #print(data)
        symbol = data['symbol']
        time_in_s = data['lastActTime'] / 1000.0
        #order_time = generate_datetime(time_in_s, tzinfo=MY_TZ)
        order_time = generate_datetime(time_in_s)
        order_status = STATUS_HUOBI2VT[data['orderStatus']]
        order_type = data['type']
        vt_type = ORDERTYPE_HUOBI2VT[data['type']]
        order_id = data['orderId']
        order_price = float(data['orderPrice'])
        if 'buy' in order_type:
            direction = Direction.LONG
        elif 'sell' in order_type:
            direction = Direction.SHORT
        else:
            pass

        if 'limit' in order_type:
            order_size = float(data['orderSize'])
            order_value = order_size * order_price
        elif 'market' in order_type:
            order_value = float(data['orderValue'])
            order_size = order_value / order_price
        elif 'ioc' in order_type:
            order_size = float(data['orderSize'])
            order_value = order_size * order_price
        else:
            order_size = float(data['orderSize'])
            order_value = order_size * order_price

        od = OrderData(gateway_name=self.gateway_name,
                       symbol=symbol,
                       exchange=Exchange.HUOBI,
                       orderid=order_id,
                       type=vt_type[1],
                       price=order_price,
                       volume=order_size,
                       direction=direction,
                       status=order_status,
                       datetime=order_time)
        return od

    def parse_creation(self, data):
        symbol = data['symbol']
        account_id = data['accountId']
        order_id = data['orderId']
        client_order_id = data['clientOrderId']
        order_source = data['orderSource']

        order_type = data['type']
        order_status = STATUS_HUOBI2VT[data['orderStatus']]
        time_in_s = data['orderCreateTime']/1000.0
        #order_time = generate_datetime(time_in_s, tzinfo=MY_TZ)
        order_time = generate_datetime(time_in_s)
        order_value = 0
        order_size = 0
        order_price = 0

        if 'buy' in order_type:
            direction = Direction.LONG
        elif 'sell' in order_type:
            direction = Direction.SHORT
        else:
            pass
        vt_type = ORDERTYPE_HUOBI2VT[data['type']]
        if 'limit' in order_type:
            order_type_vt = OrderType.LIMIT
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            order_value = order_size * order_price
        elif 'market' in order_type:
            order_type_vt = OrderType.MARKET
            if 'buy' in order_type:
                order_value = float(data['orderValue'])
            if 'sell' in order_type:
                order_size = float(data['orderSize'])
            order_price = 0
            #order_size = order_value / order_price
        elif 'ioc' in order_type:
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            order_value = order_size * order_price
        else:
            print(data)
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            order_value = order_size * order_price

        od = OrderData(gateway_name=self.gateway_name,
                       symbol=symbol,
                       exchange=Exchange.HUOBI,
                       orderid=order_id,
                       type=vt_type[1],
                       direction=direction,
                       price=order_price,
                       volume=order_size,
                       traded=order_value,
                       status=order_status,
                       datetime=order_time)
        return od

    def parse_trade(self, data):
        '''
        {'tradePrice': '41.3037', 'tradeVolume': '0.0171',
        'tradeTime': 1613490112635, 'aggressor': False,
        'execAmt': '0.0171', 'tradeId': 3372275,
        'orderPrice': '41.3037', 'orderSize': '0.2',
        'remainAmt': '0.1829', 'orderSource': 'spot-android',
        'clientOrderId': '', 'orderId': 206678784129560,
        'orderStatus': 'partial-filled', 'eventType': 'trade',
        'symbol': 'bch3lusdt', 'type': 'buy-limit'}
        '''
        symbol = data['symbol']
        exchange = Exchange.HUOBI
        order_id = data['orderId']
        order_status = STATUS_HUOBI2VT[data['orderStatus']]
        order_type = data['type']
        time_in_s = data['tradeTime'] / 1000.0
        #order_time = generate_datetime(time_in_s, tzinfo=MY_TZ)
        order_time = generate_datetime(time_in_s)

        if 'buy' in order_type:
            direction = Direction.LONG
        elif 'sell' in order_type:
            direction = Direction.SHORT
        else:
            pass
        vt_type = ORDERTYPE_HUOBI2VT[data['type']]

        if 'limit' in order_type:
            order_type_vt = OrderType.LIMIT
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            #order_volume = float(data['remainAmt'])
            trade_price = data['tradePrice']
            trade_volume = order_size
            remain_amount = float(data['remainAmt'])
            exec_amount = float(data['execAmt'])
            traded_value = order_price * exec_amount
        elif 'ioc' in order_type:
            order_type_vt = OrderType.IOC
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            # order_volume = float(data['remainAmt'])
            trade_price = data['tradePrice']
            trade_volume = order_size
            remain_amount = float(data['remainAmt'])
            exec_amount = float(data['execAmt'])
            traded_value = order_price * exec_amount
        elif 'fok' in order_type:
            order_type_vt = OrderType.FOK
            order_price = float(data['orderPrice'])
            order_size = float(data['orderSize'])
            # order_volume = float(data['remainAmt'])
            trade_price = data['tradePrice']
            trade_volume = order_size
            remain_amount = float(data['remainAmt'])
            exec_amount = float(data['execAmt'])
            traded_value = order_price * exec_amount
        elif 'market' in order_type:
            order_type_vt = OrderType.MARKET
            trade_price = float(data['tradePrice'])
            trade_volume = float(data['tradeVolume'])
            remain_amount = float(data['remainAmt'])
            exec_amount = float(data['execAmt'])
            traded_value = trade_price * trade_volume
        else:
            pass
        od = OrderData(gateway_name=self.gateway_name,
                       symbol=symbol, exchange=Exchange.HUOBI,
                       orderid=order_id, type=vt_type[1],
                       direction=direction, price=trade_price,
                       volume=trade_volume, traded=traded_value,
                       remain_amount=remain_amount,
                       exec_amount=exec_amount,
                       status=order_status, datetime=order_time)
        return od

    def gen_huobi_order(self, data: dict):
        '''
        limit order:
        {'accountId': 263903, 'orderPrice': '42.8042', 'orderSize': '0.2',
        'orderCreateTime': 1613476719841, 'orderSource': 'spot-android',
        'clientOrderId': '', 'orderId': 204565155967518,
        'orderStatus': 'submitted',
        'eventType': 'creation', 'symbol': 'bch3lusdt', 'type': 'buy-limit'}

        buy market:
        {'tradePrice': '42.8981', 'tradeVolume': '0.116555278672015776',
        'tradeTime': 1613489430415, 'aggressor': True,
        'execAmt': '4.99999999999999996',
        'tradeId': 3372044, 'orderValue': '5',
        'remainAmt': '0.00000000000000004',
        'orderSource': 'spot-android',
        'clientOrderId': '', 'orderId': 206678683466465,
        'orderStatus': 'filled', 'eventType': 'trade',
        'symbol': 'bch3lusdt', 'type': 'buy-market'}

        order partially filled
        {'tradePrice': '41.3037', 'tradeVolume': '0.0171',
        'tradeTime': 1613490112635, 'aggressor': False,
        'execAmt': '0.0171', 'tradeId': 3372275,
        'orderPrice': '41.3037', 'orderSize': '0.2',
        'remainAmt': '0.1829', 'orderSource': 'spot-android',
        'clientOrderId': '', 'orderId': 206678784129560,
        'orderStatus': 'partial-filled', 'eventType': 'trade',
        'symbol': 'bch3lusdt', 'type': 'buy-limit'}

        '''
        #print(data)
        event_type = data['eventType']
        if event_type == 'trigger':
            pass
        elif event_type == 'deletion':
            od = self.parse_deletion(data)
        elif event_type == 'creation':
            od = self.parse_creation(data)
        elif event_type == 'trade':
            od = self.parse_trade(data)
        elif event_type == 'cancellation':
            od = self.parse_deletion(data)
        return od

    def on_order(self, data: dict) -> None:
        """"""
        # process order data
        od = self.gen_huobi_order(data)
        self.gateway.on_order(od)
        order = self.gateway.get_order(od.orderid)

        # process trade data
        if order.status == Status.ALLTRADED or order.status == Status.PARTTRADED:
            trade = TradeData(
                symbol=order.symbol,
                exchange=Exchange.HUOBI,
                orderid=order.orderid,
                tradeid=str(data["tradeId"]),
                direction=order.direction,
                price=float(data["tradePrice"]),
                volume=float(data["tradeVolume"]),
                datetime=datetime.now(MY_TZ),
                gateway_name=self.gateway_name,
            )
            print(trade)
            self.gateway.on_trade(trade)


class HuobiDataWebsocketApi(HuobiWebsocketApiBase):
    """"""

    # default_kline_intervals: List[Interval] = [Interval.MINUTE,
    #                                            Interval.MINUTE_5,
    #                                            Interval.MINUTE_15,
    #                                            Interval.MINUTE_30,
    #                                            Interval.HOUR,
    #                                            Interval.HOUR_4,
    #                                            Interval.DAILY,
    #                                            Interval.WEEKLY,
    #                                            Interval.MONTHLY,
    #                                            Interval.YEARLY]
    default_kline_intervals: List[Interval] = [Interval.MINUTE]

    def __init__(self, gateway):
        """"""
        super().__init__(gateway)

        self.req_id: int = 0
        self.ticks: Dict[str, TickData] = {}
        self.klines: Dict[str, BarData] = {}
        self.trades: Dict[str, TradeData] = {}
        #self.disconnect_count = 0

    def connect(self, key: str, secret: str, proxy_host: str, proxy_port: int) -> None:
        """"""
        print(key)
        print(secret)
        print(proxy_host)
        print(proxy_port)
        super().connect(
            key,
            secret,
            WEBSOCKET_DATA_HOST,
            proxy_host,
            proxy_port
        )

    def on_connected(self) -> None:
        """"""
        self.gateway.write_log("行情Websocket API连接成功")

    def on_disconnected(self) -> None:
        """"""
        self.gateway.write_log("行情Websocket API失去连接")
        print("行情Websocket API失去连接")
        self.disconnect_count += 1
        time.sleep(10*(self.disconnect_count+1))
        if self.disconnect_count > 5:
            time.sleep(300)
            self.disconnect_count = 0

        self.login()
        self.connect(key=self.key, secret=self.secret, proxy_host=self.proxy_host, proxy_port=self.proxy_port)
        for symbol in self.klines:
            self.gateway.write_log(f"Data Subscribe {symbol}")
            req = SubscribeRequest(symbol=symbol, exchange=Exchange.HUOBI)
            self.subscribe(req=req)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        symbol = req.symbol

        # Create tick data buffer
        tick = TickData(
            symbol=symbol,
            name=symbol_name_map.get(symbol, ""),
            exchange=Exchange.HUOBI,
            datetime=datetime.now(MY_TZ),
            gateway_name=self.gateway_name,
        )
        self.ticks[symbol] = tick

        # create kline buffer
        bar = BarData(symbol=symbol,
                      exchange=Exchange.HUOBI,
                      datetime=datetime.now(MY_TZ),
                      gateway_name=self.gateway_name)

        self.klines[symbol] = bar

        # create market trades buffer
        market_trade = TradeData(symbol=symbol,
                                 exchange=Exchange.HUOBI,
                                 datetime=datetime.now(MY_TZ),
                                 gateway_name=self.gateway_name, orderid='', tradeid='')

        self.trades[symbol] = market_trade

        # Subscribe to market depth update
        self.req_id += 1
        req = {"sub": f"market.{symbol}.depth.step0", "id": str(self.req_id)}
        print(req)
        self.send_packet(req)

        # Subscribe to market detail update
        self.req_id += 1
        req = {"sub": f"market.{symbol}.detail", "id": str(self.req_id)}
        print(req)
        self.send_packet(req)

        # Subscribe to kline 1min, 5min, 15min, 30min, 60min, 4hour, 1day, 1mon, 1week, 1year
        for ii in self.default_kline_intervals:
            self.req_id += 1
            req = {"sub": f"market.{symbol}.kline.{INTERVAL_VT2HUOBI[ii]}", "id": str(self.req_id)}
            print(req)
            self.send_packet(req)

        # subscribe market trades
        self.req_id += 1
        req = {"sub": f"market.{symbol}.trade.detail", "id": str(self.req_id)}
        print(req)
        self.send_packet(req)

        # subscribe mbp market data
        # market.$symbol.mbp.$levels
        self.req_id += 1
        levels = 150
        req = {"sub": f"market.{symbol}.mbp.{levels}", "id": str(self.req_id)}
        print(req)
        self.send_packet(req)

        # subscribe mbp
        # market.$symbol.mbp.refresh.$levels
        self.req_id += 1
        levels = 20
        req = {"sub": f"market.{symbol}.mbp.refresh.{levels}", "id": str(self.req_id)}
        print(req)
        self.send_packet(req)

    def on_data(self, packet: dict) -> None:
        """"""
        #print(packet)
        channel = packet.get("ch", None)
        if channel:
            if "depth.step" in channel:
                self.on_market_depth(packet)
            elif "detail" in channel:
                if "trade" in channel:
                    self.on_market_trade(packet)
                else:
                    self.on_market_detail(packet)
            elif "kline" in channel:
                self.on_kline(packet)
            elif "market" in channel:
                if 'mbp' in channel:
                    if 'refresh' in channel:
                        self.on_mbp_refresh(packet)
                    else:
                        self.on_mbp_incremental(packet)
        elif "err-code" in packet:
            code = packet["err-code"]
            msg = packet["err-msg"]
            self.gateway.write_log(f"错误代码：{code}, 错误信息：{msg}")
        else:
            pass

    def on_mbp_refresh(self, data: dict) -> None:
        #print('on_mbp_refresh')
        symbol = data["ch"].split(".")[1]
        tick = data['tick']
        ts = data['ts']
        #time = generate_datetime(ts/1000, tzinfo=MY_TZ)
        time = generate_datetime(ts / 1000)
        seq_num = tick['seqNum']
        if 'bids' in tick:
            bids_list = tick['bids']
            bids = {}
            for d in bids_list:
                bids[d[0]] = d[1]
        if 'asks' in tick:
            asks_list = tick['asks']
            asks = {}
            for d in asks_list:
                asks[d[0]] = d[1]
        order_book = OrderBookData(symbol=symbol, exchange=Exchange.HUOBI, gateway_name=self.gateway_name,
                                   time=time, seq_num=seq_num, pre_seq_num=0, bids=bids, asks=asks)
        self.gateway.on_order_book(order_book=order_book)

    def on_mbp_incremental(self, data: dict) -> None:
        #print('on_mbp_incremental')
        symbol = data["ch"].split(".")[1]
        tick = data['tick']
        ts = data['ts']
        #time = generate_datetime(ts/1000, tzinfo=MY_TZ)
        time = generate_datetime(ts / 1000)
        seq_num = tick['seqNum']
        pre_seq_num = tick['prevSeqNum']
        if 'bids' in tick:
            bids_list = tick['bids']
            bids = {}
            for d in bids_list:
                bids[d[0]] = d[1]
        if 'asks' in tick:
            asks_list = tick['asks']
            asks = {}
            for d in asks_list:
                asks[d[0]] = d[1]
        order_book = OrderBookData(symbol=symbol, exchange=Exchange.HUOBI, gateway_name=self.gateway_name,
                                   time=time, seq_num=seq_num, pre_seq_num=pre_seq_num, bids=bids, asks=asks)
        self.gateway.on_order_book(order_book=order_book)

    def on_market_depth(self, data: dict) -> None:
        """行情深度推送 """
        symbol = data["ch"].split(".")[1]
        tick = self.ticks[symbol]
        tick.datetime = generate_datetime(data["ts"] / 1000)

        bids = data["tick"]["bids"]
        for n in range(5):
            price, volume = bids[n]
            tick.__setattr__("bid_price_" + str(n + 1), float(price))
            tick.__setattr__("bid_volume_" + str(n + 1), float(volume))

        asks = data["tick"]["asks"]
        for n in range(5):
            price, volume = asks[n]
            tick.__setattr__("ask_price_" + str(n + 1), float(price))
            tick.__setattr__("ask_volume_" + str(n + 1), float(volume))

        if tick.last_price:
            self.gateway.on_tick(copy(tick))

    def on_market_detail(self, data: dict) -> None:
        """市场细节推送"""
        symbol = data["ch"].split(".")[1]
        tick = self.ticks[symbol]
        tick.datetime = generate_datetime(data["ts"] / 1000)

        tick_data = data["tick"]
        tick.open_price = float(tick_data["open"])
        tick.high_price = float(tick_data["high"])
        tick.low_price = float(tick_data["low"])
        tick.last_price = float(tick_data["close"])
        tick.volume = float(tick_data["vol"])

        if tick.bid_price_1:
            self.gateway.on_tick(copy(tick))

    def on_market_trade(self, data: dict):
        symbol = data['ch'].split('.')[1]
        market_trade = self.trades[symbol]
        trade_data = data['tick']['data']
        #print(data)
        for td in trade_data:
            price = td['price']
            volume = td['amount']
            tradeid = td['tradeId']
            #market_trade.datetime = generate_datetime(td["ts"] / 1000, tzinfo=MY_TZ)
            market_trade.datetime = generate_datetime(td["ts"] / 1000)
            market_trade.price = price
            market_trade.volume = volume
            market_trade.tradeid = tradeid
            raw_direction = td['direction']
            if raw_direction == 'buy':
                direction = Direction.LONG
            elif raw_direction == 'sell':
                direction = Direction.SHORT
            market_trade.direction = direction
            self.gateway.on_market_trade(copy(market_trade))

    def on_kline(self, data: dict):
        '''
        :param data:
        :return:
        '''
        symbol = data["ch"].split(".")[1]
        bar = BarData(symbol=symbol, exchange=Exchange.HUOBI,
                      datetime=generate_datetime(data["ts"] / 1000),
                      gateway_name=self.gateway_name)
        bar.interval = HUOBI2INTERVAL_VT[data["ch"].split(".")[3]]
        bar.volume = data["tick"]["vol"]
        bar.open_price = data["tick"]["open"]
        bar.close_price = data["tick"]["close"]
        bar.high_price = data["tick"]["high"]
        bar.low_price = data["tick"]["low"]
        bar.count = data["tick"]["count"]
        bar.amount = data["tick"]["amount"]
        bar.open_time = generate_datetime(data["tick"]["id"])
        self.gateway.on_kline(copy(bar))


def _split_url(url):
    """
    将url拆分为host和path
    :return: host, path
    """
    result = re.match("\w+://([^/]*)(.*)", url)  # noqa
    if result:
        return result.group(1), result.group(2)


def create_signature(
    api_key,
    method,
    host,
    path,
    secret_key,
    get_params=None
) -> Dict[str, str]:
    """
    创建签名
    :param get_params: dict 使用GET方法时附带的额外参数(urlparams)
    :return:
    """
    sorted_params = [
        ("AccessKeyId", api_key),
        ("SignatureMethod", "HmacSHA256"),
        ("SignatureVersion", "2"),
        ("Timestamp", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
    ]

    if get_params:
        sorted_params.extend(list(get_params.items()))
        sorted_params = list(sorted(sorted_params))
    encode_params = urllib.parse.urlencode(sorted_params)

    payload = [method, host, path, encode_params]
    payload = "\n".join(payload)
    payload = payload.encode(encoding="UTF8")

    secret_key = secret_key.encode(encoding="UTF8")

    digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest)

    params = dict(sorted_params)
    params["Signature"] = signature.decode("UTF8")
    return params


def create_signature_v2(
    api_key,
    method,
    host,
    path,
    secret_key,
    get_params=None
) -> Dict[str, str]:
    """
    创建签名
    :param get_params: dict 使用GET方法时附带的额外参数(urlparams)
    :return:
    """
    sorted_params = [
        ("accessKey", api_key),
        ("signatureMethod", "HmacSHA256"),
        ("signatureVersion", "2.1"),
        ("timestamp", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
    ]

    if get_params:
        sorted_params.extend(list(get_params.items()))
        sorted_params = list(sorted(sorted_params))
    encode_params = urllib.parse.urlencode(sorted_params)

    payload = [method, host, path, encode_params]
    payload = "\n".join(payload)
    payload = payload.encode(encoding="UTF8")

    secret_key = secret_key.encode(encoding="UTF8")

    digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest)

    params = dict(sorted_params)
    params["authType"] = "api"
    params["signature"] = signature.decode("UTF8")
    return params


def generate_datetime(timestamp: float, tzinfo=None) -> datetime:
    """"""
    dt = datetime.fromtimestamp(timestamp)
    dt = dt.replace(tzinfo=tzinfo)
    return dt
