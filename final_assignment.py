import asyncio
from yolo_uno import *
from lcd1602 import *
from dht20 import *
from pins import *

lcd1602 = LCD1602()
dht20 = DHT20()

led_D13 = Pins(D13_PIN)
heater_led = RGBLed(D3_PIN, 4)
cooler_led = RGBLed(D5_PIN, 4)
humidifier_led = RGBLed(D7_PIN, 4)

GREEN = hex_to_rgb("#00ff00")
ORANGE = hex_to_rgb("#ffa500")
RED = hex_to_rgb("#ff0000")
OFF = hex_to_rgb("#000000")

HEATER_SAFE_MAX = 28.0
HEATER_WARNING_MAX = 35.0

COOLER_THRESHOLD = 30.0
COOLER_DURATION_MS = 5000

HUMIDITY_THRESHOLD = 50.0
HUMIDIFIER_GREEN_TIME = 5000
HUMIDIFIER_YELLOW_TIME = 3000
HUMIDIFIER_RED_TIME = 2000

share_data = {
    "temperature": 0.0,
    "humidity": 0.0
}

data_mutex = asyncio.Semaphore(1)

lcd_event = asyncio.Event()
heater_event = asyncio.Event()
cooler_event = asyncio.Event()
humidifier_event = asyncio.Event()

async def task_LED_Blinky():
    while True:
        led_D13.toggle()
        await asleep_ms(1000)

async def task_read_sensor():
    while True:
        try:
            temp = await dht20.atemperature()
            humi = await dht20.ahumidity()

            await data_mutex.acquire()
            try:
                share_data["temperature"] = temp
                share_data["humidity"] = humi
            finally:
                data_mutex.release()

            print("[Sensor] Temp={:.1f} C, Humidity={:.1f} %".format(temp, humi))

            lcd_event.set()
            heater_event.set()
            cooler_event.set()
            humidifier_event.set()

        except Exception as e:
            print("[Sensor Error]:", e)

        await asleep_ms(5000)

async def task_LCD():
    while True:
        await lcd_event.wait()
        lcd_event.clear()

        try:
            await data_mutex.acquire()
            try:
                temp = share_data["temperature"]
                humi = share_data["humidity"]
            finally:
                data_mutex.release()

            lcd1602.show("TEMP: {:.1f} C".format(temp).ljust(16), 0, 0)
            lcd1602.show("HUMI: {:.1f} %".format(humi).ljust(16), 1, 0)

        except Exception as e:
            print("[LCD Error]:", e)

async def task_heater():
    current_state = None
    while True:
        await heater_event.wait()
        heater_event.clear()

        try:
            await data_mutex.acquire()
            try:
                temp = share_data["temperature"]
            finally:
                data_mutex.release()

            if temp < HEATER_SAFE_MAX:
                state = "SAFE"
                color = GREEN
            elif temp <= HEATER_WARNING_MAX:
                state = "WARNING"
                color = ORANGE
            else:
                state = "DANGER"
                color = RED

            if state != current_state:
                current_state = state
                heater_led.show(0, color)
                print("[Heater] {} : {:.1f} C".format(state, temp))

        except Exception as e:
            print("[Heater Error]:", e)

async def task_cooler():
    while True:
        await cooler_event.wait()
        cooler_event.clear()

        try:
            await data_mutex.acquire()
            try:
                temp = share_data["temperature"]
            finally:
                data_mutex.release()

            if temp > COOLER_THRESHOLD:
                print("[Cooler] ON - Temperature {:.1f} C".format(temp))
                cooler_led.show(0, GREEN)
                await asleep_ms(COOLER_DURATION_MS)
                cooler_led.show(0, OFF)
                print("[Cooler] OFF after {} ms".format(COOLER_DURATION_MS))
            else:
                cooler_led.show(0, OFF)

        except Exception as e:
            print("[Cooler Error]:", e)

async def task_humidifier():
    state = "IDLE"
    while True:
        try:
            if state == "IDLE":
                await humidifier_event.wait()
                humidifier_event.clear()

                await data_mutex.acquire()
                try:
                    humi = share_data["humidity"]
                finally:
                    data_mutex.release()

                if humi < HUMIDITY_THRESHOLD:
                    print("[Humidifier] Start cycle - Humidity {:.1f}%".format(humi))
                    state = "GREEN"
                else:
                    humidifier_led.show(0, OFF)

            elif state == "GREEN":
                print("[Humidifier] GREEN")
                humidifier_led.show(0, GREEN)
                await asleep_ms(HUMIDIFIER_GREEN_TIME)
                state = "YELLOW"

            elif state == "YELLOW":
                print("[Humidifier] YELLOW")
                humidifier_led.show(0, ORANGE)
                await asleep_ms(HUMIDIFIER_YELLOW_TIME)
                state = "RED"

            elif state == "RED":
                print("[Humidifier] RED")
                humidifier_led.show(0, RED)
                await asleep_ms(HUMIDIFIER_RED_TIME)
                humidifier_led.show(0, OFF)

                await data_mutex.acquire()
                try:
                    humi = share_data["humidity"]
                finally:
                    data_mutex.release()

                if humi < HUMIDITY_THRESHOLD:
                    print("[Humidifier] Humidity still low {:.1f}% -> Repeat".format(humi))
                    state = "GREEN"
                else:
                    print("[Humidifier] Humidity normal {:.1f}% -> IDLE".format(humi))
                    state = "IDLE"

        except Exception as e:
            print("[Humidifier Error]:", e)

async def setup():
    print("System Started")
    create_task(task_LED_Blinky())
    create_task(task_read_sensor())
    create_task(task_LCD())
    create_task(task_heater())
    create_task(task_cooler())
    create_task(task_humidifier())

async def main():
    await setup()
    while True:
        await asleep_ms(100)

run_loop(main())
