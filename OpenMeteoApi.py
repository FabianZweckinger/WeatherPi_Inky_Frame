from datetime import timedelta
from WeatherPiEInk import config
import requests

# Weather code (WMO):
# 0	            Clear sky
# 1, 2, 3       Mainly clear, partly cloudy, and overcast
# 45, 48        Fog and depositing rime fog
# 51, 53, 55	Drizzle: Light, moderate, and dense intensity
# 56, 57        Freezing Drizzle: Light and dense intensity
# 61, 63, 65	Rain: Slight, moderate and heavy intensity
# 66, 67	    Freezing Rain: Light and heavy intensity
# 71, 73, 75	Snow fall: Slight, moderate, and heavy intensity
# 77	        Snow grains
# 80, 81, 82	Rain showers: Slight, moderate, and violent
# 85, 86	    Snow showers slight and heavy
# 95 *	        Thunderstorm: Slight or moderate
# 96, 99 *	    Thunderstorm with slight and heavy hail

def get_weather(current_datetime):
    time_delta = current_datetime + timedelta(days=7)

    # Create date strings for api
    forecast_today_str = str(current_datetime.year) + '-' \
                         + str(current_datetime.month).zfill(2) + '-' \
                         + str(current_datetime.day).zfill(2)

    forecast_last_date_str = str(time_delta.year) + '-' \
                             + str(time_delta.month).zfill(2) + '-' \
                             + str(time_delta.day).zfill(2)

    url = config["OPENMETRO_URL"].format(config["OPENMETRO_WEATHER_LAT"], config["OPENMETRO_WEATHER_LONG"],
                                         config["OPENMETRO_TIMEZONE"], forecast_today_str, forecast_last_date_str)
    print('Weather API URL: ' + url)

    weather_response = requests.get(url).json()

    return {
        'daily_dates': weather_response['daily']['time'][1:],
        'daily_temperatures_min': weather_response['daily']['temperature_2m_min'][1:],
        'daily_temperatures_max': weather_response['daily']['temperature_2m_max'][1:],
        'daily_weathercodes': weather_response['daily']['weathercode'][1:],
        'hourly_temperatures': weather_response['hourly']['temperature_2m'][current_datetime.hour + 1:current_datetime.hour + 24],
        'hourly_precipitation_probability': weather_response['hourly']['precipitation_probability'][current_datetime.hour + 1:current_datetime.hour + 24],
        'current_weathercode': weather_response['hourly']['weathercode'][current_datetime.hour],
        'current_temperature': weather_response['hourly']['temperature_2m'][current_datetime.hour:current_datetime.hour + 1][0],
        'current_humidity': weather_response['hourly']['relativehumidity_2m'][current_datetime.hour:current_datetime.hour + 1][0],
        'current_windspeed': weather_response['hourly']['windspeed_10m'][current_datetime.hour:current_datetime.hour + 1][0],
        'current_sunrise': weather_response['daily']['sunrise'][0],
        'current_sunset': weather_response['daily']['sunset'][0],
        'relative_humidity_2m': weather_response['current']['relative_humidity_2m'],
        'current_pressure': weather_response['current']['pressure_msl'],
        'apparent_temperature': weather_response['current']['apparent_temperature'],
        'uv_index_max': weather_response['daily']['uv_index_max'][0],
    }
