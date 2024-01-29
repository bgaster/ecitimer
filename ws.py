import network
import socket
import time

# from netman import connect_to_network
from machine import Pin
import uasyncio as asyncio
import aqueue
import netman

import neopixel

ws_pin = 17
led_num = 30
BRIGHTNESS = 0.2  # Adjust the brightness (0.0 - 1.0)
disco_speed = 50 / 1000.0;  

neoRing = neopixel.NeoPixel(Pin(ws_pin), led_num)

def colorHSV(hue, sat = 255, val = 255):
        """
        Converts HSV color to rgb tuple and returns it.
        The logic is almost the same as in Adafruit NeoPixel library:
        https://github.com/adafruit/Adafruit_NeoPixel so all the credits for that
        go directly to them (license: https://github.com/adafruit/Adafruit_NeoPixel/blob/master/COPYING)

        :param hue: Hue component. Should be on interval 0..65535
        :param sat: Saturation component. Should be on interval 0..255
        :param val: Value component. Should be on interval 0..255
        :return: (r, g, b) tuple
        """
        if hue >= 65536:
            hue %= 65536

        hue = (hue * 1530 + 32768) // 65536
        if hue < 510:
            b = 0
            if hue < 255:
                r = 255
                g = hue
            else:
                r = 510 - hue
                g = 255
        elif hue < 1020:
            r = 0
            if hue < 765:
                g = 255
                b = hue - 510
            else:
                g = 1020 - hue
                b = 255
        elif hue < 1530:
            g = 0
            if hue < 1275:
                r = hue - 1020
                b = 255
            else:
                r = 255
                b = 1530 - hue
        else:
            r = 255
            g = 0
            b = 0

        v1 = 1 + val
        s1 = 1 + sat
        s2 = 255 - sat

        r = ((((r * s1) >> 8) + s2) * v1) >> 8
        g = ((((g * s1) >> 8) + s2) * v1) >> 8
        b = ((((b * s1) >> 8) + s2) * v1) >> 8

        return r, g, b

async def theater_chase_rainbow(wait):
    # First pixel starts at red (hue 0)
    first_pixel_hue = 0
  
    for a in range(0,30):
        for b in range(0,3):
            neoRing.fill((0,0,0))
            neoRing.write()
    
            #    'c' counts up from 'b' to end of strip in increments of 3...
            for c in range(0,led_num, 2):
                # hue of pixel 'c' is offset by an amount to make one full
                # revolution of the color wheel (range 65536) along the length
                # of the strip (strip.numPixels() steps):
                hue   = int(first_pixel_hue + c * 65536 / led_num);
                # hue -> RGB
                r, g, b = colorHSV(hue)
                # we really need to gamma32((r,g,b))
                color = (r,g,b) 
                # // Set pixel 'c' to value 'color'
                neoRing[c] = color 

            neoRing.write();                
            await asyncio.sleep(wait);                 
            # One cycle of color wheel over 90 frames
            firstPixelHue = first_pixel_hue + (65536 / 90); 

def set_brightness(color):
    r, g, b = color
    r = int(r * BRIGHTNESS)
    g = int(g * BRIGHTNESS)
    b = int(b * BRIGHTNESS)
    return (r, g, b)

# led = Pin(15, Pin.OUT)
onboard = Pin("LED", Pin.OUT, value=0)

# ssid = 'gideon'
# password = 'cloudysky326'
ssid = 'Ben\'s iPhone (2)'
password = 'k0w9m2pbdr7h'
country = 'GB'

def make_html(ip, status):
    html = """<!DOCTYPE html>
    <html>
    <head> <title>ECI Lighting Talk Timer</title> </head>
        <body> <h1>ECI Lighting Talk Timer</h1>
            <p><a href="http://"""+ip+"""/">Home</a></p>
            <p>Current status: %s</p>
            <p><a href="http://"""+ip+"""/light/start">Start</a></p>
            <p><a href="http://"""+ip+"""/light/stop">Stop</a></p>
            <p><a href="http://"""+ip+"""/light/twominute">Two Minute</a></p>
            <p><a href="http://"""+ip+"""/light/fourminute">Four Minute</a></p>
            <p><a href="http://"""+ip+"""/light/pechakucha">Psecha Kucha</a></p>
            <p><a href="http://"""+ip+"""/light/test">Test (30 sec)</a></p>
            <br>
            <br>
            <p>by ECI Group</p>
        </body>
    </html>
    """
    return html % status

async def serve_client(reader, writer, wifi_connection, queue):
    print("Client connected")
    request_line = await reader.readline()
    print("Request:", request_line)
    # We are not interested in HTTP request headers, skip them
    while await reader.readline() != b"\r\n":
        pass

    request = str(request_line)
    start = request.find('/light/start')
    stop = request.find('/light/stop')
    two_minute = request.find('/light/twominute')
    four_minute = request.find('/light/fourminute')
    pecha_kucha = request.find('/light/pechakucha')
    test = request.find('/light/test')

    print( 'led on = ' + str(start))
    print( 'led off = ' + str(stop))

    stateis = ""
    if start == 6:
        print("led on")
        await queue.put({"start": ()})
        stateis = "timer start"
    
    if stop == 6:
        print("led off")
        await queue.put({"stop": ()})
        stateis = "timer stop"

    if two_minute == 6:
        print("two minute timer")
        await queue.put({"time": (2 * 60, 12, 12)})

    if test == 6:
        print("test (30 sec) timer")
        await queue.put({"time": (30, 12, 12)})

    # if four_minute == 6:
    #     print("four minute timer")
    #     await queue.put({"time": (4 * 1000,4 * 1000,4 * 1000)})

    # if pecha_kucha == 6:
    #     print("Pecha Kucha timer")
    #     await queue.put({"time": (6 * 60 + 40) * 1000})
        
    response = make_html(wifi_connection[0], stateis)
    writer.write('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
    writer.write(response)

    await writer.drain()
    await writer.wait_closed()
    print("Client disconnected")

async def main():
    print('Connecting to Network...')
    # wifi_connection = netman.connect_to_network(ssid = 'gideon', password = 'cloudysky326', country = 'UK')
    wifi_connection = netman.connect_to_network(ssid = 'BenPhone', password = 'k0w9m2pbdr7h', country = 'UK')

    # state
    black = (0,0,0)
    green = (0,255,0)
    red   = (255,0,0)
    orange = (255, 40, 0)

    colour = green

    # clear the neopixels
    neoRing.fill(black)
    neoRing.write()

    # messages from server
    #  { "start": (),
    #    "stop": (),
    #    "time": int
    #  }
    #  Messages:
    #     ["start"], start timer
    #     ["stop"], stop timer
    #     ["time"], time in ms for timer
    queue = aqueue.Queue()

    print('Setting up webserver...')
    asyncio.create_task(asyncio.start_server(lambda r, w: serve_client(r,w,wifi_connection,queue), "0.0.0.0", 80))
    
    duration = 0.0
    green_steps = -1
    orange_steps = -1
    step = 0
    running = False
    timings = []
    
    while True:
        message = {}
        try:
            message = queue.get_nowait()
        except aqueue.QueueEmpty:
            pass

        if "start" in message: 
            print('start')
            if green_steps != 0:
                running = True
        elif "stop" in message:
            # stop timer
            duration = 0.0
            green_steps = -1
            orange_steps = -1
            step = 0
            running = False
            colour = green
            # clear ring
            neoRing.fill((0,0,0))
            neoRing.write()
        elif "time" in message:
            details = message['time']
            duration = details[0]
            # print('duration: ' + str(duration))
            # print('duration over leds')
            green_steps  = details[1]
            orange_steps = details[2]  
            print("green_steps: " + str(green_steps))
            print('organge_steps: ' + str(orange_steps))

            # exponetial progression of LEDs over the timer duration
            base = 2  # Choose a base for the exponential decrease

            timings = [duration * (base ** (-i / (led_num - 1))) for i in range(led_num)]

            # Calculate and apply scaling factor
            sum_diff = duration - sum(timings)
            scale_factor = 1 + sum_diff / sum(timings)
            timings = [value * scale_factor for value in timings]

            # print('total: ' + str(sum(timings)))
                
        if step == green_steps:
            colour = orange
        elif step == (green_steps + orange_steps):
            colour = red

        # check to see if time has expired
        if step == led_num and running:
            print('stopping')
            await theater_chase_rainbow(disco_speed)
            duration = 0.0
            green_steps = -1
            orange_steps = -1
            step = 0
            running = False
            colour = green

        if running:
            ani_time_now = timings[step] / (led_num - step)
            for l in range(led_num, step, -1):
                if l != led_num:
                    neoRing[l] = black            

                neoRing[l-1] = colour
                neoRing.write()
                await asyncio.sleep(ani_time_now)

            step = step + 1
        
        if not running:
            await asyncio.sleep(0.25)
        
        # onboard.on()
        # print("heartbeat")
        # await asyncio.sleep(0.25)
        # onboard.off()
        # await asyncio.sleep(5)
        
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()

    # 2 mins

    # 30 leds


    # Green   60x
    # Orange  25
    # Red     15