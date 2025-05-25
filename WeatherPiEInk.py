#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# MIT License
#
# Copyright (c) 2016 LoveBootCaptain (https://github.com/LoveBootCaptain)
# Copyright (c) 2025 FabianZweckinger (https://github.com/FabianZweckinger)

# Author: Stephan Ansorge aka LoveBootCaptain, Fabian Zweckinger

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import datetime
import json
import locale
import logging
import math
import os
import sys
import threading
import time
import OpenMeteoApi
import pygame
import pygame.gfxdraw
import requests
from PIL import Image, ImageDraw
import Webserver

PATH = sys.path[0] + "/"
ICON_PATH = os.path.join(PATH, 'icons')
FONT_PATH = os.path.join(PATH, 'fonts')
LOG_PATH = os.path.join(PATH, 'logs')

# create logger
logger = logging.getLogger(__package__)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger.setLevel(logging.INFO)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

config_data = open(os.path.join(PATH, 'config.json')).read()
config = json.loads(config_data)

theme_config = config["THEME"]

theme_settings = open(os.path.join(PATH, theme_config)).read()
theme = json.loads(theme_settings)

SERVER = config['OPENMETRO_URL']
METRIC = config['LOCALE']['METRIC']

locale.setlocale(locale.LC_ALL, (config['LOCALE']['ISO'], 'UTF-8'))

THREADS = []

def start_server():
    Webserver.run_server()

if config["SERVER_MODE"]:
    # Start webserver in a separate thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

WMO_TO_IMG = {
    0: "c01",  # Clear sky
    1: "c02",  # Mainly clear
    2: "c03",  # Partly cloudy
    3: "c04",  # Overcast
    45: "a05",  # Fog
    48: "a05",  # Depositing rime fog
    51: "d01",  # Drizzle light
    53: "d02",  # Drizzle moderate
    55: "d03",  # Drizzle dense
    56: "f01",  # Freezing light
    57: "f01",  # Freezing drizzle dense
    61: "r01",  # Rain slight
    63: "r02",  # Rain moderate
    65: "r03",  # Rain heavy
    66: "f01",  # Freezing rain light
    67: "f01",  # Freezing rain heavy
    71: "s01",  # Snow fall slight
    73: "s02",  # Snow fall moderate
    75: "s03",  # Snow fall heavy
    77: "s01",  # Snow grains
    80: "r04",  # Rain shower slight
    81: "r05",  # Rain shower moderate
    82: "r06",  # Rain shower heavy
    85: "s01",  # Snow shower
    86: "s02",  # Snow shower heavy
    95: "t02",  # Thunderstorm slight or moderate
    96: "t05",  # Thunderstorm with slight
    99: "t05",  # Thunderstorm with heavy hail
}

try:
    if config['ENV'] == 'Pi':
        if config['DISPLAY']['FRAMEBUFFER'] is not False:
            # using the dashboard on a raspberry with TFT displays might make this necessary
            os.putenv('SDL_FBDEV', config['DISPLAY']['FRAMEBUFFER'])
            os.environ["SDL_VIDEODRIVER"] = "fbcon"

        LOG_PATH = '/mnt/ramdisk/'

    logger.info(f"STARTING IN {config['ENV']} MODE")


except Exception as e:
    logger.warning(e)
    quit()

pygame.display.init()
pygame.mixer.quit()
pygame.font.init()
pygame.display.set_caption('WeatherPiTFT')


def quit_all():
    pygame.display.quit()
    pygame.quit()

    global THREADS

    for thread in THREADS:
        logger.info(f'Thread killed {thread}')
        thread.cancel()
        thread.join()

    sys.exit()


# display settings from theme config
DISPLAY_WIDTH = int(config["DISPLAY"]["WIDTH"])
DISPLAY_HEIGHT = int(config["DISPLAY"]["HEIGHT"])

# the drawing area to place all text and img on
SURFACE_WIDTH = DISPLAY_WIDTH
SURFACE_HEIGHT = DISPLAY_HEIGHT

SCALE = float(DISPLAY_WIDTH / SURFACE_WIDTH)
ZOOM = 1

AA = config['DISPLAY']['AA']

# correction for 1:1 displays like hyperpixel4 square
if DISPLAY_WIDTH / DISPLAY_HEIGHT == 1:
    logger.info(f'square display configuration detected')
    square_width = int(DISPLAY_WIDTH / float(4 / 3))
    SCALE = float(square_width / SURFACE_WIDTH)

    logger.info(f'scale and display correction caused by square display')
    logger.info(f'DISPLAY_WIDTH: {square_width} new SCALE: {SCALE}')
    logger.info(f'DISPLAY_WIDTH: {square_width} new SCALE: {SCALE}')

# check if a landscape display is configured
if DISPLAY_WIDTH > DISPLAY_HEIGHT:
    logger.info(f'landscape display configuration detected')
    SCALE = float(DISPLAY_HEIGHT / SURFACE_HEIGHT)

    logger.info(f'scale and display correction caused by landscape display')
    logger.info(f'DISPLAY_HEIGHT: {DISPLAY_HEIGHT} new SCALE: {SCALE}')

# zoom the application surface rendering to display size scale
if SCALE != 1:
    ZOOM = SCALE

    if DISPLAY_HEIGHT < SURFACE_HEIGHT:
        logger.info('screen smaller as surface area - zooming smaller')
        SURFACE_HEIGHT = DISPLAY_HEIGHT
        SURFACE_WIDTH = int(SURFACE_HEIGHT / (4 / 3))
        logger.info(f'surface correction caused by small display')
        if DISPLAY_WIDTH == DISPLAY_HEIGHT:
            logger.info('small and square')
            ZOOM = round(ZOOM, 2)
        else:
            ZOOM = round(ZOOM, 1)
        logger.info(f'zoom correction caused by small display')
    else:
        logger.info('screen bigger as surface area - zooming bigger')
        SURFACE_WIDTH = int(DISPLAY_WIDTH * ZOOM)
        SURFACE_HEIGHT = int(DISPLAY_HEIGHT * ZOOM)
        logger.info(f'surface correction caused by bigger display')

    logger.info(f'SURFACE_WIDTH: {SURFACE_WIDTH} SURFACE_HEIGHT: {SURFACE_HEIGHT} ZOOM: {ZOOM}')

FIT_SCREEN = (int((DISPLAY_WIDTH - SURFACE_WIDTH) / 2), int((DISPLAY_HEIGHT - SURFACE_HEIGHT) / 2))

# the real display surface
tft_surf = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT), pygame.NOFRAME if config['ENV'] == 'Pi' else 0)

# the drawing area - everything will be drawn here before scaling and rendering on the display tft_surf
display_surf = pygame.Surface((SURFACE_WIDTH, SURFACE_HEIGHT))
# dynamic surface for status bar updates and dynamic values like fps
dynamic_surf = pygame.Surface((SURFACE_WIDTH, SURFACE_HEIGHT))
# exclusive surface for the time
time_surf = pygame.Surface((SURFACE_WIDTH, SURFACE_HEIGHT))
# surface for the weather data - will only be created once if the data is updated from the api
weather_surf = pygame.Surface((SURFACE_WIDTH, SURFACE_HEIGHT))

clock = pygame.time.Clock()

logger.info(f'display with {DISPLAY_WIDTH}px width and {DISPLAY_HEIGHT}px height is set with AA {AA}')

BACKGROUND = tuple(theme["COLOR"]["BACKGROUND"])
MAIN_FONT = tuple(theme["COLOR"]["MAIN_FONT"])
MOONLIGHT = tuple(theme["COLOR"]["MOONLIGHT"])
MOONDARK = tuple(theme["COLOR"]["MOONDARK"])
BLACK = tuple(theme["COLOR"]["BLACK"])
DARK_GRAY = tuple(theme["COLOR"]["DARK_GRAY"])
WHITE = tuple(theme["COLOR"]["WHITE"])
RED = tuple(theme["COLOR"]["RED"])
GREEN = tuple(theme["COLOR"]["GREEN"])
BLUE = tuple(theme["COLOR"]["BLUE"])
LIGHT_BLUE = tuple((BLUE[0], 210, BLUE[2]))
DARK_BLUE = tuple((BLUE[0], 100, 255))
YELLOW = tuple(theme["COLOR"]["YELLOW"])
DARK_YELLOW = tuple(theme["COLOR"]["DARK_YELLOW"])
ORANGE = tuple(theme["COLOR"]["ORANGE"])
VIOLET = tuple(theme["COLOR"]["VIOLET"])
COLOR_LIST = [BLUE, LIGHT_BLUE, DARK_BLUE]

FONT_REGULAR = theme["FONT"]["MEDIUM"]
FONT_BOLD = theme["FONT"]["BOLD"]
DATE_SIZE = int(theme["FONT"]["DATE_SIZE"] * ZOOM)
CLOCK_SIZE = int(theme["FONT"]["CLOCK_SIZE"] * ZOOM)
SMALLEST_SIZE = int(theme["FONT"]["SMALLEST_SIZE"] * ZOOM)
SMALL_SIZE = int(theme["FONT"]["SMALL_SIZE"] * ZOOM)
MEDIUM_SIZE = int(theme["FONT"]["MEDIUM_SIZE"] * ZOOM)
BIG_SIZE = int(theme["FONT"]["BIG_SIZE"] * ZOOM)
HUGE_SIZE = int(theme["FONT"]["HUGE_SIZE"] * ZOOM)

FONT_SMALLEST = pygame.font.Font(os.path.join(FONT_PATH, FONT_REGULAR), SMALLEST_SIZE)
FONT_SMALLEST_BOLD = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), SMALLEST_SIZE)
FONT_SMALL = pygame.font.Font(os.path.join(FONT_PATH, FONT_REGULAR), SMALL_SIZE)
FONT_SMALL_BOLD = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), SMALL_SIZE)
FONT_MEDIUM = pygame.font.Font(os.path.join(FONT_PATH, FONT_REGULAR), MEDIUM_SIZE)
FONT_MEDIUM_BOLD = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), MEDIUM_SIZE)
FONT_BIG = pygame.font.Font(os.path.join(FONT_PATH, FONT_REGULAR), BIG_SIZE)
FONT_BIG_BOLD = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), BIG_SIZE)
FONT_HUGE = pygame.font.Font(os.path.join(FONT_PATH, FONT_REGULAR), HUGE_SIZE)
FONT_BIG_BOLD = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), HUGE_SIZE)
DATE_FONT = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), DATE_SIZE)
CLOCK_FONT = pygame.font.Font(os.path.join(FONT_PATH, FONT_BOLD), CLOCK_SIZE)

WEATHERICON = 'unknown'

FORECASTICON_DAYS = ['unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown']

CONNECTION_ERROR = True
REFRESH_ERROR = True
PATH_ERROR = True

CONNECTION = False
READING = False
UPDATING = False

JSON_DATA_WEATHER = {}


def image_factory(image_path):
    result = {}
    for img in os.listdir(image_path):
        image_id = img.split('.')[0]
        if image_id == "":
            pass
        else:
            result[image_id] = Image.open(os.path.join(image_path, img))
    return result


class DrawString:
    def __init__(self, surf, string: str, font, color, y: int):
        """
        :param string: the input string
        :param font: the fonts object
        :param color: a rgb color tuple
        :param y: the y position where you want to render the text
        """
        self.string = string
        self.font = font
        self.color = color
        self.y = int(y * ZOOM)
        self.size = self.font.size(self.string)
        self.surf = surf

    def left(self, offset=0, rotation=0):
        """
        :param offset: define some offset pixel to move strings a little bit more left (default=0)
        """

        x = int(10 * ZOOM + (offset * ZOOM))

        self.draw_string(x, rotation)

    def right(self, offset=0, rotation=0):
        """
        :param offset: define some offset pixel to move strings a little bit more right (default=0)
        """

        x = int((SURFACE_WIDTH - self.size[0] - (10 * ZOOM)) - (offset * ZOOM))

        self.draw_string(x, rotation)

    def center(self, parts, part, offset=0, rotation=0):
        """
        :param parts: define in how many parts you want to split your display
        :param part: the part in which you want to render text (first part is 0, second is 1, etc.)
        :param offset: define some offset pixel to move strings a little bit (default=0)
        """

        x = int(((((SURFACE_WIDTH / parts) / 2) + ((SURFACE_WIDTH / parts) * part)) -
                 (self.size[0] / 2)) + (offset * ZOOM))

        self.draw_string(x, rotation)

    def draw_string(self, x, rotation=0):
        """
        takes x and y from the functions above and render the fonts
        """

        self.surf.blit(pygame.transform.rotate(self.font.render(self.string, True, self.color), rotation), (x, self.y))


class DrawImage:
    def __init__(self, surf, image=Image, y=None, size=None, fillcolor=None, angle=None):
        """
        :param image: image from the image_factory()
        :param y: the y-position of the image you want to render
        """
        self.image = image
        if y:
            self.y = int(y * ZOOM)

        self.img_size = self.image.size
        self.size = int(size * ZOOM)
        self.angle = angle
        self.surf = surf

        if angle:
            self.image = self.image.rotate(self.angle, resample=Image.BICUBIC)

        if size:
            width, height = self.image.size
            if width >= height:
                width, height = (self.size, int(self.size / width * height))
            else:
                width, height = (int(self.size / width * height), self.size)

            new_image = self.image.resize((width, height), Image.LANCZOS if AA else Image.BILINEAR)
            self.image = new_image
            self.img_size = new_image.size

        self.fillcolor = fillcolor

        self.image = pygame.image.fromstring(self.image.tobytes(), self.image.size, self.image.mode)

    @staticmethod
    def fill(surface, fillcolor: tuple):
        """converts the color on an mono colored icon"""
        surface.set_colorkey(BACKGROUND)
        w, h = surface.get_size()
        r, g, b = fillcolor
        for x in range(w):
            for y in range(h):
                a: int = surface.get_at((x, y))[3]
                # removes some distortion from scaling/zooming
                if a > 5:
                    color = pygame.Color(r, g, b, a)
                    surface.set_at((x, y), color)

    def left(self, offset=0):
        """
        :param offset: define some offset pixel to move image a little bit more left(default=0)
        """

        x = int(10 * ZOOM + (offset * ZOOM))

        self.draw_image(x)

    def right(self, offset=0):
        """
        :param offset: define some offset pixel to move image a little bit more right (default=0)
        """

        x = int((SURFACE_WIDTH - self.img_size[0] - 10 * ZOOM) - (offset * ZOOM))

        self.draw_image(x)

    def center(self, parts, part, offset=0):
        """
        :param parts: define in how many parts you want to split your display
        :param part: the part in which you want to render text (first part is 0, second is 1, etc.)
        :param offset: define some offset pixel to move strings a little bit (default=0)
        """

        x = int(((((SURFACE_WIDTH / parts) / 2) + ((SURFACE_WIDTH / parts) * part)) -
                 (self.img_size[0] / 2)) + (offset * ZOOM))

        self.draw_image(x)

    def draw_middle_position_icon(self):

        position_x = int((SURFACE_WIDTH - ((SURFACE_WIDTH / 3) / 2) - (self.image.get_rect()[2] / 2)))

        position_y = int((self.y - (self.image.get_rect()[3] / 2)))

        self.draw_image(draw_x=position_x, draw_y=position_y)

    def draw_position(self, pos: tuple):
        x, y = pos
        if y == 0:
            y += 1
        self.draw_image(draw_x=int(x * ZOOM), draw_y=int(y * ZOOM))

    def draw_absolut_position(self, pos: tuple):
        x, y = pos
        if y == 0:
            y += 1
        self.draw_image(draw_x=int(x), draw_y=int(y))

    def draw_image(self, draw_x, draw_y=None):
        """
        takes x from the functions above and the y from the class to render the image
        """

        if self.fillcolor:

            surface = self.image
            self.fill(surface, self.fillcolor)

            if draw_y:
                self.surf.blit(surface, (int(draw_x), int(draw_y)))
            else:
                self.surf.blit(surface, (int(draw_x), self.y))
        else:
            if draw_y:
                self.surf.blit(self.image, (int(draw_x), int(draw_y)))
            else:
                self.surf.blit(self.image, (int(draw_x), self.y))


def draw_hourly_temp(surf, y, size_x, size_y, hourly_temperatures, width=2, lower_offset=10):
    image = Image.new("RGBA", (size_x , size_y+width+lower_offset))
    draw = ImageDraw.Draw(image)

    temp_min = min(hourly_temperatures)
    temp_max = max(hourly_temperatures)

    segment_x_size = size_x / len(hourly_temperatures)
    hour_count=1
    for x in range(len(hourly_temperatures)):
        temp_normalized = (hourly_temperatures[x] - temp_max) / (temp_min - temp_max)
        draw.rectangle((x * segment_x_size, temp_normalized * size_y, (x+1) * segment_x_size, size_y + lower_offset), fill=YELLOW)
        draw.rectangle((x * segment_x_size, temp_normalized * size_y, (x+1) * segment_x_size, temp_normalized * size_y + width), fill=DARK_YELLOW)

        if x % 4 == 0:
            DrawString(surf, str(round(hourly_temperatures[x])) + "°C", FONT_SMALL_BOLD,
                       BLACK, y + temp_normalized * size_y + width - 22).left(x * segment_x_size + 30)
            new_datetime = datetime.datetime.now() + datetime.timedelta(hours=hour_count)
            DrawString(surf, str(new_datetime.hour).rjust(2, '0') + ":00", FONT_SMALLEST,
                       BLACK, y + size_y + 14).left(x * segment_x_size + 27)
            hour_count = hour_count + 4

    logger.debug(f'hourly temperature plot min. temp: {temp_min} max. temp: {temp_max}')

    image = pygame.image.fromstring(image.tobytes(), image.size, image.mode)

    x = SURFACE_WIDTH - size_x * 1.07

    surf.blit(image, (x, y))



def draw_hourly_precipitation_probability(surf, y, size_x, size_y, hourly_precip_prob, width=2, lower_offset=0):
    image = Image.new("RGBA", (size_x , size_y+width+lower_offset))
    draw = ImageDraw.Draw(image)

    prec_min = 0
    prec_max = 100

    segment_x_size = size_x / len(hourly_precip_prob)
    for x in range(len(hourly_precip_prob)):
        temp_normalized = (hourly_precip_prob[x] - prec_max) / (prec_min - prec_max)
        draw.rectangle((x * segment_x_size, temp_normalized * size_y, (x+1) * segment_x_size, size_y + lower_offset), fill=BLUE)
        draw.rectangle((x * segment_x_size, temp_normalized * size_y, (x+1) * segment_x_size, temp_normalized * size_y + width), fill=DARK_BLUE)

        if x % 3 == 0:
            DrawString(surf, str(round(hourly_precip_prob[x])) + "%", FONT_SMALL_BOLD,
                       BLACK, y + temp_normalized * size_y + width - 22).left(x * segment_x_size + 30)

    logger.debug(f'hourly precipitation probabilty plot min. temp: {prec_min} max. probabilty plot: {prec_max}')

    image = pygame.image.fromstring(image.tobytes(), image.size, image.mode)

    x = SURFACE_WIDTH - size_x * 1.07

    surf.blit(image, (x, y))


class Update(object):

    @staticmethod
    def update_json():

        global THREADS, CONNECTION_ERROR, CONNECTION

        thread = threading.Timer(config["TIMER"]["UPDATE"], Update.update_json)

        thread.start()

        THREADS.append(thread)

        CONNECTION = pygame.time.get_ticks() + 1500  # 1.5 seconds

        try:
            logger.info(f'connecting to server: {SERVER}')

            current_datetime = datetime.datetime.now()

            weather = OpenMeteoApi.get_weather(current_datetime)

            data = {'weather': weather}

            with open(LOG_PATH + '_latest_weather.json', 'w+') as outputfile:
                json.dump(data, outputfile, indent=2, sort_keys=True)

            logger.info('json file saved')

            CONNECTION_ERROR = False

        except (requests.HTTPError, requests.ConnectionError) as update_ex:

            CONNECTION_ERROR = True

            logger.warning(f'Connection ERROR: {update_ex}')

    @staticmethod
    def read_json():

        global THREADS, JSON_DATA_WEATHER, REFRESH_ERROR, READING

        thread = threading.Timer(config["TIMER"]["RELOAD"], Update.read_json)

        thread.start()

        THREADS.append(thread)

        READING = pygame.time.get_ticks() + 1500  # 1.5 seconds

        try:

            data = open(LOG_PATH + '_latest_weather.json').read()

            new_json_data = json.loads(data)

            logger.info('json file read by module')
            logger.info(f'{new_json_data}')

            JSON_DATA_WEATHER = new_json_data['weather']

            REFRESH_ERROR = False

        except IOError as read_ex:

            REFRESH_ERROR = True

            logger.warning(f'ERROR - json file read by module: {read_ex}')

        Update.icon_path()

    @staticmethod
    def icon_path():

        global WEATHERICON, FORECASTICON_DAYS, PRECIPTYPE, PRECIPCOLOR, UPDATING

        icon_extension = '.png'
        day_or_night = 'd'

        updated_list = []

        forecast_icons = []
        for i in range(7):
            forecast_icons.append(str(WMO_TO_IMG[JSON_DATA_WEATHER['daily_weathercodes'][i]]))

        logger.debug(forecast_icons)

        logger.debug(f'validating path: {forecast_icons}')

        # Current weather:
        df_sun = theme["DATE_FORMAT"]["SUNRISE_SUNSET"]
        new_datetime = datetime.datetime.now()

        sunrise = format_datetime(JSON_DATA_WEATHER['current_sunrise'], df_sun)
        sunset = format_datetime(JSON_DATA_WEATHER['current_sunset'], df_sun)

        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        sunrise_with_date = today_date + " " + sunrise
        sunset_with_date = today_date + " " + sunset

        sunrise_time = datetime.datetime.strptime(sunrise_with_date, "%Y-%m-%d %H:%M")
        sunset_time = datetime.datetime.strptime(sunset_with_date, "%Y-%m-%d %H:%M")

        # Current weather day or night
        current_icon = str(WMO_TO_IMG[JSON_DATA_WEATHER['current_weathercode']])

        day_or_night = 'd'
        if sunset_time < new_datetime or new_datetime < sunrise_time:
            day_or_night = 'n'
        if os.path.isfile(os.path.join(ICON_PATH, current_icon + day_or_night + icon_extension)):
            logger.debug(f'TRUE : {current_icon}')
            updated_list.append(current_icon + day_or_night)
        else:
            logger.warning(f'FALSE : {current_icon}')
            updated_list.append('unknown')


        for icon in forecast_icons:
            if os.path.isfile(os.path.join(ICON_PATH, icon + 'd' + icon_extension)):
                logger.debug(f'TRUE : {icon}')
                updated_list.append(icon + 'd')
            else:
                logger.warning(f'FALSE : {icon}')
                updated_list.append('unknown')

        WEATHERICON = updated_list[0]
        FORECASTICON_DAYS = [updated_list[1], updated_list[2], updated_list[3], updated_list[4], updated_list[5],
                             updated_list[6]]

        global PATH_ERROR

        if any("unknown" in s for s in updated_list):

            PATH_ERROR = True

        else:

            PATH_ERROR = False

        logger.info(f'update path for icons: {updated_list}')

        Update.get_precip_type()

    @staticmethod
    def get_precip_type():

        global JSON_DATA_WEATHER

        Update.create_surface()

    @staticmethod
    def create_surface():

        global weather_surf, UPDATING

        new_surf = pygame.Surface((SURFACE_WIDTH, SURFACE_HEIGHT))
        new_surf.fill(BACKGROUND)

        df_forecast = theme["DATE_FORMAT"]["FORECAST_DAY"]
        df_sun = theme["DATE_FORMAT"]["SUNRISE_SUNSET"]

        sunrise = format_datetime(JSON_DATA_WEATHER['current_sunrise'], df_sun)
        sunset = format_datetime(JSON_DATA_WEATHER['current_sunset'], df_sun)

        wind_speed = float(JSON_DATA_WEATHER['current_windspeed'])
        wind_speed = wind_speed if METRIC else wind_speed / 1.609
        wind_speed_unit = 'km/h' if METRIC else 'mph'
        wind_speed_string = str(f'{round(wind_speed, 1)} {wind_speed_unit}')

        current_humidity = JSON_DATA_WEATHER['current_humidity']
        current_humidity_string = str(current_humidity) + "%"

        current_pressure = JSON_DATA_WEATHER['current_pressure']
        current_pressure_string = str(current_pressure) + " mbar"

        current_uvi = JSON_DATA_WEATHER['uv_index_max']

        DrawImage(new_surf, images[WEATHERICON], size=120).draw_position(pos=(30, 80))

        temp_out_unit = "°C" if METRIC else "°F"
        temp_out = str(round(JSON_DATA_WEATHER["current_temperature"]))
        apparent_temperature = JSON_DATA_WEATHER['apparent_temperature']
        apparent_temperature_string = config['LOCALE']['FEELS_LIKE'] + " " + str(apparent_temperature) + temp_out_unit

        DrawString(new_surf, temp_out, FONT_HUGE, BLACK, 90).right(560)
        DrawString(new_surf, temp_out_unit, FONT_BIG, BLACK, 101).right(530)
        DrawString(new_surf, apparent_temperature_string, FONT_MEDIUM, BLACK, 155).right(530)

        # Draw daily forcast
        for i, day in enumerate(FORECASTICON_DAYS):
            day_ts = format_date(JSON_DATA_WEATHER['daily_dates'][i], df_forecast)
            DrawString(new_surf, day_ts, FONT_SMALL_BOLD, MAIN_FONT, 360).left(110 * i + 50)

            day_max_temp = int(JSON_DATA_WEATHER['daily_temperatures_max'][i])
            day_min_temp = int(JSON_DATA_WEATHER['daily_temperatures_min'][i])
            DrawString(new_surf, str(day_max_temp) + "° / " + str(day_min_temp) + "°", FONT_SMALL_BOLD, MAIN_FONT,
                       447).center(1, 0, 110 * i - 330)

            DrawImage(new_surf, images[day], size=70).draw_position(pos=(110 * i + 35, 375))

        # Moon
        DrawString(new_surf, config['LOCALE']['MOON'], FONT_SMALL_BOLD, MAIN_FONT, 360).left(110 * 6 + 50)

        draw_moon_layer(new_surf, int(708 * ZOOM), int(385 * ZOOM), int(60 * ZOOM))

        grid_data = [[images['sunset'], sunset],
                     [images['sunrise'], sunrise],
                     [images['humidity'], current_humidity_string],
                     [images['wind'], wind_speed_string],
                     [images['uvi'], current_uvi],
                     [images['pressure'], current_pressure_string], ]

        # Draw "data grid"
        for x in range(2):
            for y in range(3):
                DrawString(new_surf, str(grid_data[y * 2 + x][1]), FONT_MEDIUM_BOLD, MAIN_FONT,
                           105 + 44 * y).center(1, 0, -225 * x + 90 + 225)
                DrawImage(new_surf, grid_data[y * 2 + x][0], 95 + 44 * y, size=40).right(225 * x + 150)

        draw_hourly_temp(new_surf, int(230 * ZOOM), int(710 * ZOOM), int(45 * ZOOM),
                         JSON_DATA_WEATHER['hourly_temperatures'])

        draw_hourly_precipitation_probability(new_surf, int(325 * ZOOM), int(710 * ZOOM), int(15 * ZOOM),
                            JSON_DATA_WEATHER['hourly_precipitation_probability'])

        weather_surf = new_surf

        logger.info(f'temp out: {temp_out}')
        logger.info(f'icon: {WEATHERICON}')
        #Seems to produce errors on Ubuntu:
        #logger.info(f'forecast: 'f'{str(format_date(JSON_DATA_WEATHER['daily_dates'][0], df_forecast))} {int(JSON_DATA_WEATHER['daily_temperatures_min'][0])} {FORECASTICON_DAYS[0]}; '
        #            f'{str(format_date(JSON_DATA_WEATHER['daily_dates'][1], df_forecast))} {int(JSON_DATA_WEATHER['daily_temperatures_min'][1])} {FORECASTICON_DAYS[1]}; '
        #             f'{str(format_date(JSON_DATA_WEATHER['daily_dates'][2], df_forecast))} {int(JSON_DATA_WEATHER['daily_temperatures_min'][2])} {FORECASTICON_DAYS[2]}')
        logger.info(f'sunrise: {sunrise} ; sunset {sunset}')
        logger.info(f'WindSpeed: {wind_speed_string}')

        # remove the ended timer and threads
        global THREADS
        THREADS = [t for t in THREADS if t.is_alive()]
        logging.info(f'threads cleaned: {len(THREADS)} left in the queue')

        pygame.time.delay(1500)
        UPDATING = pygame.time.get_ticks() + 1500  # 1.5 seconds

        return weather_surf

    @staticmethod
    def run():
        Update.update_json()
        Update.read_json()


def format_date(date_string, date_format):
    return datetime.datetime.strptime(date_string, "%Y-%m-%d").strftime(date_format)


def format_datetime(datetime_string, datetime_format):
    return datetime.datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M").strftime(datetime_format)


def get_brightness():
    current_time = int(format_datetime(time.time(), '%H'))
    return 25 if current_time >= 20 or current_time <= 5 else 100


def draw_time_layer():
    current_datetime = datetime.datetime.now()

    # Calculate how many minutes to add to round up to the next 5-minute mark
    minute = current_datetime.minute
    remainder = minute % 5
    if remainder != 0:
        # Add minutes to get to next multiple of 5
        add_minutes = 5 - remainder
        current_datetime = current_datetime + datetime.timedelta(minutes=add_minutes)

    date_day_string = current_datetime.strftime(theme["DATE_FORMAT"]["DATE"])
    date_time_string = current_datetime.strftime(theme["DATE_FORMAT"]["TIME"])

    logger.debug(f'Day: {date_day_string}')
    logger.debug(f'Time: {date_time_string}')

    DrawString(time_surf, date_day_string, DATE_FONT, MAIN_FONT, 68).center(1, 0)
    DrawString(time_surf, date_time_string, CLOCK_FONT, MAIN_FONT, 0).center(1, 0)


def draw_moon_layer(surf, x, y, size):
    # based on @miyaichi's fork -> great idea :)
    _size = 1000
    dt = datetime.datetime.strptime(JSON_DATA_WEATHER['daily_dates'][0], "%Y-%m-%d")
    moon_age = (((dt.year - 11) % 19) * 11 + [0, 2, 0, 2, 2, 4, 5, 6, 7, 8, 9, 10][dt.month - 1] + dt.day) % 30

    image = Image.new("RGBA", (_size + 2, _size + 2))
    draw = ImageDraw.Draw(image)

    radius = int(_size / 2)

    # draw full moon
    draw.ellipse([(1, 1), (_size, _size)], fill=MOONLIGHT)

    # draw dark side of the moon
    theta = moon_age / 14.765 * math.pi
    sum_x = sum_length = 0

    for _y in range(-radius, radius, 1):
        alpha = math.acos(_y / radius)
        _x = radius * math.sin(alpha)
        length = radius * math.cos(theta) * math.sin(alpha)

        if moon_age < 15:
            start = (radius - _x, radius + _y)
            end = (radius + length, radius + _y)
        else:
            start = (radius - length, radius + _y)
            end = (radius + _x, radius + _y)

        draw.line((start, end), fill=MOONDARK)

        sum_x += 2 * _x + x
        sum_length += end[0] - start[0]

    logger.debug(f'moon phase age: {moon_age} percentage: {round(100 - (sum_length / sum_x) * 100, 1)}')

    image = image.resize((size, size), Image.LANCZOS if AA else Image.BILINEAR)
    image = pygame.image.fromstring(image.tobytes(), image.size, image.mode)

    surf.blit(image, (x, y))


def create_scaled_surf(surf, aa=False):
    if aa:
        scaled_surf = pygame.transform.smoothscale(surf, (SURFACE_WIDTH, SURFACE_HEIGHT))
    else:
        scaled_surf = pygame.transform.scale(surf, (SURFACE_WIDTH, SURFACE_HEIGHT))

    return scaled_surf


def loop():
    Update.run()

    running = True

    while running:
        now = datetime.datetime.now()

        # Only update when minute is multiple of 5 and second is 0
        if not config["SERVER_MODE"] or now.minute % 2 == 0 and now.second < 30:
            tft_surf.fill(BACKGROUND)

            # fill the actual main surface and blit the image/weather layer
            display_surf.fill(BACKGROUND)
            display_surf.blit(weather_surf, (0, 0))

            # fill the dynamic layer, make it transparent and use draw functions that write to that surface
            dynamic_surf.fill(BACKGROUND)
            dynamic_surf.set_colorkey(BACKGROUND)

            # finally take the dynamic surface and blit it to the main surface
            display_surf.blit(dynamic_surf, (0, 0))

            # now do the same for the time layer so it did not interfere with the other layers
            # fill the layer and make it transparent as well
            time_surf.fill(BACKGROUND)
            time_surf.set_colorkey(BACKGROUND)

            # draw the time to the main layer
            draw_time_layer()
            display_surf.blit(time_surf, (0, 0))

            for event in pygame.event.get():

                if event.type == pygame.QUIT:

                    running = False

                    quit_all()

                elif event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_ESCAPE:

                        running = False

                        quit_all()

                    elif event.key == pygame.K_SPACE:
                        pygame.image.save(display_surf, 'screenshot.png')
                        logger.info('Screenshot created')

            # finally take the main surface and blit it to the tft surface
            tft_surf.blit(create_scaled_surf(display_surf, aa=AA), FIT_SCREEN)

            # update the display with all surfaces merged into the main one
            pygame.display.update()

            # Sleep a bit to reduce CPU usage
            if config["SERVER_MODE"]:
                pygame.image.save(display_surf, 'temp_screenshot.png')

                # Open the PNG and convert to JPG with Pillow
                img = Image.open('temp_screenshot.png')
                img = img.convert('RGB')  # JPG doesn't support alpha channel
                img.save('screenshot.jpg', 'JPEG')

                logger.info('Screenshot created')
                time.sleep(30)

        clock.tick(1)

    quit_all()


if __name__ == '__main__':

    try:
        images = image_factory(ICON_PATH)
        loop()

    except KeyboardInterrupt:
        quit_all()
