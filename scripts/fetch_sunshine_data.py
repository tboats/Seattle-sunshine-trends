import urllib.request
import urllib.error
import json
import os
import sys
import time
from datetime import datetime, timedelta

def fetch_noaa_oni(data_dir):
    """
    Fetches the Oceanic Niño Index (ONI) from NOAA Climate Prediction Center (CPC).
    """
    cached_file = os.path.join(data_dir, 'raw_oni_1950_2026.json')
    if os.path.exists(cached_file):
        print("Using cached NOAA ONI data.")
        with open(cached_file, 'r') as f:
            return json.load(f)

    print("Fetching NOAA CPC Oceanic Niño Index (1950-2026)...")
    url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SeattleWeatherAnalysis/1.0)'})
    
    records = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            lines = resp.read().decode('utf-8').strip().splitlines()
        
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) >= 4:
                records.append({
                    'season': parts[0],
                    'year': int(parts[1]),
                    'sst_total': float(parts[2]),
                    'sst_anomaly': float(parts[3])
                })
        print(f"Successfully loaded {len(records)} ONI seasonal records.")
        with open(cached_file, 'w') as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to fetch online ONI data ({e}).")
        raise
    return records

def fetch_open_meteo_chunk_with_retry(lat, lon, start_date, end_date, max_retries=5):
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&"
        f"start_date={start_date}&end_date={end_date}&"
        f"daily=sunshine_duration,daylight_duration,shortwave_radiation_sum,cloud_cover_mean,precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean&"
        f"temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SeattleWeatherAnalysis/1.0)'})
    
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_sec = 6 * attempt
                print(f"    [HTTP 429 Rate Limit] Waiting {wait_sec}s before retry {attempt}/{max_retries}...")
                time.sleep(wait_sec)
            else:
                print(f"    [HTTP {e.code}] {e.reason}")
                if attempt == max_retries:
                    raise
                time.sleep(3)
        except Exception as e:
            print(f"    [Network Error] {e}. Retrying in 4s...")
            time.sleep(4)
            if attempt == max_retries:
                raise
    raise RuntimeError(f"Failed to fetch chunk {start_date} to {end_date} after {max_retries} attempts.")

def fetch_recent_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=sunshine_duration,daylight_duration,shortwave_radiation_sum,cloud_cover_mean,precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean&"
        f"past_days=14&forecast_days=1&"
        f"temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SeattleWeatherAnalysis/1.0)'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

def fetch_all_weather_data(data_dir):
    lat, lon = 47.6062, -122.3321
    chunks_dir = os.path.join(data_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)
    cached_file = os.path.join(data_dir, 'raw_weather_1950_2026.json')
    
    chunks = [
        ("1950-01-01", "1959-12-31"),
        ("1960-01-01", "1969-12-31"),
        ("1970-01-01", "1979-12-31"),
        ("1980-01-01", "1989-12-31"),
        ("1990-01-01", "1999-12-31"),
        ("2000-01-01", "2009-12-31"),
        ("2010-01-01", "2019-12-31"),
        ("2020-01-01", datetime.now().strftime("%Y-%m-%d"))
    ]
    
    daily_combined = {
        'time': [],
        'sunshine_duration': [],
        'daylight_duration': [],
        'shortwave_radiation_sum': [],
        'cloud_cover_mean': [],
        'precipitation_sum': [],
        'temperature_2m_max': [],
        'temperature_2m_min': [],
        'temperature_2m_mean': []
    }
    
    fields = [
        'sunshine_duration', 'daylight_duration', 'shortwave_radiation_sum',
        'cloud_cover_mean', 'precipitation_sum', 'temperature_2m_max',
        'temperature_2m_min', 'temperature_2m_mean'
    ]

    print("Fetching Open-Meteo ERA5 Reanalysis data (1950 to 2026)...")
    for start_d, end_d in chunks:
        chunk_filename = f"chunk_{start_d[:4]}_{end_d[:4]}.json"
        chunk_file_path = os.path.join(chunks_dir, chunk_filename)
        
        if os.path.exists(chunk_file_path):
            print(f"  [Cached] Reading chunk {start_d} to {end_d} from {chunk_filename}...")
            with open(chunk_file_path, 'r') as f:
                chunk_data = json.load(f)
        else:
            print(f"  Fetching chunk {start_d} to {end_d} from API...")
            chunk_data = fetch_open_meteo_chunk_with_retry(lat, lon, start_d, end_d)
            with open(chunk_file_path, 'w') as f:
                json.dump(chunk_data, f)
            print(f"    Saved {chunk_filename}.")
            time.sleep(2.5) # Polite gap between archive calls

        daily = chunk_data.get('daily', {})
        t_list = daily.get('time', [])
        daily_combined['time'].extend(t_list)
        for f in fields:
            daily_combined[f].extend(daily.get(f, []))

    # Merge recent days from Forecast API if needed
    try:
        print("  Checking real-time forecast API for the latest days...")
        recent_data = fetch_recent_forecast(lat, lon)
        r_daily = recent_data.get('daily', {})
        existing_times = set(daily_combined['time'])
        added_count = 0
        for i, t in enumerate(r_daily.get('time', [])):
            if t not in existing_times:
                daily_combined['time'].append(t)
                for f in fields:
                    vals = r_daily.get(f, [])
                    daily_combined[f].append(vals[i] if i < len(vals) else None)
                added_count += 1
            else:
                idx = daily_combined['time'].index(t)
                for f in fields:
                    vals = r_daily.get(f, [])
                    if i < len(vals) and vals[i] is not None:
                        daily_combined[f][idx] = vals[i]
        print(f"  Merged {added_count} additional recent days up to today.")
    except Exception as e:
        print(f"  Warning: could not fetch recent forecast days: {e}")

    # Build list of daily dictionaries
    total_days = len(daily_combined['time'])
    observations = []
    for i in range(total_days):
        observations.append({
            'date': daily_combined['time'][i],
            'sunshine_duration_s': daily_combined['sunshine_duration'][i],
            'daylight_duration_s': daily_combined['daylight_duration'][i],
            'shortwave_radiation_mj': daily_combined['shortwave_radiation_sum'][i],
            'cloud_cover_pct': daily_combined['cloud_cover_mean'][i],
            'precip_in': daily_combined['precipitation_sum'][i],
            'temp_max_f': daily_combined['temperature_2m_max'][i],
            'temp_min_f': daily_combined['temperature_2m_min'][i],
            'temp_mean_f': daily_combined['temperature_2m_mean'][i]
        })

    print(f"Total days compiled: {len(observations)} ({observations[0]['date']} to {observations[-1]['date']})")
    
    with open(cached_file, 'w') as f:
        json.dump(observations, f)
    print(f"Cached raw weather data to {cached_file}")
    return observations

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    fetch_noaa_oni(data_dir)
    fetch_all_weather_data(data_dir)
    print("\nData acquisition complete!")

if __name__ == '__main__':
    main()
