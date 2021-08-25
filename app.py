import json
import config
import decimal
import math
import requests
import hashlib

from flask import Flask, request, render_template, session, redirect, flash
from flask_session import Session
from binance.client import Client
from binance.enums import *
from decimal import Decimal as D, ROUND_DOWN, ROUND_UP

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from pprint import pprint


app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def initFirebase():
    cred = credentials.Certificate(
        "bot-binance-258c3-firebase-adminsdk-uqdjc-6f00a02905.json")
    firebase_admin.initialize_app(cred)


init = initFirebase()


def orderV1(side, quantity, symbol,  bot_token, bot_id, binance_api_key, binance_api_secret, order_type=ORDER_TYPE_MARKET):
    client = Client(binance_api_key, binance_api_secret)
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        order = client.create_order(
            symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        telegram_bot_sendtext(
            "an exception occured - {}".format(e), bot_token, bot_id)
        return False

    return order


def order(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    client = Client(config.API_KEY, config.API_SECRET)
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        order = client.create_order(
            symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        telegram_bot_sendtext(
            "an exception occured - {}".format(e))
        return False

    return order


def telegram_bot_sendtext_admin(bot_message):

    bot_token = config.BOT_TOKEN
    bot_chatID = config.BOT_ID
    send_text = 'https://api.telegram.org/bot' + bot_token + \
        '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()


def telegram_bot_sendtext(bot_message, bot_token, bot_id):

    bot_token = bot_token
    bot_chatID = bot_id
    send_text = 'https://api.telegram.org/bot' + bot_token + \
        '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()


@app.route('/webhookV1', methods=['POST'])
def webhookV1():

    try:

        data = json.loads(request.data)
        # return data
        username = data['username']
        password = data['password']
        passphrase = data['passphrase']
        # confirm passphrase
        db = firestore.client()

        user_collection = db.collection(u'users')
        docs = user_collection.where(u'username', u'==', username).get()

        if len(docs) == 0:
            telegram_bot_sendtext_admin(
                f"Error : Usename or password does not exist!\n User : {username}")
            return {
                "status": "Error",
                "message": "Usename or password does not exist!"
            }

        doc = []
        doc_id = ''
        for o in docs:
            doc = o.to_dict()
            doc_id = o.id

        account = False
        if (hashlib.md5(password.encode()).hexdigest() == doc['password']):
            account = True

        if account == False:
            telegram_bot_sendtext_admin(
                f"Error : Usename or password does not exist!\n User : {username}")
            return {
                "status": "Error Pass",
                "message": "Usename or password does not exist!"
            }

        binance_api_key = doc['binance_api_key']
        binance_api_secret = doc['binance_api_secret']
        telegram_bot_id = doc['telegram_bot_id']
        telegram_bot_token = doc['telegram_bot_token']
        webhook_passphrase = doc['webhook_passphrase']
        is_active = doc['is_active']

        if is_active == False:
            telegram_bot_sendtext_admin(
                f"Error : Usename or password does not exist!\n User : {username}")
            return {
                "status": "Error",
                "message": "User is not active"
            }

        if data['passphrase'] != webhook_passphrase:
            telegram_bot_sendtext(
                "Dangerous! : Someone is trying to use the api.", telegram_bot_token, telegram_bot_id)
            return {
                "error": "error",
                "message": "Nice try!, invalid"
            }

        if binance_api_key == None or binance_api_secret == None:
            telegram_bot_sendtext(
                "Error! : Please check binance api information!", telegram_bot_token, telegram_bot_id)
            return {
                "error": "error",
                "message": "Nice try!, invalid"
            }

        client = Client(binance_api_key, binance_api_secret)

        # chage side buy or sell to upper case
        side = data['strategy']['order_action'].upper()

        # exchange symbol BNBUSDT
        exchange = data['exchange']

        # coin symbol
        symbol = data['symbol']

        # amount buy/usdt
        usdt = float(data['usdt'])

        # minimum buy in binance
        if usdt <= 10:
            telegram_bot_sendtext(
                f" ERROR : {side} -> {exchange} -> USDT must be over than 10 usdt")
            return {
                "code": "warning",
                "message": "USDT must be over than 10 usdt"
            }

        # recent trade
        recent_trade = client.get_my_trades(symbol=exchange, limit=1)
        price = float(data['strategy']['order_price'])
        # quantity for buy
        quantity = usdt / price
        quantity = round(quantity, 6)
        # telegram_bot_sendtext(
        #     f"USDT : {usdt}", telegram_bot_token, telegram_bot_id)
        # telegram_bot_sendtext(
        #     f"PRICE : {price}", telegram_bot_token, telegram_bot_id)
        # telegram_bot_sendtext(
        #     f"quantity : {quantity}", telegram_bot_token, telegram_bot_id)

        print(usdt)
        print(price)
        print(quantity)
        # get asset balance with param
        asset_balance = client.get_asset_balance(symbol)

        # get asset balance free for sell (sell all)
        asset_balance_free = float(asset_balance['free'])

        info = client.get_symbol_info(exchange)

        # stepSize decimal 1, 0.1, 0.01
        step_size = [float(_['stepSize']) for _ in info['filters']
                     if _['filterType'] == 'LOT_SIZE'][0]
        step_size = '%.8f' % step_size
        step_size = step_size.rstrip('0')
        decimals = len(step_size.split('.')[1])

        # quantity for buy
        quantity = math.floor(quantity * 10 ** decimals) / 10 ** decimals

        telegram_bot_sendtext(
            f"last quantity : {quantity}", telegram_bot_token, telegram_bot_id)

        # quantity forsell
        asset_balance_free = math.floor(
            asset_balance_free * 10 ** decimals) / 10 ** decimals

        # Order side BUY
        if side == 'BUY':

            # request create order buy to binance
            order_response = orderV1(side, quantity, exchange,
                                     telegram_bot_token, telegram_bot_id, binance_api_key, binance_api_secret)
            if order_response:
                buy_quantity = 0
                buy_price = 0
                # response buy usdt
                buy_usdt = str(
                    round(float(order_response['cummulativeQuoteQty']), 5))
                for f in order_response['fills']:
                    # response buy quantity
                    buy_quantity += float(f['qty'])
                    # response buy price
                    buy_price += float(f['price'])

                telegram_bot_sendtext(
                    f"================= \nOrder executed! \nBUY: {exchange} \nQuantity: {quantity} {symbol} \nPrice: {buy_price} USDT \nSpent: {buy_usdt} USDT \n=================", telegram_bot_token, telegram_bot_id)
            # order = client.order_market_buy(symbol=exchange, quantity=quantity)
        elif side == 'SELL':

            # coin in spot wallet must not empty
            if asset_balance_free > 0:

                # request create order sell to binance
                order_response = orderV1(side, asset_balance_free, exchange,
                                         telegram_bot_token, telegram_bot_id, binance_api_key, binance_api_secret)

                if order_response:
                    sell_quantity = 0
                    sell_price = 0
                    # response receive usdt
                    receive_usdt = str(
                        round(float(order_response['cummulativeQuoteQty']), 5))
                    for f in order_response['fills']:
                        # response sell quantity
                        sell_quantity += float(f['qty'])
                        # response sell price
                        sell_price += float(f['price'])

                    # response sell quantity
                    sell_quantity = str(sell_quantity)

                    # binance have many sell price -> average sell price
                    sell_price = str(sell_price/len(order_response['fills']))

                    # recent receive usdt
                    recentQty = round(float(recent_trade[0]['quoteQty']), 5)

                    # profit = now receive(sell) - recent spent(buy)
                    profit = float(receive_usdt) - float(recentQty)

                    # percent of porfit
                    percent_profit = profit / recentQty * 100

                    # set decimals 5 point
                    profit = round(profit, 5)
                    print(f"now receive: {receive_usdt}")
                    print(f"recent: {recentQty}")
                    print(f"profit: {profit}")

                    if percent_profit >= 0:
                        percent_profit = "+" + str(round(percent_profit, 2))
                    else:
                        percent_profit = str(round(percent_profit, 2))

                    telegram_bot_sendtext(
                        f"================= \nOrder executed! \nSELL: {exchange} \nQuantity: {quantity} {symbol} \nPrice: {sell_price} USDT \nReceive: {receive_usdt} USDT \n================= \nProfit: {profit} USDT \nPercent: {percent_profit} % \n=================", telegram_bot_token, telegram_bot_id)

                    print(order_response)

            else:
                telegram_bot_sendtext(
                    "ERROR : You not have " + str(symbol) + " coin! ", telegram_bot_token, telegram_bot_id)
                return {
                    "code": "warning",
                    "message": "You not have coin!"
                }
        else:
            telegram_bot_sendtext(
                "SIDE ERROR", telegram_bot_token, telegram_bot_id)
            return {
                "error": "error",
                "message": "SIDE ERROR"
            }

        if order_response:
            # telegram_bot_sendtext("SUCCESS : order executed")
            return {
                "code": "success",
                "message": "order executed"
            }
        else:
            print("order failed")

            telegram_bot_sendtext("ERROR : order failed " + str(symbol) + "",
                                  telegram_bot_token, telegram_bot_id)
            return {
                "error": "error",
                "message": "order failed"
            }

        return {
            "code": "success",
            "message": data
        }
    except Exception as e:
        text = "an exception occured - {}".format(e)
        telegram_bot_sendtext_admin(
            f"{text} \n User : {username}")


@app.route('/webhook', methods=['POST'])
def webhook():

    data = json.loads(request.data)

    # return data
    # confirm passphrase
    client = Client(config.API_KEY, config.API_SECRET)

    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        telegram_bot_sendtext("Dangerous! : Someone is trying to use the api.")
        return {
            "error": "error",
            "message": "Nice try!, invalid"
        }
    # chage side buy or sell to upper case
    side = data['strategy']['order_action'].upper()

    # exchange symbol BNBUSDT
    exchange = data['exchange']

    # coin symbol
    symbol = data['symbol']

    # amount buy/usdt
    usdt = data['usdt']

    # minimum buy in binance
    if usdt <= 10:
        telegram_bot_sendtext(
            f" ERROR : {side} -> {exchange} -> USDT must be over than 10 usdt")
        return {
            "code": "warning",
            "message": "USDT must be over than 10 usdt"
        }

    # recent trade
    recent_trade = client.get_my_trades(symbol=exchange, limit=1)

    # quantity for buy
    quantity = round(usdt / data['strategy']['order_price'], 2)

    # get asset balance with param
    asset_balance = client.get_asset_balance(symbol)

    # get asset balance free for sell (sell all)
    asset_balance_free = float(asset_balance['free'])

    info = client.get_symbol_info(exchange)

    # stepSize decimal 1, 0.1, 0.01
    step_size = [float(_['stepSize']) for _ in info['filters']
                 if _['filterType'] == 'LOT_SIZE'][0]
    step_size = '%.8f' % step_size
    step_size = step_size.rstrip('0')
    decimals = len(step_size.split('.')[1])

    # quantity for buy
    quantity = math.floor(quantity * 10 ** decimals) / 10 ** decimals

    # quantity forsell
    asset_balance_free = math.floor(
        asset_balance_free * 10 ** decimals) / 10 ** decimals

    # Order side BUY
    if side == 'BUY':

        # request create order buy to binance
        order_response = order(side, quantity, exchange)
        if order_response:
            buy_quantity = 0
            buy_price = 0
            # response buy usdt
            buy_usdt = str(
                round(float(order_response['cummulativeQuoteQty']), 5))
            for f in order_response['fills']:
                # response buy quantity
                buy_quantity += float(f['qty'])
                # response buy price
                buy_price += float(f['price'])

            telegram_bot_sendtext(
                f"================= \nOrder executed! \nBUY: {exchange} \nQuantity: {quantity} {symbol} \nPrice: {buy_price} USDT \nSpent: {buy_usdt} USDT \n=================")
        # order = client.order_market_buy(symbol=exchange, quantity=quantity)
    elif side == 'SELL':

        # coin in spot wallet must not empty
        if asset_balance_free > 0:

            # request create order sell to binance
            order_response = order(side, asset_balance_free, exchange)

            if order_response:
                sell_quantity = 0
                sell_price = 0
                # response receive usdt
                receive_usdt = str(
                    round(float(order_response['cummulativeQuoteQty']), 5))
                for f in order_response['fills']:
                    # response sell quantity
                    sell_quantity += float(f['qty'])
                    # response sell price
                    sell_price += float(f['price'])

                # response sell quantity
                sell_quantity = str(sell_quantity)

                # binance have many sell price -> average sell price
                sell_price = str(sell_price/len(order_response['fills']))

                # recent receive usdt
                recentQty = round(float(recent_trade[0]['quoteQty']), 5)

                # profit = now receive(sell) - recent spent(buy)
                profit = float(receive_usdt) - float(recentQty)

                # percent of porfit
                percent_profit = profit / recentQty * 100

                # set decimals 5 point
                profit = round(profit, 5)
                print(f"now receive: {receive_usdt}")
                print(f"recent: {recentQty}")
                print(f"profit: {profit}")

                if percent_profit >= 0:
                    percent_profit = "+" + str(round(percent_profit, 2))
                else:
                    percent_profit = str(round(percent_profit, 2))

                telegram_bot_sendtext(
                    f"================= \nOrder executed! \nSELL: {exchange} \nQuantity: {quantity} {symbol} \nPrice: {sell_price} USDT \nReceive: {receive_usdt} USDT \n================= \nProfit: {profit} USDT \nPercent: {percent_profit} % \n=================")

                print(order_response)

        else:
            telegram_bot_sendtext("ERROR : You not have coin! ")
            return {
                "code": "warning",
                "message": "You not have coin!"
            }
    else:
        telegram_bot_sendtext("SIDE ERROR")
        return {
            "error": "error",
            "message": "SIDE ERROR"
        }

    if order_response:
        # telegram_bot_sendtext("SUCCESS : order executed")
        return {
            "code": "success",
            "message": "order executed"
        }
    else:
        print("order failed")

        telegram_bot_sendtext("ERROR : order failed")
        return {
            "error": "error",
            "message": "order failed"
        }

    return {
        "code": "success",
        "message": data
    }


@app.route('/home')
def hello_world():
    return render_template('home.html')


@app.route('/auth', methods=['POST'])
def auth():

    username = request.form['username']
    password = request.form['password']
    print(username)
    print(password)

    db = firestore.client()

    user_collection = db.collection(u'users')
    docs = user_collection.where(u'username', u'==', username).get()

    if len(docs) == 0:
        data = {
            "status": "Error",
            "message": "Usename or password does not exist!"
        }
        return render_template('response.html', data=data)

    doc = []
    doc_id = ''
    for o in docs:
        doc = o.to_dict()
        doc_id = o.id

    account = False
    if (hashlib.md5(password.encode()).hexdigest() == doc['password']):
        account = True

    if account == False:
        data = {
            "status": "Error",
            "message": "Usename or password does not exist!"
        }
        return render_template('response.html', data=data)

    data = {
        "id": doc_id,
        "username": doc['username'],
        "email": doc['email'],
        "binance_api_key": doc['binance_api_key'],
        "binance_api_secret": doc['binance_api_secret'],
        "telegram_bot_id": doc['telegram_bot_id'],
        "telegram_bot_token": doc['telegram_bot_token'],
        "webhook_passphrase": doc['webhook_passphrase'],
        "is_active": doc['is_active'],
        "is_admin": doc['is_admin'],
    }

    session["auth"] = data
    print(session)
    return redirect("/home")

    if doc['is_admin'] == True:
        return render_template('home_admmin.html')
    else:
        return render_template('home.html')
    # print(doc['username'])
    print(data)

    return data


@app.route('/')
def login():

    # Use the application default credential
    return render_template('login.html')


@app.route('/logout')
def logout():

    session["auth"] = None
    # Use the application default credential
    return render_template('login.html')


@app.route('/home')
def home():
    # Use the application default credential
    return render_template('home.html')


@app.route('/register')
def register():

    return render_template('register.html')


@app.route('/signup', methods=['POST'])
def signup():

    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    rePassword = request.form['re-password']

    if password != rePassword:

        data = {
            "status": "Error",
            "message": "Password and Re-Password Not Match!"
        }

        return render_template('response.html', data=data)

    print(username)
    print(password)

    db = firestore.client()

    user_collection = db.collection(u'users')
    docs = user_collection.where(u'username', u'==', username).get()

    if docs:
        data = {
            "status": "Error",
            "message": "Username is exist!"
        }
        return render_template('response.html', data=data)

    en_pass = hashlib.md5(password.encode()).hexdigest()
    user = db.collection(u'users').document()
    user.set({
        u'username': username,
        u'password': en_pass,
        u'email': email,
        u'binance_api_key': u'',
        u'binance_api_secret': u'',
        u'telegram_bot_id': u'',
        u'telegram_bot_token': u'',
        u'webhook_passphrase': u'',
        u'is_active': True,
        u'is_admin': False,
    })

    data = {
        "status": "Success",
        "message": "Sign Up Success!"
    }

    return render_template('response.html', data=data)


@app.route('/update', methods=['POST'])
def update():

    doc_id = request.form['id']

    email = request.form['email']
    webhook_passphrase = request.form['passphrase']

    binance_api_key = request.form['binance_api_key']
    binance_api_secret = request.form['binance_api_secret']
    telegram_bot_id = request.form['bot_id']
    telegram_bot_token = request.form['bot_token']

    password = request.form['password']
    rePassword = request.form['re_password']
    # print(request.form)
    # return request.form
    if password != rePassword:

        data = {
            "status": "Error",
            "message": "Password and Re-Password Not Match!"
        }

        return render_template('response.html', data=data)

    # print(doc_id)
    # return doc_id

    db = firestore.client()

    docs = db.collection(u'users').document(doc_id)
    print(password)
    # user = db.collection(u'users').document(doc_id)
    en_pass = hashlib.md5(password.encode()).hexdigest()
    if password != None and password != '':
        print('if')
        docs.update({
            u'password': en_pass,
            u'email': email,
            u'binance_api_key': binance_api_key,
            u'binance_api_secret': binance_api_secret,
            u'telegram_bot_id': telegram_bot_id,
            u'telegram_bot_token': telegram_bot_token,
            u'webhook_passphrase': webhook_passphrase,
        })
    else:
        print('else')
        docs.update({
            u'email': email,
            u'binance_api_key': binance_api_key,
            u'binance_api_secret': binance_api_secret,
            u'telegram_bot_id': telegram_bot_id,
            u'telegram_bot_token': telegram_bot_token,
            u'webhook_passphrase': webhook_passphrase,
        })

    docs = db.collection(u'users').document(doc_id).get()
    docs = docs.to_dict()

    data = {
        "id": doc_id,
        "username": docs['username'],
        "email": docs['email'],
        "binance_api_key": docs['binance_api_key'],
        "binance_api_secret": docs['binance_api_secret'],
        "telegram_bot_id": docs['telegram_bot_id'],
        "telegram_bot_token": docs['telegram_bot_token'],
        "webhook_passphrase": docs['webhook_passphrase'],
        "is_active": docs['is_active'],
        "is_admin": docs['is_admin'],
    }

    session["auth"] = data
    print(session)
    flash('Update Success!')
    return redirect("/home")

    return render_template('response.html', data=data)


@app.route('/test/binance', methods=['POST'])
def testBinance():
    binance_api_key = request.form['binance_api_key']
    binance_api_secret = request.form['binance_api_secret']
    print(binance_api_key)
    print(binance_api_secret)
    if binance_api_key == '' or binance_api_key == '':
        data = {
            "status": "error",
            "title": "Test Failed",
            "msg": "Binance testing failed!"
        }
        return data

    data = {
        "status": "success",
        "title": "Test Success",
        "msg": "Binance testing passed!"
    }
    client = Client(binance_api_key, binance_api_secret)
    try:
        print('try')
        test = client.get_account_status()

    except Exception as e:
        data = {
            "status": "error",
            "title": "Test Failed",
            "msg": "Binance testing failed!"
        }

    return data


@app.route('/test/telegram', methods=['POST'])
def testTelegram():

    text = "Bot testing success!"

    telegram_bot_id = request.form['telegram_bot_id']
    telegram_bot_token = request.form['telegram_bot_token']

    if telegram_bot_id == '' or telegram_bot_token == '':
        data = {
            "status": "error",
            "title": "Test Failed",
            "msg": "Telegram testing failed!"
        }
        return data

    tested = telegram_bot_sendtext(text, telegram_bot_token, telegram_bot_id)

    if tested:
        data = {
            "status": "success",
            "title": "Test Success",
            "msg": "Telegram testing passed!"
        }
    else:
        data = {
            "status": "failed",
            "title": "Test Failed",
            "msg": "Telegram testing failed!"
        }

    print(telegram_bot_sendtext)

    return data
