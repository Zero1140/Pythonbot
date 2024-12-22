import json
import pandas_ta as ta
import numpy as np
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
import time
import logging
import traceback
import os
from functools import lru_cache
import sys

# Configuración de logging
log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(log_directory, f"trading_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Agregar un nuevo logger para registros detallados
detailed_logger = logging.getLogger('detailed_logger')
detailed_log_file = os.path.join(log_directory, f"detailed_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
detailed_handler = logging.FileHandler(detailed_log_file)
detailed_handler.setLevel(logging.DEBUG)
detailed_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
detailed_handler.setFormatter(detailed_formatter)
detailed_logger.addHandler(detailed_handler)

def cargar_configuracion():
    try:
        with open("configmt5.json", "r") as f:
            config = json.load(f)
        logging.info("Configuración cargada exitosamente.")
        detailed_logger.debug(f"Configuración cargada: {config}")
        return config
    except FileNotFoundError as e:
        logging.critical(f"Archivo de configuración no encontrado: {str(e)}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.critical(f"Error al decodificar el archivo JSON de configuración: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Error inesperado al cargar la configuración: {str(e)}")
        sys.exit(1)

# Cargar configuración
try:
    config = cargar_configuracion()
    symbol_config = config['symbol_config']
    timeframe = eval(config['timeframe'])
    creds = config['creds']
    max_daily_loss = config.get('max_daily_loss', 10)  # Pérdida diaria máxima permitida en porcentaje
    logging.info("Configuraciones específicas extraídas correctamente.")
    detailed_logger.debug(f"Configuraciones específicas: symbol_config={symbol_config}, timeframe={timeframe}, max_daily_loss={max_daily_loss}")
except Exception as e:
    logging.critical(f"Error al extraer configuraciones específicas: {str(e)}")
    sys.exit(1)

# Función para inicializar MetaTrader 5
def initialize_mt5(max_attempts=3, retry_delay=5):
    for attempt in range(max_attempts):
        try:
            if not mt5.initialize(**creds):
                raise ConnectionError(f"Error al inicializar MetaTrader 5: {mt5.last_error()}")
            
            if not mt5.terminal_info() or not mt5.account_info():
                raise ConnectionError("No se pudo obtener información del terminal o de la cuenta.")
            
            logging.info("Plataforma inicializada y lista para operar.")
            detailed_logger.debug(f"Intento {attempt + 1}: Inicialización exitosa")
            return True
        except Exception as e:
            logging.error(f"Intento {attempt + 1} fallido: {str(e)}")
            detailed_logger.error(f"Intento {attempt + 1} fallido: {str(e)}\nTraceback: {traceback.format_exc()}")
            if attempt < max_attempts - 1:
                logging.info(f"Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                logging.critical("No se pudo inicializar MetaTrader 5 después de varios intentos.")
                print("Verifique la configuración y el estado de MetaTrader 5.")
                return False

# Inicializar MetaTrader 5 al inicio del script
if not initialize_mt5():
    logging.critical("No se pudo inicializar MetaTrader 5. Saliendo del script.")
    sys.exit(1)

def get_now():
    return datetime.now(pytz.timezone("Etc/GMT-4"))

def verificar_conexion_mt5():
    if not mt5.terminal_info():
        logging.warning("Conexión con MetaTrader 5 perdida. Intentando reconectar...")
        detailed_logger.warning("Conexión con MetaTrader 5 perdida. Intentando reconectar...")
        return initialize_mt5()
    return True

def obtener_datos_ohlc(symbol, max_intentos=3):
    for intento in range(max_intentos):
        try:
            if not verificar_conexion_mt5():
                raise ConnectionError("No se pudo reconectar a MetaTrader 5")
            
            ahora = get_now() + timedelta(hours=3)
            desde = ahora - timedelta(minutes=150*5)
            raw_ohlc_data = mt5.copy_rates_range(symbol, timeframe, desde, ahora)
            if raw_ohlc_data is None or len(raw_ohlc_data) == 0:
                raise ValueError(f"Datos OHLC vacíos o nulos para {symbol}")
            df = pd.DataFrame(raw_ohlc_data)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            # Registrar la última fila en un archivo de texto
            with open(f"registro_dataframe_{symbol}.txt", "a") as f:
                f.write(f"Última actualización del DataFrame para {symbol}: {ahora}\n")
                f.write(str(df.iloc[-1]) + "\n\n")
            
            logging.info(f"Datos OHLC obtenidos exitosamente para {symbol}. Filas: {len(df)}")
            
            return df
        except Exception as e:
            logging.error(f"Error al obtener datos OHLC para {symbol} (intento {intento + 1}): {str(e)}")
            detailed_logger.error(f"Error al obtener datos OHLC para {symbol} (intento {intento + 1}): {str(e)}\nTraceback: {traceback.format_exc()}")
        
        if intento < max_intentos - 1:
            logging.info(f"Reintentando obtener datos OHLC para {symbol}...")
            time.sleep(5)
        else:
            logging.critical(f"No se pudieron obtener los datos OHLC para {symbol} después de {max_intentos} intentos.")
    return None

def analyze_rsi_bollinger(df, config):
    if df is None or df.empty:
        logging.error("DataFrame vacío o nulo en analyze_rsi_bollinger")
        return None
    try:
        df = df[df.high != df.low].copy()
        
        df['RSI'] = ta.rsi(df.close, length=config['rsi_length'])
        df = df.join(ta.bbands(df.close, length=15, std=1.5))
        df['ATR'] = ta.atr(df.high, df.low, df.close, length=7)
        
        logging.debug(f"Análisis RSI y Bollinger completado. Filas resultantes: {len(df)}")
        
        return df.dropna()
    except Exception as e:
        logging.error(f"Error en analyze_rsi_bollinger: {str(e)}")
        detailed_logger.error(f"Error en analyze_rsi_bollinger: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def analyze_vwap_bollinger(df, config):
    if df is None or df.empty:
        logging.error("DataFrame vacío o nulo en analyze_vwap_bollinger")
        return None
    try:
        df = df[df.high != df.low].copy()
        
        df["VWAP"] = ta.vwap(df.high, df.low, df.close, df.tick_volume)
        df['RSI'] = ta.rsi(df.close, length=config['rsi_length'])
        df = df.join(ta.bbands(df.close, length=config['bb_length'], std=config['bb_std']))
        df['ATR'] = ta.atr(df.high, df.low, df.close, length=7)
        
        logging.debug(f"Análisis VWAP y Bollinger completado. Filas resultantes: {len(df)}")
        
        return df.dropna()
    except Exception as e:
        logging.error(f"Error en analyze_vwap_bollinger: {str(e)}")
        detailed_logger.error(f"Error en analyze_vwap_bollinger: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def bollinger_signal(df):
    if df is None or df.empty:
        logging.error("DataFrame vacío o nulo en bollinger_signal")
        return None
    try:
        condition_buy = df['close'] <= df['BBL_15_1.5']
        condition_sell = df['close'] >= df['BBU_15_1.5']

        df['bollinger_Signal'] = 0  # Default no signal
        df.loc[condition_buy, 'bollinger_Signal'] = 2
        df.loc[condition_sell, 'bollinger_Signal'] = 1
        
        logging.debug(f"Señales Bollinger calculadas. Compras: {sum(condition_buy)}, Ventas: {sum(condition_sell)}")
       
        return df
    except Exception as e:
        logging.error(f"Error en bollinger_signal: {str(e)}")
        detailed_logger.error(f"Error en bollinger_signal: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def vwap_signal(df, config):
    if df is None or df.empty:
        logging.error("DataFrame vacío o nulo en vwap_signal")
        return None
    try:
        VWAPsignal = [0] * len(df)
        backcandles = config['backcandles']

        for row in range(backcandles, len(df)):
            upt = 1
            dnt = 1
            for i in range(row-backcandles, row+1):
                if max(df.open.iloc[i], df.close.iloc[i]) >= df.VWAP.iloc[i]:
                    dnt = 0
                if min(df.open.iloc[i], df.close.iloc[i]) <= df.VWAP.iloc[i]:
                    upt = 0
            if upt == 1 and dnt == 1:
                VWAPsignal[row] = 3
            elif upt == 1:
                VWAPsignal[row] = 2
            elif dnt == 1:
                VWAPsignal[row] = 1

        df['VWAPSignal'] = VWAPsignal
        logging.debug(f"Señales VWAP calculadas. Distribución: {pd.Series(VWAPsignal).value_counts()}")
        
        return df
    except Exception as e:
        logging.error(f"Error en vwap_signal: {str(e)}")
        detailed_logger.error(f"Error en vwap_signal: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def calculate_rsi_signal_windowed(rsi_series, config):
    try:
        rsi_signal = np.zeros(len(rsi_series))
        for i in range(len(rsi_series)):
            window_start = max(0, i - 5)
            window = rsi_series[window_start:i+1]
            if not window.empty and window.gt(50.1).all():
                rsi_signal[i] = 2
            elif not window.empty and window.lt(49.9).all():
                rsi_signal[i] = 1
        
        logging.debug(f"Señales RSI calculadas. Distribución: {pd.Series(rsi_signal).value_counts()}")
        
        return rsi_signal
    except Exception as e:
        logging.error(f"Error en calculate_rsi_signal_windowed: {str(e)}")
        detailed_logger.error(f"Error en calculate_rsi_signal_windowed: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def process(df, symbol):
    if df is None or df.empty:
        logging.error(f"DataFrame vacío o nulo en process para {symbol}")
        return None
    try:
        config = symbol_config[symbol]
        if config['strategy'] == 'rsi_bollinger':
            df = analyze_rsi_bollinger(df, config)
            if df is None:
                return None
            df = bollinger_signal(df)
            if df is None:
                return None
            df['RSI_signal'] = calculate_rsi_signal_windowed(df['RSI'], config)
            if 'RSI_signal' not in df or df['RSI_signal'].isnull().all():
                return None
            df['TotalSignal'] = df.apply(lambda row: row['bollinger_Signal'] if row['bollinger_Signal'] == row['RSI_signal'] else 0, axis=1)
        elif config['strategy'] == 'vwap_bollinger':
            df = analyze_vwap_bollinger(df, config)
            if df is None:
                return None
            df = vwap_signal(df, config)
            if df is None:
                return None
            df['TotalSignal'] = df.apply(lambda row: 2 if row['VWAPSignal'] == 2 and row['close'] <= row['BBL_14_2.0'] and row['RSI'] < 45 else
                                                     1 if row['VWAPSignal'] == 1 and row['close'] >= row['BBU_14_2.0'] and row['RSI'] > 55 else 0, axis=1)
        else:
            logging.error(f"Estrategia no reconocida para {symbol}")
            return None
        
        logging.info(f"Procesamiento completado para {symbol}. Señales totales: {df['TotalSignal'].value_counts()}")
        
        return df
    except Exception as e:
        logging.error(f"Error en process para {symbol}: {str(e)}")
        detailed_logger.error(f"Error en process para {symbol}: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None

def calcular_parametros_trading(symbol, df):
    if df is None or df.empty:
        logging.error(f"DataFrame vacío o nulo en calcular_parametros_trading para {symbol}")
        return None, None, None
    try:
        config = symbol_config[symbol]
        signal = df["TotalSignal"].iloc[-1]
        close = df.close.iloc[-1]
        
        slatr = 1.0 * df["ATR"].iloc[-1] * config['slatrcoef']
        
        # Obtener el valor actual de la cuenta
        account_info = mt5.account_info()
        if account_info is None:
            raise ValueError("No se pudo obtener la información de la cuenta")
        equity = account_info.equity
        
        pip_value = (1e-4 / close) * 1e5
        
        if np.isnan(slatr) or np.isnan(pip_value):
            logging.error(f"Valores no válidos encontrados en el cálculo del tamaño para {symbol}. SLATR: {slatr}, Pip Value: {pip_value}")
            return None, None, None
        
        # Obtener datos de profundidad de mercado
        market_book = mt5.market_book_get(symbol)
        if market_book is None:
            size = round((config['risk_perc'] * equity / (slatr * pip_value)) / 100000.0, 2)
        else:
            # Calcular el tamaño de la orden basado en la liquidez disponible
            available_volume = sum([item.volume for item in market_book])
            size = min(round((config['risk_perc'] * equity / (slatr * pip_value)) / 100000.0, 2), available_volume)
        
        ahora = get_now() 
        
        logging.info(f"Parámetros de trading calculados para {symbol}: Tamaño del lote: {size}, SLATR: {slatr}, TPSLRatio: {config['TPSLRatio_coef']}, Señal: {signal}, Pip Value: {pip_value}")
        detailed_logger.debug(f"Parámetros de trading para {symbol}:\n"
                              f"Tamaño del lote: {size}\n"
                              f"SLATR: {slatr}\n"
                              f"TPSLRatio: {config['TPSLRatio_coef']}\n"
                              f"Señal: {signal}\n"
                              f"Pip Value: {pip_value}\n"
                              f"Equity: {equity}\n"
                              f"close: {close}")
        
        with open(f"registro_dataframe_{symbol}.txt", "a") as f:
            f.write(f"Tamaño del lote calculado: {size} : {ahora}\n")
            f.write(str(df.iloc[-1]) + "\n\n")
            f.write(f"SLATR: {slatr}\n")
            f.write(f"PIP Value: {pip_value}\n")
        
        # Guardar el valor de size en un archivo
        with open(f"size_log_{symbol}.txt", "a") as f:
            f.write(f"{ahora},{size}\n")
        
        return slatr, signal, size
    except Exception as e:
        logging.error(f"Error en calcular_parametros_trading para {symbol}: {str(e)}")
        detailed_logger.error(f"Error en calcular_parametros_trading para {symbol}: {str(e)}\nTraceback: {traceback.format_exc()}")
        return None, None, None

def open_orders(symbol, signal, size, slatr):
    logging.info(f"Iniciando apertura de órdenes para {symbol}")
    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"No se pudo obtener información del símbolo {symbol}")
        
        config = symbol_config[symbol]
        spread = symbol_info.ask - symbol_info.bid
        
        maxspread = config['max_spread']
        with open(f"size_log_{symbol}.txt", "a") as f:
            f.write(f"El spread máximo permitido: {maxspread}\n")
            f.write(f"El spread actual es: {spread}\n")
        
        # Obtener datos de profundidad de mercado
        market_book = mt5.market_book_get(symbol)
        
        # Optimizar el precio de entrada utilizando el market book
        if market_book is not None:
            if signal == 2 and spread < maxspread:  # Señal de compra
                best_ask = min([item.price for item in market_book if item.type == mt5.BOOK_TYPE_SELL])
                
                entry_price = best_ask
                SLBuy = entry_price - slatr - spread
                TPBuy = entry_price + slatr * config['TPSLRatio_coef'] + spread
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": size,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": entry_price,
                    "sl": SLBuy,
                    "tp": TPBuy,
                    "magic": 234000,
                    "comment": "python script open",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                logging.info(f"Intentando abrir orden de compra para {symbol}")
                detailed_logger.debug(f"Detalles de la orden de compra para {symbol}:\n{request}")
                ejecutar_orden(request, "compra", symbol)
                
            elif signal == 1 and spread < maxspread:  # Señal de venta
                best_bid = max([item.price for item in market_book if item.type == mt5.BOOK_TYPE_BUY])
                entry_price = best_bid
                SLSell = entry_price + slatr + spread
                TPSell = entry_price - slatr * config['TPSLRatio_coef'] - spread
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": size,
                    "type": mt5.ORDER_TYPE_SELL,
                    "price": entry_price,
                    "sl": SLSell,
                    "tp": TPSell,
                    "magic": 234000,
                    "comment": "python script open",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                logging.info(f"Intentando abrir orden de venta para {symbol}")
                detailed_logger.debug(f"Detalles de la orden de venta para {symbol}:\n{request}")
                ejecutar_orden(request, "venta", symbol)
            else:
                logging.info(f"No se abrió orden para {symbol}. Señal: {signal}, Spread: {spread}, Max Spread: {maxspread}")
        else:
            # Utilizar slippage en caso de que el símbolo no tenga market book
            if symbol == 'AUDNZD':
                slippage = np.random.uniform(-0.0002, 0.0002)  # Simulación de slippage para AUDNZD (2 pips)
            elif symbol == 'USDCAD':
                slippage = np.random.uniform(-0.0003, 0.0003)  # Simulación de slippage para USDCAD (3 pips)
            elif symbol == 'EURUSD':
                slippage = np.random.uniform(-0.0001, 0.00015)  # Simulación de slippage para EURUSD (1-1.5 pips)
            else:
                slippage = np.random.uniform(-0.0003, 0.0003) 
            if signal == 2 and spread < maxspread:  # Señal de compra
                entry_price = symbol_info.ask + slippage
                SLBuy = entry_price - slatr - spread
                TPBuy = entry_price + slatr * config['TPSLRatio_coef'] + spread
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": size,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": entry_price,
                    "sl": SLBuy,
                    "tp": TPBuy,
                    "magic": 234000,
                    "comment": "python script open",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                logging.info(f"Intentando abrir orden de compra para {symbol} con slippage")
                detailed_logger.debug(f"Detalles de la orden de compra para {symbol} con slippage:\n{request}")
                ejecutar_orden(request, "compra", symbol)
                
            elif signal == 1 and spread < maxspread:  # Señal de venta
                entry_price = symbol_info.bid - slippage
                SLSell = entry_price + slatr + spread
                TPSell = entry_price - slatr * config['TPSLRatio_coef'] - spread
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": size,
                    "type": mt5.ORDER_TYPE_SELL,
                    "price": entry_price,
                    "sl": SLSell,
                    "tp": TPSell,
                    "magic": 234000,
                    "comment": "python script open",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                logging.info(f"Intentando abrir orden de venta para {symbol} con slippage")
                detailed_logger.debug(f"Detalles de la orden de venta para {symbol} con slippage:\n{request}")
                ejecutar_orden(request, "venta", symbol)
            else:
                logging.info(f"No se abrió orden para {symbol}. Señal: {signal}, Spread: {spread}, Max Spread: {maxspread}")
    except Exception as e:
        logging.error(f"Error en open_orders para {symbol}: {str(e)}")
        detailed_logger.error(f"Error en open_orders para {symbol}: {str(e)}\nTraceback: {traceback.format_exc()}")
        ahora = get_now() 
        with open("errores_operaciones.txt", "a") as f:
            f.write(f"{ahora}: Error al abrir operación para {symbol}: {str(e)}\n")

def ejecutar_orden(request, tipo, symbol, max_intentos=3):
    for intento in range(max_intentos):
        try:
            if not verificar_conexion_mt5():
                raise ConnectionError("No se pudo reconectar a MetaTrader 5")
            
            result = mt5.order_send(request)
            if result is None:
                raise ValueError(f"Error al enviar orden de {tipo} para {symbol}: resultado nulo")
            elif result.retcode != mt5.TRADE_RETCODE_DONE:
                raise ValueError(f"Error al abrir orden de {tipo} para {symbol}: {result.comment}")
            else:
                logging.info(f"Orden de {tipo} abierta exitosamente para {symbol}")
                detailed_logger.info(f"Orden de {tipo} abierta exitosamente para {symbol}. Detalles: {result}")
                # Registrar la ejecución de la orden en un archivo de texto
                ahora = get_now() 
                with open("registro_dataframe.txt", "a") as f:
                    f.write(f"Orden ejecutada: {ahora}\n")
                    f.write(f"Tipo: {tipo}, Símbolo: {symbol}\n")
                    f.write(f"Detalles: {str(request)}\n\n")
                return
        except Exception as e:
            logging.error(f"Error al ejecutar orden de {tipo} para {symbol} (intento {intento + 1}): {str(e)}")
            detailed_logger.error(f"Error al ejecutar orden de {tipo} para {symbol} (intento {intento + 1}): {str(e)}\nTraceback: {traceback.format_exc()}")
            if intento < max_intentos - 1:
                logging.info(f"Reintentando ejecutar orden de {tipo} para {symbol}...")
                time.sleep(5)
            else:
                logging.error(f"No se pudo ejecutar la orden de {tipo} para {symbol} después de {max_intentos} intentos.")
                ahora = get_now() 
                with open("errores_operaciones.txt", "a") as f:
                    f.write(f"{ahora}: Error al ejecutar orden de {tipo} para {symbol} después de {max_intentos} intentos: {str(e)}\n")

def close_orders(df, symbol):
    logging.info(f"Iniciando cierre de órdenes para {symbol}")
    try:
        if not verificar_conexion_mt5():
            raise ConnectionError("No se pudo reconectar a MetaTrader 5")
        
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            logging.info(f"No hay posiciones abiertas para cerrar en {symbol}")
            return

        config = symbol_config[symbol]
        rsi = df["RSI"].iloc[-1]
        for position in positions:
            close_condition = (position.type == mt5.POSITION_TYPE_BUY and rsi >= config['rsi_overbought']) or \
                              (position.type == mt5.POSITION_TYPE_SELL and rsi <= config['rsi_oversold'])
            
            if close_condition:
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": position.volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": position.ticket,
                    "price": mt5.symbol_info_tick(symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                    "magic": 234000,
                    "comment": "python script close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                logging.info(f"Intentando cerrar posición para {symbol}. Tipo: {'Compra' if position.type == mt5.POSITION_TYPE_BUY else 'Venta'}, RSI: {rsi}")
                ejecutar_orden(close_request, "cierre", symbol)
            else:
                logging.info(f"No se cerró posición para {symbol}. Tipo: {'Compra' if position.type == mt5.POSITION_TYPE_BUY else 'Venta'}, RSI: {rsi}")
    except Exception as e:
        logging.error(f"Error en close_orders para {symbol}: {str(e)}")
        logging.debug(f"Traceback completo:\n{traceback.format_exc()}")
        ahora = get_now() 
        with open("errores_operaciones.txt", "a") as f:
            f.write(f"{ahora}: Error al cerrar operaciones para {symbol}: {str(e)}\n")

def verificar_perdida_diaria():
    try:
        account_info = mt5.account_info()
        if account_info is None:
            raise ValueError("No se pudo obtener la información de la cuenta")
        
        balance_inicial = account_info.balance
        equity_actual = account_info.equity
        
        perdida_porcentual = (balance_inicial - equity_actual) / balance_inicial * 100
        
        if perdida_porcentual >= max_daily_loss:
            logging.warning(f"Se ha alcanzado o superado la pérdida diaria del {max_daily_loss}%. Pérdida actual: {perdida_porcentual:.2f}%")
            return True
        return False
    except Exception as e:
        logging.error(f"Error al verificar la pérdida diaria: {str(e)}")
        return False

def cerrar_todas_las_posiciones():
    try:
        positions = mt5.positions_get()
        if positions is None:
            logging.info("No hay posiciones abiertas para cerrar")
            return
        
        for position in positions:
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
                "magic": 234000,
                "comment": "python script close all",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            logging.info(f"Intentando cerrar posición para {position.symbol}")
            ejecutar_orden(close_request, "cierre", position.symbol)
        
        logging.info("Todas las posiciones han sido cerradas")
    except Exception as e:
        logging.error(f"Error al cerrar todas las posiciones: {str(e)}")
        logging.debug(f"Traceback completo:\n{traceback.format_exc()}")

def trading_job():
    ahora = get_now() 
    logging.info(f"Iniciando ciclo de trading a las {ahora}")
    
    # Verificar si se ha alcanzado la pérdida diaria máxima
    if verificar_perdida_diaria():
        logging.warning("Se ha alcanzado la pérdida diaria máxima. Cerrando todas las posiciones y deteniendo operaciones.")
        cerrar_todas_las_posiciones()
        return
    
    for symbol in symbol_config.keys():
        logging.info(f"Procesando {symbol}")
        try:
            df = obtener_datos_ohlc(symbol)
            if df is not None:
                df = process(df, symbol)
                if df is not None:
                    slatr, signal, size = calcular_parametros_trading(symbol, df)
                    if None not in (slatr, signal, size):
                        open_orders(symbol, signal, size, slatr)
                        close_orders(df, symbol)
                    
                    logging.info(f"Últimas 5 filas del DataFrame para {symbol}:")
                    logging.info(df.tail())
                else:
                    logging.warning(f"No se pudo procesar el DataFrame para {symbol}")
            else:
                logging.warning(f"No se pudieron obtener datos OHLC para {symbol}")
        except Exception as e:
            logging.error(f"Error en trading_job para {symbol}: {str(e)}")
            logging.debug(f"Traceback completo:\n{traceback.format_exc()}")
            ahora = get_now() 
            with open("errores_operaciones.txt", "a") as f:
                f.write(f"{ahora}: Error en trading_job para {symbol}: {str(e)}\n")
    
    ahora = get_now() 
    logging.info(f"Ciclo de trading completado a las {ahora}")

def main():
    scheduler = BlockingScheduler()
    
    # Configuración de la tarea: Desde las 22:00 del domingo (día 6) hasta las 21:30 del viernes (día 4)
    scheduler.add_job(
        trading_job,
        'cron',
        day_of_week='sun',
        hour='22-23',
        minute='1,6,11,16,21,26,31,36,41,46,51,56',
        timezone='Europe/London'
    )
    scheduler.add_job(
        trading_job,
        'cron',
        day_of_week='mon-thu',
        hour='0-23',
        minute='1,6,11,16,21,26,31,36,41,46,51,56',
        timezone='Europe/London'
    )
    scheduler.add_job(
        trading_job,
        'cron',
        day_of_week='fri',
        hour='0-21',
        minute='1,6,11,16,21,26,31,36,41,46,51,56',
        timezone='Europe/London'
    )
    
    # Agregar tarea para cerrar todas las posiciones a las 21:30 del viernes
    scheduler.add_job(
        cerrar_todas_las_posiciones,
        'cron',
        day_of_week='fri',
        hour='21',
        minute='30',
        timezone='Europe/London'
    )
    
    # Agregar tarea para verificar la conexión cada 5 minutos
    scheduler.add_job(
        verificar_conexion_mt5,
        'interval',
        minutes=3
    )
    
    logging.info("Iniciando el scheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Deteniendo el scheduler...")
    except Exception as e:
        logging.error(f"Error inesperado en el scheduler: {str(e)}")
        logging.debug(f"Traceback completo:\n{traceback.format_exc()}")
        ahora = get_now() 
        with open("errores_operaciones.txt", "a") as f:
            f.write(f"{ahora}: Error inesperado en el scheduler: {str(e)}\n")
    finally:
        mt5.shutdown()
        logging.info("MetaTrader 5 desconectado.")

if __name__ == "__main__":
    main()
    # cd C:\Users\guill\desktop\trading\proyectos de programacion\robot>