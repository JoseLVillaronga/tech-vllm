"""
title: Consulta de Clima y Pronóstico (OpenWeatherMap)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Consulta de clima actual y pronóstico extendido a 5 días con ajuste automático de zona horaria IANA para cualquier ciudad del mundo.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.2.0
license: MIT
"""

import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pydantic import BaseModel, Field

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


class Tools:
    class Valves(BaseModel):
        OPENWEATHER_API_KEY: str = Field(
            default="TU_OPENWEATHER_API_KEY_AQUI",
            description="API Key de OpenWeatherMap (obtenida gratis en https://openweathermap.org/api)"
        )
        DEFAULT_TIMEZONE: str = Field(
            default="America/Argentina/Buenos_Aires",
            description="Zona horaria IANA por defecto para horas de salida/puesta del sol y fechas (ej: 'America/Argentina/Buenos_Aires', 'America/Montevideo', 'Europe/Madrid', o 'auto')"
        )
        DEFAULT_UNITS: str = Field(
            default="metric",
            description="Unidades de medida: 'metric' (Celsius), 'imperial' (Fahrenheit)"
        )
        DEFAULT_LANG: str = Field(
            default="es",
            description="Idioma de las descripciones (ej: 'es', 'en')"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _format_timestamp(self, ts: Optional[int], city_tz_offset: int = 0) -> str:
        if not ts:
            return "N/D"
        tz_setting = str(self.valves.DEFAULT_TIMEZONE).strip()
        if tz_setting.lower() == "auto":
            tz = timezone(timedelta(seconds=city_tz_offset))
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
            return dt.strftime("%H:%M:%S")
        if ZoneInfo:
            try:
                tz = ZoneInfo(tz_setting)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
                return dt.strftime("%H:%M:%S")
            except Exception:
                pass
        tz = timezone(timedelta(seconds=city_tz_offset))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
        return dt.strftime("%H:%M:%S")

    def _format_date(self, ts: Optional[int], city_tz_offset: int = 0) -> str:
        if not ts:
            return ""
        tz_setting = str(self.valves.DEFAULT_TIMEZONE).strip()
        if tz_setting.lower() != "auto" and ZoneInfo:
            try:
                tz = ZoneInfo(tz_setting)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        tz = timezone(timedelta(seconds=city_tz_offset))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
        return dt.strftime("%Y-%m-%d")

    def get_current_weather(self, city: str, country_code: Optional[str] = None) -> str:
        """
        Obtiene el clima actual y el reporte detallado del día de hoy para una ciudad o localidad.
        :param city: Nombre de la ciudad o localidad (ej: 'Buenos Aires', 'San Nicolas', 'Madrid', 'Rosario').
        :param country_code: Código ISO de dos letras del país opcional (ej: 'AR', 'ES', 'UY', 'CL').
        :return: Resumen detallado del clima de hoy con mínimas, máximas, sensación térmica, viento, humedad, amanecer y atardecer en hora local.
        """
        clean_city = str(city).strip() if city and not str(type(city)).endswith("FieldInfo'>") else ""
        clean_country = str(country_code).strip() if country_code and not str(type(country_code)).endswith("FieldInfo'>") else None

        query = f"{clean_city},{clean_country}" if clean_country else clean_city
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": query,
            "units": str(self.valves.DEFAULT_UNITS),
            "lang": str(self.valves.DEFAULT_LANG),
            "appid": str(self.valves.OPENWEATHER_API_KEY)
        }

        try:
            response = requests.get(url, params=params, timeout=10.0)
            if response.status_code == 404:
                return f"Error: No se encontró la ciudad '{clean_city}'. Verifica el nombre o especifica el país."
            response.raise_for_status()
            data = response.json()

            city_tz_offset = data.get("timezone", 0)
            sunrise_ts = data.get("sys", {}).get("sunrise")
            sunset_ts = data.get("sys", {}).get("sunset")

            sunrise_str = self._format_timestamp(sunrise_ts, city_tz_offset)
            sunset_str = self._format_timestamp(sunset_ts, city_tz_offset)

            clima_info = {
                "ciudad": data.get("name"),
                "pais": data.get("sys", {}).get("country"),
                "temperatura_C": data.get("main", {}).get("temp"),
                "sensacion_termica_C": data.get("main", {}).get("feels_like"),
                "temp_min_C": data.get("main", {}).get("temp_min"),
                "temp_max_C": data.get("main", {}).get("temp_max"),
                "humedad_pct": data.get("main", {}).get("humidity"),
                "presion_hPa": data.get("main", {}).get("pressure"),
                "viento_ms": data.get("wind", {}).get("speed"),
                "estado_cielo": data.get("weather", [{}])[0].get("description", "N/D"),
                "amanecer": f"{sunrise_str} (hora local)",
                "atardecer": f"{sunset_str} (hora local)"
            }
            return f"Clima actual y reporte de hoy en {clima_info['ciudad']} ({clima_info['pais']}):\n" + "\n".join(f"- {k}: {v}" for k, v in clima_info.items())
        except Exception as e:
            return f"Error al consultar el clima actual: {str(e)}"

    def get_weather_forecast(self, city: str, country_code: Optional[str] = None) -> str:
        """
        Obtiene el pronóstico meteorológico extendido para los próximos 5 días de una ciudad o localidad.
        :param city: Nombre de la ciudad o localidad (ej: 'Buenos Aires', 'San Nicolas', 'Cordoba').
        :param country_code: Código ISO de dos letras del país opcional (ej: 'AR', 'ES', 'MX').
        :return: Pronóstico agrupado día por día con temperaturas mínimas, máximas y estado del tiempo.
        """
        clean_city = str(city).strip() if city and not str(type(city)).endswith("FieldInfo'>") else ""
        clean_country = str(country_code).strip() if country_code and not str(type(country_code)).endswith("FieldInfo'>") else None

        query = f"{clean_city},{clean_country}" if clean_country else clean_city
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": query,
            "units": str(self.valves.DEFAULT_UNITS),
            "lang": str(self.valves.DEFAULT_LANG),
            "appid": str(self.valves.OPENWEATHER_API_KEY)
        }

        try:
            response = requests.get(url, params=params, timeout=10.0)
            if response.status_code == 404:
                return f"Error: No se encontró la ciudad '{clean_city}' para el pronóstico."
            response.raise_for_status()
            data = response.json()

            city_tz_offset = data.get("city", {}).get("timezone", 0)
            daily_data = defaultdict(list)
            for item in data.get("list", []):
                ts = item.get("dt")
                date_str = self._format_date(ts, city_tz_offset) if ts else item.get("dt_txt", "")[:10]
                if date_str:
                    daily_data[date_str].append(item)

            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            resumen_dias = []

            for date_str, items in list(daily_data.items())[:5]:
                temps = [it.get("main", {}).get("temp") for it in items if it.get("main", {}).get("temp") is not None]
                min_t = min(temps) if temps else "N/D"
                max_t = max(temps) if temps else "N/D"
                climas = [it.get("weather", [{}])[0].get("description", "") for it in items]
                clima_freq = max(set(climas), key=climas.count) if climas else "N/D"
                try:
                    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    dia_nombre = dias_semana[dt_obj.weekday()]
                    header_fecha = f"{dia_nombre} {dt_obj.day}/{dt_obj.month}"
                except Exception:
                    header_fecha = date_str

                resumen_dias.append(f"📅 **{header_fecha} ({date_str})**: Mín: {min_t}°C | Máx: {max_t}°C | Estado: {clima_freq}")

            city_name = data.get("city", {}).get("name", clean_city)
            country = data.get("city", {}).get("country", "")
            return f"Pronóstico meteorológico extendido para {city_name} ({country}):\n\n" + "\n".join(resumen_dias)
        except Exception as e:
            return f"Error al consultar el pronóstico extendido: {str(e)}"
