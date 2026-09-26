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
    Updates cache if new data is available, with graceful fallback to cached version.
    """
    cached_file = os.path.join(data_dir, 'raw_oni_1950_2026.json')
    url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SeattleWeatherAnalysis/1.0)'})
    
    records = []
    try:
        print("Checking NOAA CPC Oceanic Niño Index (1950-2026)...")
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
        print(f"Successfully loaded {len(records)} ONI seasonal records from NOAA.")
        with open(cached_file, 'w') as f:
            json.dump(records, f, indent=2)
        return records
    except Exception as e:
        print(f"Warning: Failed to fetch live ONI from NOAA ({e}). Checking local cache...")
        if os.path.exists(cached_file):
            with open(cached_file, 'r') as f:
                records = json.load(f)
            print(f"Loaded {len(records)} ONI records from local cache.")
            return records
        raise

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

def fetch_recent_forecast(lat, lon, past_days=14):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=sunshine_duration,daylight_duration,shortwave_radiation_sum,cloud_cover_mean,precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean&"
        f"past_days={past_days}&forecast_days=1&"
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
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Fast Incremental Path: If we already have the full multi-decadal archive cached
    if os.path.exists(cached_file):
        print("Existing multi-decadal raw weather dataset detected. Running fast daily incremental update...")
        with open(cached_file, 'r') as f:
            observations = json.load(f)
            
        obs_map = {o['date']: o for o in observations}
        last_date = observations[-1]['date'] if observations else "1950-01-01"
        print(f"  Last recorded date in cache: {last_date}")

        # Fetch recent observations (last 14 days up to today)
        try:
            print("  Fetching latest observations from Open-Meteo API...")
            recent_data = fetch_recent_forecast(lat, lon, past_days=14)
            r_daily = recent_data.get('daily', {})
            t_list = r_daily.get('time', [])
            
            updated_count = 0
            new_count = 0
            for i, t in enumerate(t_list):
                new_entry = {
                    'date': t,
                    'sunshine_duration_s': r_daily.get('sunshine_duration', [None])[i],
                    'daylight_duration_s': r_daily.get('daylight_duration', [None])[i],
                    'shortwave_radiation_mj': r_daily.get('shortwave_radiation_sum', [None])[i],
                    'cloud_cover_pct': r_daily.get('cloud_cover_mean', [None])[i],
                    'precip_in': r_daily.get('precipitation_sum', [None])[i],
                    'temp_max_f': r_daily.get('temperature_2m_max', [None])[i],
                    'temp_min_f': r_daily.get('temperature_2m_min', [None])[i],
                    'temp_mean_f': r_daily.get('temperature_2m_mean', [None])[i]
                }
                if t in obs_map:
                    obs_map[t] = new_entry
                    updated_count += 1
                else:
                    obs_map[t] = new_entry
                    new_count += 1
            print(f"  Successfully updated {updated_count} recent days and added {new_count} new days.")
            
            # Recompile sorted observations list
            sorted_dates = sorted(obs_map.keys())
            updated_observations = [obs_map[d] for d in sorted_dates]
            
            with open(cached_file, 'w') as f:
                json.dump(updated_observations, f)
            print(f"  Saved updated dataset: {len(updated_observations)} total days ({updated_observations[0]['date']} to {updated_observations[-1]['date']})")
            return updated_observations
        except Exception as e:
            print(f"  Warning during incremental update ({e}). Returning existing cached observations.")
            return observations

    # Full Historical Path (Initial Setup Only)
    chunks = [
        ("1950-01-01", "1959-12-31"),
        ("1960-01-01", "1969-12-31"),
        ("1970-01-01", "1979-12-31"),
        ("1980-01-01", "1989-12-31"),
        ("1990-01-01", "1999-12-31"),
        ("2000-01-01", "2009-12-31"),
        ("2010-01-01", "2019-12-31"),
        ("2020-01-01", today_str)
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

    print("Fetching Open-Meteo ERA5 Reanalysis data (1950 to present)...")
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
            time.sleep(2.5)

        daily = chunk_data.get('daily', {})
        t_list = daily.get('time', [])
        daily_combined['time'].extend(t_list)
        for f in fields:
            daily_combined[f].extend(daily.get(f, []))

    # Merge recent days from Forecast API
    try:
        recent_data = fetch_recent_forecast(lat, lon, past_days=14)
        r_daily = recent_data.get('daily', {})
        existing_times = set(daily_combined['time'])
        for i, t in enumerate(r_daily.get('time', [])):
            if t not in existing_times:
                daily_combined['time'].append(t)
                for f in fields:
                    vals = r_daily.get(f, [])
                    daily_combined[f].append(vals[i] if i < len(vals) else None)
            else:
                idx = daily_combined['time'].index(t)
                for f in fields:
                    vals = r_daily.get(f, [])
                    if i < len(vals) and vals[i] is not None:
                        daily_combined[f][idx] = vals[i]
    except Exception as e:
        print(f"  Warning: could not fetch recent forecast days: {e}")

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
