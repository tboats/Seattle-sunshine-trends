import json
import os
import math
from collections import defaultdict
from datetime import datetime

def load_data(data_dir):
    weather_file = os.path.join(data_dir, 'raw_weather_1950_2026.json')
    oni_file = os.path.join(data_dir, 'raw_oni_1950_2026.json')
    
    if not os.path.exists(weather_file):
        raise FileNotFoundError(f"Weather data not found at {weather_file}")
    if not os.path.exists(oni_file):
        raise FileNotFoundError(f"ONI data not found at {oni_file}")
        
    with open(weather_file, 'r') as f:
        weather_data = json.load(f)
    with open(oni_file, 'r') as f:
        oni_data = json.load(f)
        
    return weather_data, oni_data

# -------------------------------------------------------------
# Statistical Functions: Mann-Kendall & Sen's Slope
# -------------------------------------------------------------

def erf_approx(x):
    # Abramowitz and Stegun approximation for erf
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return sign * y

def normal_cdf(z):
    return 0.5 * (1.0 + erf_approx(z / math.sqrt(2.0)))

def mann_kendall_test(series):
    """
    Computes Mann-Kendall non-parametric monotonic trend test.
    Returns: S, var_S, z, p_value, tau
    """
    n = len(series)
    if n < 4:
        return {'S': 0, 'z': 0.0, 'p_value': 1.0, 'tau': 0.0, 'trend': 'insufficient_data'}
        
    S = 0
    for k in range(n - 1):
        for j in range(k + 1, n):
            diff = series[j] - series[k]
            if diff > 0:
                S += 1
            elif diff < 0:
                S -= 1
                
    # Tie adjustment
    counts = defaultdict(int)
    for x in series:
        counts[x] += 1
    tie_sum = sum(t * (t - 1) * (2 * t + 5) for t in counts.values() if t > 1)
    
    var_S = (n * (n - 1) * (2 * n + 5) - tie_sum) / 18.0
    if var_S <= 0:
        var_S = 1e-6
        
    if S > 0:
        z = (S - 1) / math.sqrt(var_S)
    elif S < 0:
        z = (S + 1) / math.sqrt(var_S)
    else:
        z = 0.0
        
    # Two-sided p-value
    p_value = 2.0 * (1.0 - normal_cdf(abs(z)))
    total_pairs = n * (n - 1) / 2.0
    tau = S / total_pairs if total_pairs else 0.0
    
    trend = "no_trend"
    if p_value < 0.05:
        trend = "increasing" if S > 0 else "decreasing"
        
    return {
        'S': S,
        'var_S': round(var_S, 2),
        'z': round(z, 4),
        'p_value': round(p_value, 5),
        'tau': round(tau, 4),
        'trend': trend,
        'significant_95': p_value < 0.05
    }

def sens_slope(x_series, y_series):
    """Computes Sen's slope (median pairwise slope) and intercept."""
    n = len(y_series)
    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = x_series[j] - x_series[i]
            if dx != 0:
                slopes.append((y_series[j] - y_series[i]) / dx)
                
    if not slopes:
        return 0.0, 0.0
        
    slopes.sort()
    med_slope = slopes[len(slopes) // 2]
    intercepts = [y - med_slope * x for x, y in zip(x_series, y_series)]
    intercepts.sort()
    med_intercept = intercepts[len(intercepts) // 2]
    
    return round(med_slope, 4), round(med_intercept, 2)

def multiple_linear_regression_2var(y, x1, x2):
    """
    Fits y = b0 + b1*x1 + b2*x2 using ordinary least squares.
    Returns: b0, b1, b2, r2
    """
    n = len(y)
    if n < 4:
        return 0, 0, 0, 0
    mean_y = sum(y) / n
    mean_x1 = sum(x1) / n
    mean_x2 = sum(x2) / n
    
    # Center variables
    cy = [val - mean_y for val in y]
    cx1 = [val - mean_x1 for val in x1]
    cx2 = [val - mean_x2 for val in x2]
    
    s_x1x1 = sum(v * v for v in cx1)
    s_x2x2 = sum(v * v for v in cx2)
    s_x1x2 = sum(v1 * v2 for v1, v2 in zip(cx1, cx2))
    s_x1y = sum(v1 * vy for v1, vy in zip(cx1, cy))
    s_x2y = sum(v2 * vy for v2, vy in zip(cx2, cy))
    
    det = (s_x1x1 * s_x2x2) - (s_x1x2 * s_x1x2)
    if abs(det) < 1e-9:
        return round(mean_y, 2), 0, 0, 0
        
    b1 = (s_x2x2 * s_x1y - s_x1x2 * s_x2y) / det
    b2 = (s_x1x1 * s_x2y - s_x1x2 * s_x1y) / det
    b0 = mean_y - b1 * mean_x1 - b2 * mean_x2
    
    ss_tot = sum(v * v for v in cy)
    ss_res = sum((y[i] - (b0 + b1 * x1[i] + b2 * x2[i]))**2 for i in range(n))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return round(b0, 4), round(b1, 4), round(b2, 4), round(r2, 4)

# -------------------------------------------------------------
# Analysis Engine
# -------------------------------------------------------------

def analyze_all(weather_data, oni_data):
    # Organize ONI by year and season
    # Seasons in ONI: DJF, JFM, FMA, MAM, AMJ, MJJ, JJA, JAS, ASO, SON, OND, NDJ
    oni_by_year_seas = {}
    oni_annual_avg = defaultdict(list)
    winter_oni = {} # DJF anomaly for that winter year
    
    for r in oni_data:
        yr = r['year']
        seas = r['season']
        anom = r['sst_anomaly']
        oni_by_year_seas[(yr, seas)] = anom
        oni_annual_avg[yr].append(anom)
        if seas == 'DJF':
            winter_oni[yr] = anom

    # Compute daily attributes
    days_by_year = defaultdict(list)
    days_by_season = defaultdict(lambda: defaultdict(list)) # yr -> season -> list of days
    
    for d in weather_data:
        date_str = d['date']
        yr = int(date_str[:4])
        mo = int(date_str[5:7])
        
        s_dur_s = d.get('sunshine_duration_s') or 0.0
        d_dur_s = d.get('daylight_duration_s') or 36000.0 # fallback 10h
        cloud = d.get('cloud_cover_pct') or 0.0
        rad_mj = d.get('shortwave_radiation_mj') or 0.0
        pr_in = d.get('precip_in') or 0.0
        t_max = d.get('temp_max_f')
        t_min = d.get('temp_min_f')
        t_mean = d.get('temp_mean_f')
        
        sun_hrs = s_dur_s / 3600.0
        daylight_hrs = d_dur_s / 3600.0
        sun_pct = min(100.0, max(0.0, (s_dur_s / d_dur_s * 100.0))) if d_dur_s > 0 else 0.0
        
        # Classification thresholds
        is_clear = (cloud <= 30.0) # NOAA Clear
        is_partly_cloudy = (30.0 < cloud <= 70.0) # NOAA Partly Cloudy
        is_cloudy = (cloud > 70.0) # NOAA Cloudy
        is_sun_break = (sun_hrs >= 1.0) # At least 1h of direct sun
        is_half_sunny = (sun_pct >= 50.0) # Majority of daytime sun
        is_mostly_sunny = (sun_pct >= 70.0) # Heavy sun
        is_glorious = (sun_pct >= 70.0 and pr_in < 0.01) # Blue skies, zero rain
        is_dry = (pr_in < 0.01)
        
        day_obj = {
            'date': date_str,
            'year': yr,
            'month': mo,
            'sun_hrs': round(sun_hrs, 2),
            'daylight_hrs': round(daylight_hrs, 2),
            'sun_pct': round(sun_pct, 1),
            'cloud_pct': round(cloud, 1),
            'rad_mj': round(rad_mj, 2),
            'precip_in': round(pr_in, 3),
            't_max': t_max,
            't_min': t_min,
            't_mean': t_mean,
            'is_clear': is_clear,
            'is_partly_cloudy': is_partly_cloudy,
            'is_cloudy': is_cloudy,
            'is_sun_break': is_sun_break,
            'is_half_sunny': is_half_sunny,
            'is_mostly_sunny': is_mostly_sunny,
            'is_glorious': is_glorious,
            'is_dry': is_dry
        }
        
        days_by_year[yr].append(day_obj)
        
        # Seasonal mapping (meteorological):
        # Winter: Dec(yr-1)-Jan-Feb -> attribute to Jan/Feb's year
        # Spring: Mar, Apr, May (MAM)
        # Summer: Jun, Jul, Aug (JJA)
        # Autumn: Sep, Oct, Nov (SON)
        if mo in (12, 1, 2):
            seas_yr = yr if mo in (1, 2) else yr + 1
            days_by_season[seas_yr]['Winter'].append(day_obj)
        elif mo in (3, 4, 5):
            days_by_season[yr]['Spring'].append(day_obj)
        elif mo in (6, 7, 8):
            days_by_season[yr]['Summer'].append(day_obj)
        elif mo in (9, 10, 11):
            days_by_season[yr]['Autumn'].append(day_obj)

    # -------------------------------------------------------------
    # Annual Summaries (1950 - 2025 full years + 2026 partial)
    # -------------------------------------------------------------
    annual_records = []
    all_years = sorted(days_by_year.keys())
    
    for yr in all_years:
        d_list = days_by_year[yr]
        n_days = len(d_list)
        is_complete = (n_days >= 365)
        
        tot_sun_hrs = sum(d['sun_hrs'] for d in d_list)
        tot_rad_mj = sum(d['rad_mj'] for d in d_list)
        tot_precip_in = sum(d['precip_in'] for d in d_list)
        avg_cloud = sum(d['cloud_pct'] for d in d_list) / n_days if n_days else 0.0
        avg_sun_pct = sum(d['sun_pct'] for d in d_list) / n_days if n_days else 0.0
        
        valid_tmax = [d['t_max'] for d in d_list if d['t_max'] is not None]
        avg_tmax = sum(valid_tmax) / len(valid_tmax) if valid_tmax else None
        
        count_clear = sum(1 for d in d_list if d['is_clear'])
        count_partly = sum(1 for d in d_list if d['is_partly_cloudy'])
        count_cloudy = sum(1 for d in d_list if d['is_cloudy'])
        count_sun_break = sum(1 for d in d_list if d['is_sun_break'])
        count_half_sunny = sum(1 for d in d_list if d['is_half_sunny'])
        count_mostly_sunny = sum(1 for d in d_list if d['is_mostly_sunny'])
        count_glorious = sum(1 for d in d_list if d['is_glorious'])
        count_dry = sum(1 for d in d_list if d['is_dry'])
        
        # ENSO classification
        oni_vals = oni_annual_avg.get(yr, [])
        mean_oni = sum(oni_vals) / len(oni_vals) if oni_vals else 0.0
        djf_anom = winter_oni.get(yr, mean_oni)
        
        # Max peak ONI in the year
        max_oni = max(oni_vals) if oni_vals else 0.0
        min_oni = min(oni_vals) if oni_vals else 0.0
        
        if max_oni >= 2.0 or djf_anom >= 2.0:
            enso_phase = "Super El Niño"
        elif max_oni >= 1.5 or djf_anom >= 1.5:
            enso_phase = "Strong El Niño"
        elif max_oni >= 0.5 or djf_anom >= 0.5:
            enso_phase = "El Niño"
        elif min_oni <= -1.5 or djf_anom <= -1.5:
            enso_phase = "Strong La Niña"
        elif min_oni <= -0.5 or djf_anom <= -0.5:
            enso_phase = "La Niña"
        else:
            enso_phase = "Neutral"

        annual_records.append({
            'year': yr,
            'days_count': n_days,
            'is_complete_year': is_complete,
            'total_sun_hours': round(tot_sun_hrs, 1),
            'avg_sun_hours_per_day': round(tot_sun_hrs / n_days, 2) if n_days else 0.0,
            'avg_sun_pct_daylight': round(avg_sun_pct, 1),
            'avg_cloud_pct': round(avg_cloud, 1),
            'total_rad_gj': round(tot_rad_mj / 1000.0, 2), # GJ/m2
            'total_precip_in': round(tot_precip_in, 2),
            'avg_tmax_f': round(avg_tmax, 1) if avg_tmax else None,
            
            # Category Day Counts
            'clear_days': count_clear,
            'partly_cloudy_days': count_partly,
            'cloudy_days': count_cloudy,
            'any_sun_days': count_clear + count_partly, # Clear + Partly Cloudy
            'sun_break_days': count_sun_break, # >= 1h direct sun
            'half_sunny_days': count_half_sunny, # >= 50% daylight
            'mostly_sunny_days': count_mostly_sunny, # >= 70% daylight
            'glorious_days': count_glorious, # >= 70% sun + dry
            'dry_days': count_dry,
            
            # ENSO
            'oni_annual_avg': round(mean_oni, 2),
            'oni_winter_djf': round(djf_anom, 2),
            'enso_phase': enso_phase
        })

    # Filter complete years (1950 - 2025) for baseline trend statistics
    complete_annuals = [r for r in annual_records if r['is_complete_year']]
    comp_years = [r['year'] for r in complete_annuals]
    
    # -------------------------------------------------------------
    # Trend Analysis on Complete Years (1950 - 2025)
    # -------------------------------------------------------------
    trend_metrics = {
        'total_sun_hours': [r['total_sun_hours'] for r in complete_annuals],
        'clear_days': [r['clear_days'] for r in complete_annuals],
        'any_sun_days': [r['any_sun_days'] for r in complete_annuals],
        'sun_break_days': [r['sun_break_days'] for r in complete_annuals],
        'half_sunny_days': [r['half_sunny_days'] for r in complete_annuals],
        'mostly_sunny_days': [r['mostly_sunny_days'] for r in complete_annuals],
        'glorious_days': [r['glorious_days'] for r in complete_annuals],
        'cloudy_days': [r['cloudy_days'] for r in complete_annuals],
        'dry_days': [r['dry_days'] for r in complete_annuals],
        'total_rad_gj': [r['total_rad_gj'] for r in complete_annuals],
        'avg_cloud_pct': [r['avg_cloud_pct'] for r in complete_annuals]
    }
    
    trend_results = {}
    for metric_name, vals in trend_metrics.items():
        mk = mann_kendall_test(vals)
        slope, intercept = sens_slope(comp_years, vals)
        trend_results[metric_name] = {
            'mann_kendall': mk,
            'sens_slope_per_year': slope,
            'sens_slope_per_decade': round(slope * 10.0, 2),
            'sens_intercept': intercept,
            'start_fitted_1950': round(intercept + slope * 1950, 1),
            'end_fitted_2025': round(intercept + slope * 2025, 1),
            'net_fitted_change_75yr': round(slope * 75, 1)
        }

    # -------------------------------------------------------------
    # Seasonal Trend Analysis
    # -------------------------------------------------------------
    seasonal_records = []
    seasons_list = ['Winter', 'Spring', 'Summer', 'Autumn']
    seasonal_trends = {}
    
    for s_name in seasons_list:
        s_annuals = []
        for yr in sorted(days_by_season.keys()):
            d_list = days_by_season[yr].get(s_name, [])
            if len(d_list) >= 80: # Complete season (~90 days)
                tot_s = sum(d['sun_hrs'] for d in d_list)
                tot_r = sum(d['rad_mj'] for d in d_list)
                clr_d = sum(1 for d in d_list if d['is_clear'])
                prt_d = sum(1 for d in d_list if d['is_partly_cloudy'])
                cld_d = sum(1 for d in d_list if d['is_cloudy'])
                hsun_d = sum(1 for d in d_list if d['is_half_sunny'])
                glor_d = sum(1 for d in d_list if d['is_glorious'])
                dry_d = sum(1 for d in d_list if d['is_dry'])
                cld_pct = sum(d['cloud_pct'] for d in d_list) / len(d_list)
                
                s_annuals.append({
                    'year': yr,
                    'season': s_name,
                    'days_count': len(d_list),
                    'total_sun_hours': round(tot_s, 1),
                    'avg_sun_hours_per_day': round(tot_s / len(d_list), 2),
                    'clear_days': clr_d,
                    'any_sun_days': clr_d + prt_d,
                    'cloudy_days': cld_d,
                    'half_sunny_days': hsun_d,
                    'glorious_days': glor_d,
                    'dry_days': dry_d,
                    'avg_cloud_pct': round(cld_pct, 1),
                    'total_rad_gj': round(tot_r / 1000.0, 2)
                })
        seasonal_records.extend(s_annuals)
        
        # Trend test for this season (sun hours & clear days)
        s_yrs = [r['year'] for r in s_annuals if r['year'] <= 2025]
        s_sun = [r['total_sun_hours'] for r in s_annuals if r['year'] <= 2025]
        s_clr = [r['clear_days'] for r in s_annuals if r['year'] <= 2025]
        
        mk_sun = mann_kendall_test(s_sun)
        slope_sun, _ = sens_slope(s_yrs, s_sun)
        
        mk_clr = mann_kendall_test(s_clr)
        slope_clr, _ = sens_slope(s_yrs, s_clr)
        
        seasonal_trends[s_name] = {
            'sun_hours': {
                'mann_kendall': mk_sun,
                'sens_slope_per_decade': round(slope_sun * 10.0, 2)
            },
            'clear_days': {
                'mann_kendall': mk_clr,
                'sens_slope_per_decade': round(slope_clr * 10.0, 2)
            },
            'historical_mean_sun_hours': round(sum(s_sun) / len(s_sun), 1) if s_sun else 0.0,
            'historical_mean_clear_days': round(sum(s_clr) / len(s_clr), 1) if s_clr else 0.0
        }

    # -------------------------------------------------------------
    # ENSO De-Aliasing & Attribution Regression
    # -------------------------------------------------------------
    # Sun_Hours = b0 + b1*(Year - 1950) + b2*(Winter_ONI)
    y_sun = [r['total_sun_hours'] for r in complete_annuals]
    x_yr = [r['year'] - 1950 for r in complete_annuals]
    x_oni = [r['oni_winter_djf'] for r in complete_annuals]
    
    b0, b_yr, b_oni, r2 = multiple_linear_regression_2var(y_sun, x_yr, x_oni)
    
    # Stratify averages by ENSO phase
    enso_groups = defaultdict(lambda: {'sun_hrs': [], 'clear_days': [], 'any_sun': [], 'precip': []})
    for r in complete_annuals:
        phase = r['enso_phase']
        enso_groups[phase]['sun_hrs'].append(r['total_sun_hours'])
        enso_groups[phase]['clear_days'].append(r['clear_days'])
        enso_groups[phase]['any_sun'].append(r['any_sun_days'])
        enso_groups[phase]['precip'].append(r['total_precip_in'])
        
    enso_stats = {}
    for phase, vals in enso_groups.items():
        enso_stats[phase] = {
            'count': len(vals['sun_hrs']),
            'avg_sun_hours': round(sum(vals['sun_hrs']) / len(vals['sun_hrs']), 1),
            'avg_clear_days': round(sum(vals['clear_days']) / len(vals['clear_days']), 1),
            'avg_any_sun_days': round(sum(vals['any_sun']) / len(vals['any_sun']), 1),
            'avg_precip_in': round(sum(vals['precip']) / len(vals['precip']), 2)
        }

    # -------------------------------------------------------------
    # Decadal Breakdown Table
    # -------------------------------------------------------------
    decades = [
        ("1950s", 1950, 1959),
        ("1960s", 1960, 1969),
        ("1970s", 1970, 1979),
        ("1980s", 1980, 1989),
        ("1990s", 1990, 1999),
        ("2000s", 2000, 2009),
        ("2010s", 2010, 2019),
        ("2020-2025", 2020, 2025)
    ]
    
    decadal_summary = []
    for label, y1, y2 in decades:
        sub = [r for r in complete_annuals if y1 <= r['year'] <= y2]
        if sub:
            n = len(sub)
            decadal_summary.append({
                'decade': label,
                'years_span': f"{y1}-{y2}",
                'years_count': n,
                'avg_sun_hours': round(sum(r['total_sun_hours'] for r in sub) / n, 1),
                'avg_clear_days': round(sum(r['clear_days'] for r in sub) / n, 1),
                'avg_any_sun_days': round(sum(r['any_sun_days'] for r in sub) / n, 1),
                'avg_half_sunny_days': round(sum(r['half_sunny_days'] for r in sub) / n, 1),
                'avg_glorious_days': round(sum(r['glorious_days'] for r in sub) / n, 1),
                'avg_cloudy_days': round(sum(r['cloudy_days'] for r in sub) / n, 1),
                'avg_dry_days': round(sum(r['dry_days'] for r in sub) / n, 1),
                'avg_precip_in': round(sum(r['total_precip_in'] for r in sub) / n, 2),
                'avg_rad_gj': round(sum(r['total_rad_gj'] for r in sub) / n, 2)
            })

    # Year 2026 In-Depth Analysis (Super El Niño year)
    y2026_days = days_by_year.get(2026, [])
    y2026_summary = None
    if y2026_days:
        s2026 = sum(d['sun_hrs'] for d in y2026_days)
        y2026_summary = {
            'year': 2026,
            'days_recorded': len(y2026_days),
            'start_date': y2026_days[0]['date'],
            'end_date': y2026_days[-1]['date'],
            'sun_hours_ytd': round(s2026, 1),
            'clear_days_ytd': sum(1 for d in y2026_days if d['is_clear']),
            'any_sun_days_ytd': sum(1 for d in y2026_days if d['is_clear'] or d['is_partly_cloudy']),
            'precip_in_ytd': round(sum(d['precip_in'] for d in y2026_days), 2),
            'oni_djf': winter_oni.get(2026),
            'oni_latest': oni_by_year_seas.get((2026, 'JJA')),
            'historical_avg_sun_thru_day_of_year': None # To be compared
        }
        
        # Compare 2026 YTD with historical baseline for the exact same calendar days (e.g. Day 1 to Day N)
        same_day_hist = []
        doy_count = len(y2026_days)
        for yr in comp_years:
            sub = days_by_year[yr][:doy_count]
            same_day_hist.append(sum(d['sun_hrs'] for d in sub))
        if same_day_hist:
            base_avg = sum(same_day_hist) / len(same_day_hist)
            y2026_summary['historical_avg_sun_ytd'] = round(base_avg, 1)
            y2026_summary['anomaly_hours_ytd'] = round(s2026 - base_avg, 1)
            y2026_summary['anomaly_pct_ytd'] = round(((s2026 - base_avg) / base_avg) * 100.0, 1)

    payload = {
        'metadata': {
            'location': 'Seattle, WA',
            'latitude': 47.6062,
            'longitude': -122.3321,
            'period': '1950-2026',
            'generated_at': datetime.now().isoformat(),
            'total_days_analyzed': len(weather_data)
        },
        'trends': trend_results,
        'seasonal_trends': seasonal_trends,
        'enso_attribution': {
            'regression': {
                'formula': 'Total_Sun_Hours = b0 + b1*(Year - 1950) + b2*(Winter_ONI)',
                'b0_baseline_1950': b0,
                'b1_secular_slope_hrs_per_yr': b_yr,
                'b1_secular_slope_hrs_per_decade': round(b_yr * 10.0, 2),
                'b2_enso_sensitivity_hrs_per_degC': b_oni,
                'r2': r2,
                'interpretation': (
                    f"Holding ENSO constant, Seattle's secular climate warming trend adds ~{round(b_yr * 10.0, 1)} "
                    f"hours of sunshine per decade. Each +1.0°C winter El Niño anomaly contributes ~{round(b_oni, 1)} "
                    f"additional sunshine hours to the year."
                )
            },
            'stats_by_phase': enso_stats
        },
        'decadal_summary': decadal_summary,
        'annual_records': annual_records,
        'seasonal_records': seasonal_records,
        'year_2026_analysis': y2026_summary
    }

    return payload

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    data_dir = os.path.join(project_root, 'data')
    
    print("Loading data...")
    weather_data, oni_data = load_data(data_dir)
    print(f"Loaded {len(weather_data)} weather records and {len(oni_data)} ONI records.")
    
    print("Running statistical trend tests and ENSO de-aliasing...")
    payload = analyze_all(weather_data, oni_data)
    
    json_path = os.path.join(data_dir, 'sunshine_trends.json')
    js_path = os.path.join(project_root, 'sunshine_trends.js')
    public_js_path = os.path.join(project_root, 'public', 'sunshine_trends.js')
    
    os.makedirs(os.path.dirname(public_js_path), exist_ok=True)
    
    with open(json_path, 'w') as f:
        json.dump(payload, f, indent=2)
    with open(js_path, 'w') as f:
        f.write(f"window.SEATTLE_SUNSHINE_TRENDS = {json.dumps(payload, indent=2)};")
    with open(public_js_path, 'w') as f:
        f.write(f"window.SEATTLE_SUNSHINE_TRENDS = {json.dumps(payload, indent=2)};")
        
    print(f"Analysis successfully written to:")
    print(f"  - {json_path}")
    print(f"  - {js_path}")
    print(f"  - {public_js_path}")
    
    print("\n--- KEY STATISTICAL RESULTS ---")
    tr = payload['trends']
    print(f"Annual Sun Hours Sen's Slope: {tr['total_sun_hours']['sens_slope_per_decade']} hrs/decade (p={tr['total_sun_hours']['mann_kendall']['p_value']}, {tr['total_sun_hours']['mann_kendall']['trend']})")
    print(f"Clear Days Sen's Slope: {tr['clear_days']['sens_slope_per_decade']} days/decade (p={tr['clear_days']['mann_kendall']['p_value']}, {tr['clear_days']['mann_kendall']['trend']})")
    print(f"Any Sun Days Sen's Slope: {tr['any_sun_days']['sens_slope_per_decade']} days/decade (p={tr['any_sun_days']['mann_kendall']['p_value']}, {tr['any_sun_days']['mann_kendall']['trend']})")
    print(f"Cloudy Days Sen's Slope: {tr['cloudy_days']['sens_slope_per_decade']} days/decade (p={tr['cloudy_days']['mann_kendall']['p_value']}, {tr['cloudy_days']['mann_kendall']['trend']})")
    print(f"ENSO Attribution: {payload['enso_attribution']['regression']['interpretation']}")

if __name__ == '__main__':
    main()
