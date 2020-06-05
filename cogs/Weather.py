import asyncio
import logging

import aiohttp
import pendulum
from discord import Embed
from discord.ext import commands

from util import celsius_to_fahrenheit, meters_to_miles
from const import WEATHER_EMOJI

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Weather(bot))


def temp_string(temp):
    return f"{round(temp, 1)}°C ({round(celsius_to_fahrenheit(temp), 1)}°F)"


def icon_to_emoji(icon_string):
    icon = icon_string[:2]
    return WEATHER_EMOJI[icon]


class OpenWeatherMapApiException(Exception):
    pass


class Weather(commands.Cog):
    CURRENT_WEATHER_API_URL = 'https://api.openweathermap.org/data/2.5/weather'
    ONECALL_WEATHER_API_URL = 'https://api.openweathermap.org/data/2.5/onecall'

    MSG_REQUEST_FAILED = 'The request to OpenWeatherMap\'s API failed.'

    def __init__(self, bot):
        self.bot = bot
        self.app_id = self.bot.config['openweathermap']['app_id']
        self.session = aiohttp.ClientSession()

    async def _make_request(self, method, route):
        async with self.session.request(method, route) as response:
            if response.status == 200:
                content = await response.json()
                return content
            elif response.status == 404:
                content = await response.json()
                raise commands.BadArgument(content['message'])
            else:
                content = await response.json()
                raise OpenWeatherMapApiException(content['message'])

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    @commands.group(name='weather', invoke_without_command=True)
    async def weather(self, ctx, *, args=None):
        if args:
            await ctx.invoke(self.current, location=args)
        else:
            await ctx.send_help(self.weather)

    @weather.command()
    async def current(self, ctx, *, location):
        response = await self._make_request('get', f'{Weather.CURRENT_WEATHER_API_URL}?appid={self.app_id}&q={location}&units=metric')
        coords = response['coord']
        lon, lat = coords.values()

        response_onecall = await self._make_request('get', f'{Weather.ONECALL_WEATHER_API_URL}?appid={self.app_id}&lon={lon}&lat={lat}&units=metric')
        current = response_onecall['current']

        content = {
            'id': response['id'],
            'city': response['name'],
            'country': response['sys']['country'],
            'main': current['weather'][0]['main'],
            'description': current['weather'][0]['description'],
            'pressure': current['pressure'],
            'humidity': current['humidity'],
            'temp': current['temp'],
            'temp_min': min([hourly['temp'] for hourly in response_onecall['hourly']]),
            'temp_max': max([hourly['temp'] for hourly in response_onecall['hourly']]),
            'feels_like': current['feels_like'],
            'visibility': current['visibility'],
            'wind_deg': current['wind_deg'],
            'wind_speed': current['wind_speed'],
            'clouds': current['clouds'],
            'uvi': current['uvi'],
            'rain': current['rain'] if 'rain' in current else None,
            'snow': current['snow'] if 'snow' in current else None,
            'icon': f"http://openweathermap.org/img/wn/{current['weather'][0]['icon']}.png",
            'emoji': icon_to_emoji(current['weather'][0]['icon'])
        }

        embed = Embed()
        embed.add_field(name='Currently', value=f"{content['emoji']} {content['description']}")
        embed.add_field(name='Pressure', value=f"{content['pressure']} mbar")
        embed.add_field(name='Humidity', value=f"{content['humidity']}%")
        embed.add_field(name='Temperature Low', value=temp_string(content['temp_min']))
        embed.add_field(name='Temperature', value=temp_string(content['temp']))
        embed.add_field(name='Temperature High', value=temp_string(content['temp_max']))
        embed.add_field(name='Visibility',
                        value=f"{round(content['visibility'] / 1000, 3)} km "
                              f"({round(meters_to_miles(content['visibility']), 3)} mi)")
        embed.add_field(name='Wind Direction', value=f"{content['wind_deg']}°")
        embed.add_field(name='Wind Speed', value=f"{content['wind_speed']} m/s")
        embed.add_field(name='Clouds', value=f"{content['clouds']}%")
        embed.add_field(name='UV Index', value=content['uvi'])
        embed.timestamp = pendulum.now('UTC')
        embed.set_author(name=f"{content['city']}, {content['country']} at openweathermap.org",
                         url=f"https://openweathermap.org/city/{content['id']}",
                         icon_url=content['icon'])
        embed.set_footer(text='Powered by openweathermap.org')
        await ctx.send(embed=embed)

    @weather.error
    @current.error
    async def current_error(self, ctx, error):
        if isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(error)
        else:
            logger.exception(error)
