from yolo_uno import *
from pins import *
from lcd1602 import *
from dht20 import *
import asyncio

class Semaphore:
    def __init__(self, value=1):
        if value < 0:
            raise ValueError("value must be >= 0")
        self.value = value

    async def acquire(self):
        while self.value <= 0:
            await asleep_ms(10)
        self.value -= 1

    def release(self):
        self.value += 1

led_D13 = Pins(D13_PIN)
rgb_led_D3 = RGBLed(D3_PIN, 4)   # Heater indicator
rgb_led_D5 = RGBLed(D5_PIN, 4)   # Cooler indicator
rgb_led_D7 = RGBLed(D7_PIN, 4)   # Humidifier indicator

lcd1602 = LCD1602()
dht20 = DHT20()

data_lock = Semaphore(1)
shared_temp = 0.0
shared_humidity = 0.0

HEATER_SAFE_MAX = 28.0
HEATER_WARNING_MAX = 32.0

COOLER_THRESHOLD = 30.0
COOLER_DURATION_MS = 5000

HUMIDITY_THRESHOLD = 40.0 
HUMIDIFIER_GREEN_MS = 5000
HUMIDIFIER_YELLOW_MS = 3000
HUMIDIFIER_RED_MS = 2000

async def task_LED_Blinky():
    while True:
        await asleep_ms(1000)
        led_D13.toggle()

async def task_read_sensor():
    global shared_temp, shared_humidity
    while True:
        t = await dht20.atemperature()
        h = await dht20.ahumidity()

        await data_lock.acquire()
        shared_temp = t
        shared_humidity = h
        data_lock.release()

        print('[Sensor] Temp = {} C, Humidity = {} %'.format(t, h))

        lcd1602.clear()
        lcd1602.show(str(t), 0, 0)
        lcd1602.show(str(h), 1, 0)

        await asleep_ms(5000)

async def task_heater():
    state = None
    while True:
        await data_lock.acquire()
        t = shared_temp
        data_lock.release()

        if t < HEATER_SAFE_MAX:
            new_state = 'SAFE'
            color = '#00ff00'
        elif t < HEATER_WARNING_MAX:
            new_state = 'WARNING'
            color = '#ffa500'
        else:
            new_state = 'CRITICAL'
            color = '#ff0000'

        if new_state != state:
            state = new_state
            rgb_led_D3.show(0, hex_to_rgb(color))
            print('[Heater] state -> {} (temp={})'.format(state, t))

        await asleep_ms(500)

async def task_cooler():
    while True:
        await data_lock.acquire()
        t = shared_temp
        data_lock.release()

        if t > COOLER_THRESHOLD:
            print('[Cooler] temp={} > {} -> activating for {} ms'.format(
                t, COOLER_THRESHOLD, COOLER_DURATION_MS))
            rgb_led_D5.show(0, hex_to_rgb('#00ff00'))
            await asleep_ms(COOLER_DURATION_MS)
            rgb_led_D5.show(0, hex_to_rgb('#000000'))
        else:
            await asleep_ms(500)

async def task_humidifier():
    while True:
        await data_lock.acquire()
        h = shared_humidity
        data_lock.release()

        if h < HUMIDITY_THRESHOLD:
            print('[Humidifier] humidity={} < {} -> running cycle'.format(
                h, HUMIDITY_THRESHOLD))

            rgb_led_D7.show(0, hex_to_rgb('#00ff00'))   # GREEN
            await asleep_ms(HUMIDIFIER_GREEN_MS)

            rgb_led_D7.show(0, hex_to_rgb('#ffff00'))   # YELLOW
            await asleep_ms(HUMIDIFIER_YELLOW_MS)

            rgb_led_D7.show(0, hex_to_rgb('#ff0000'))   # RED
            await asleep_ms(HUMIDIFIER_RED_MS)

            rgb_led_D7.show(0, hex_to_rgb('#000000'))
        else:
            await asleep_ms(500)

async def setup():
    print('App started')
    create_task(task_LED_Blinky())
    create_task(task_read_sensor())
    create_task(task_heater())
    create_task(task_cooler())
    create_task(task_humidifier())

async def main():
    await setup()
    while True:
        await asleep_ms(100)

run_loop(main())
