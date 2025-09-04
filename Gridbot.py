# -*- coding: utf-8 -*-
"""
@author: luisf
"""
import websocket,json
import requests
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
#coneccion a base de datos
cnx = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    database="precios_sol_usdt",
    password=os.getenv("PASSWORD_DB"))

cursor = cnx.cursor()
socket='wss://ws.bitso.com' #conexion al socket de bitso
DISCORD_WEBHOOK_URL = os.getenv("WEBHOOK_URL")#conexion webook de discord
precioInicial=None
dinero=1000 #simulacion de dinero inicial
retorno_objetivo=0.11 #Aqui se define el porcentaje de cambio para enviar alerta
#funcion para guardar precios en la base de datos
def guardar_precio(precio):
    sql = "INSERT INTO historial_precio (precio_sol) VALUES (%s)"
    print("estamos en la funcion---Guardar precio--")
    valores = (precio,) #almacenar el valor de precio
    cursor.execute(sql, valores)
    cnx.commit()

#funcion para guardar las posiciones de compra en la base de datos
def posiciones(precio_compra,cantidad,objetivo):
    sql="INSERT INTO posiciones (precio_compra,cantidad,objetivo) VALUES (%s,%s,%s)"
    print("Estamos en la funcion posiciones gg--")
    valores=(precio_compra,cantidad,objetivo) #almacenar el precio de compra, cantidad de sol y el objetivo
    cursor.execute(sql, valores)
    cnx.commit()
#Esta funcion simula lacompra de solana la cual compra 20 usdt cada que se llama
def compra(precio_compra):
    global retorno_objetivo
    global dinero
    if dinero <= 20: #erifica si hay dinero suficiente para comprar
        print(f"No hay dinero suficiente se tiene:${dinero} usdt") #verificar fondos
        mensaje=f"No hay fondos suficientes para comprar: se tiene ${dinero} usdt"
        enviar_alerta_discord(mensaje, precio_compra, 0)# Alerta en discord de fondos 
    else:
        cantidad_gastar=20
        objetivo=((retorno_objetivo/100)*precio_compra)+precio_compra
        cantidad_sol=cantidad_gastar/precio_compra
        print(f"Se realizo la compra de: ${cantidad_sol} por ${cantidad_gastar} usdt")
        posiciones(precio_compra,cantidad_sol,objetivo) #Almacenar posicion de compra
        dinero= dinero-cantidad_gastar
        print(f"---dinero gastado queda --> ${dinero} usdt")#Dinero restante
#Esta funcion realiza la venta de una posicion abierta 
def vender(precio_actual):
    global dinero #De los registros en la tabla de posiciones se verifica cual esta abierta 
    cursor.execute("SELECT * FROM posiciones WHERE vendida = FALSE ORDER BY id ASC")
    print("estamos dentro de funcion ----vender---")
    #mostrar posiciones abirertas
    posiciones=cursor.fetchall()
    for pos in posiciones: 
        print(f"posiciones abiertas: {pos[0]} precio_compra: ${pos[1]} cantidad: {pos[2]} objetivo: ${pos[3]}")
        if precio_actual >= pos[3]:#verifica si el precio actual es mayor o igual al objetivo 
            print(f"Se vendio la posicion id {pos[0]} de valor ${pos[2]} al precio {precio_actual}")
            print(f"ganancia obtenida: ${pos[2]*precio_actual}")
            dinero += pos[2] * precio_actual
            mensaje=f"💵 se vendio la posicion ${pos[0]} de valor ${pos[2]} al precio ${precio_actual} DLLS obtenidos ${pos[2]*precio_actual}"
            cursor.execute("UPDATE posiciones SET vendida=TRUE WHERE id=%s",(pos[0],))#se actualiza la posicion como vendida
            enviar_alerta_discord(mensaje,precio_actual,0)
            cnx.commit()

#esta funcion envia las alertas a dicord usando el webhook
def enviar_alerta_discord(mensaje, precio_actual, cambio_porcentaje):
    "enviar una alerta a discord  usando webhook"
    try:
        color = 0x00ff00 if cambio_porcentaje > 0 else 0xff0000 #segun el cambio de precio
        #lo que insertara
        embed = {
            "title": "🚨 Alerta de Precio - SOL/USDT",
            "description": mensaje,
            "color": color,
            "fields": [#tipos de mensajea enviar 
                {
                    "name": "💰 Precio Actual",
                    "value": f"${precio_actual:.6f}",
                    "inline": True
                },
                {
                    "name": "📈 Cambio",
                    "value": f"{cambio_porcentaje:+.2f}%",
                    "inline": True
                },
                {
                    "name": "⏰ Hora",
                    "value": datetime.now().strftime("%H:%M:%S"),
                    "inline": True
                }
            ],
            "thumbnail": {
                "url": "https://cryptologos.cc/logos/solana-sol-logo.png"
            },
            "footer": {
                "text": "Monitor de precios Bitso",
                "icon_url": "https://bitso.com/favicon.ico"
            }
        }
        payload = {
            "username": "Price Monitor Bot",
            "embeds": [embed]
        }
        
        # Enviar alerta a Discord
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        
        if response.status_code == 204:
            print("✅ Alerta enviada a Discord")
        else:
            print(f"❌ Error enviando a Discord: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error enviando alerta a Discord: {e}")

#Funcion que recibe el precioactual y verifica si hay cambios significativos 
#conforme al porcentaj definido en retornoobjetivo
def cambio_precio(valor_actual):
    global precioInicial
    global retorno_objetivo
    global dinero
    if precioInicial is None:#cuando se ejecuta el bot por primera vez se establecera la compra 
        precioInicial =valor_actual
        compra(precioInicial)# se ejecuta la funcion de compra 
        guardar_precio(precioInicial)
        objetivo=((retorno_objetivo/100)*precioInicial)+precioInicial
        print(f"Precio inicial establecido y compra : ${precioInicial} objetivo: {retorno_objetivo}%--> ${objetivo}")
        mensaje = f"🟢 Monitor de precios iniciado---primera compra hecha a :$ {precioInicial} objetivo: {retorno_objetivo}%--> ${objetivo}--->dinero disponible=${dinero}"
        enviar_alerta_discord(mensaje, valor_actual, 0)
        return
    cambio =((valor_actual - precioInicial) / precioInicial) * 100 #obtenmos el porcentaje de cambio 
    if cambio >= retorno_objetivo: #comparacion de si es mayor 
        mensaje = f"📈 ¡SUBIDA SIGNIFICATIVA! El precio subió más del {retorno_objetivo}%"
        print(f"El precio ha cambiado más del {retorno_objetivo}%: {cambio:.2f}%")
        enviar_alerta_discord(mensaje, valor_actual, cambio)
        vender(valor_actual)
        precioInicial = valor_actual
        print(f"precio inicial modificado a: ${precioInicial} ")
    elif cambio <= -retorno_objetivo: #comparacion de si es menor para ejecutar la compra
        mensaje = f"📉 ¡CAÍDA SIGNIFICATIVA! El precio bajó más del -{retorno_objetivo}%"
        print(f"El precio ha caido y cambiado más del -{retorno_objetivo}%: {cambio:.2f}%")
        enviar_alerta_discord(mensaje, valor_actual, cambio)
        compra(valor_actual)
        print("se ejcuto la compra")
        precioInicial = valor_actual
        print(f"precio inicial modificado a: ${precioInicial} ")
    else: #si no se cumple las demas condiciones solo muestra los cambios y informacion de el dinero
        print(f"Precio actual: {valor_actual} || cambio: {cambio:.2f}%")
        print(f"Dinero disponible: ${dinero}")
        guardar_precio(valor_actual)
        #vender(valor_actual)#quitar vender de aqui
        
def on_message(ws, message):#obtener los datos y filtrar el precio --> se obtinen las transacciones hechas
   data_message=json.loads(message)
   #print(data_message)
   print(data_message["payload"])
   #print("precio------:", data_message["payload"][0]['r'])
   cambio_precio(float(data_message["payload"][0]['r']))#Del arreglo seleccionamos el dato de el precio

def on_close(ws):#cuando cerramos la coneccion 
    print("###  Connection closed ###")
    try:
        payload = {
            "username": "Price Monitor Bot",
            "content": "🔴 Monitor de precios desconectado"
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except:
        pass

def on_error(ws, error): #si hay error
    print(f"Error de WebSocket: {error}")

def on_open(ws):
    # Subscripcion al ticket de sol_usdt
    subscribe_message = {
       'action': 'subscribe',
       'book': 'sol_usdt',
       'type': 'trades'#eleccion de trades hechos
    }
    ws.send(json.dumps(subscribe_message))
    print("Suscrito a SOL/USDT trades")

#ejecucion del bot
if __name__=="__main__":
    print("🚀 Iniciando monitor de precios SOL/USDT...")
    print(f"📱 Las alertas se enviarán a Discord cuando el precio cambie ±{retorno_objetivo}%")
    ws = websocket.WebSocketApp(socket,on_message=on_message,on_error=on_error,on_close=on_close)
    ws.on_open = on_open
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Monitor detenido por el usuario")
    except Exception as e:
        print(f"❌ Error: {e}")    
    
