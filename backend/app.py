from flask import Flask, request, jsonify, render_template
import pandas as pd
import numpy as np
from pathlib import Path
import re
import time
import logging
import os
from flask_caching import Cache
from flask_compress import Compress
from collections import defaultdict
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, unset_jwt_cookies
)
import datetime

app = Flask(__name__)
app.config['CACHE_TYPE'] = 'FileSystemCache'
app.config['CACHE_DIR'] = '/tmp/flask_cache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 0
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(hours=1)
cache = Cache(app)
Compress(app)

db = SQLAlchemy(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

def get_csv_path(symbol, interval, yyyymmdd: str, source: str) -> str:
    path = f"/data/{source}/{yyyymmdd[:4]}/{yyyymmdd}/{symbol}_{yyyymmdd}_{interval}.csv"
    if os.path.exists(path):
        return path
    return f"/data/index_{source}/{yyyymmdd[:4]}/{yyyymmdd}/{symbol}_{yyyymmdd}_{interval}.csv"

def load_single_day(symbol, interval, yyyymmdd: str, source: str, field: str) -> pd.DataFrame:
    path = get_csv_path(symbol, interval, yyyymmdd, source) 
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=['time'], index_col='time', usecols=["time", field])

def get_file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return -1

def load_cached_field(symbol, interval, date: str, field: str, source: str) -> pd.DataFrame:
    key = f"{symbol}:{interval}:{date}:{field}:{source}"
    path = get_csv_path(symbol, interval, date, source)
    current_mtime = get_file_mtime(path)

    cached_bundle = cache.get(key)
    if cached_bundle:
        cached_df, cached_mtime = cached_bundle
        if cached_mtime == current_mtime:
            return cached_df  # ✅ 缓存有效，直接用

    # 缓存无效或不存在，重新加载
    base_field = field
    if field.endswith('_pct_change'):
        base_field = field[:-11]
    df = load_single_day(symbol, interval, date, source, base_field)
    if df.empty:
        return pd.DataFrame()

    if field.endswith('_pct_change'):
        base_field = field[:-11]
        if base_field not in df.columns:
            return pd.DataFrame()
        s = df[base_field].pct_change().fillna(0)
    else:
        if field not in df.columns:
            return pd.DataFrame()
        s = df[field]

    result = pd.DataFrame({field: s})
    result.index.name = 'time'

    # ❗️更新缓存，包含 DataFrame 和当前文件 mtime
    cache.set(key, (result, current_mtime), timeout=3600 * 24)
    return result

CSV_PATTERN = re.compile(r'^([A-Z\.]+[A-Z\d]*)_(\d{8})_(\w+).csv$')

running_dir = Path("/data/running")
history_dir = Path("/data/history")

@app.route('/api/get-options')
def get_options():
    symbols, intervals, fields = set([
        'N225.OSE.JPN',
        'SPX.CBOE',
        'NDX.NASDAQ',
        'RUT.RUSSELL',
        'MID.PSE',
        'DJI.CME',
        ]), set(), set()
    base = running_dir / '2025/20250715'
    for f in base.rglob("*.csv"):
        m = CSV_PATTERN.match(f.name)
        if m:
            symbols.add(m.group(1))
            intervals.add(m.group(3))
            if not fields:
                try:
                    df = pd.read_csv(f, nrows=5)
                    fields.update(df.columns.drop("time", errors='ignore'))
                except Exception as e:
                    app.logger.warning(f"Failed to read fields from {f}: {e}")

    fields = [field for field in sorted(fields) if field not in ['id', 'interval', 'type']]
    fields += [f'{field}_pct_change' for field in fields if field not in ['adjustment']]
    return jsonify({
        "symbols": sorted(symbols),
        "intervals": sorted(intervals),
        "fields": fields
    })

@app.route('/api/get-plot', methods=['POST'])
def get_plot():
    data = request.json
    symbol = data['symbol']
    interval = data['interval']
    fields = data['fields']
    start_date = int(data['start'])
    end_date = int(data['end'])
    app.logger.info(f"Plot request: {symbol} {interval} {fields} {start_date}~{end_date}")
    t0 = time.perf_counter()

    # 日期范围
    date_range = pd.date_range(
        pd.to_datetime(str(start_date), format="%Y%m%d"),
        pd.to_datetime(str(end_date), format="%Y%m%d"),
        freq='D'
    )
    date_strs = [d.strftime('%Y%m%d') for d in date_range]

    df_hist_daily = defaultdict(list)
    df_run_daily = defaultdict(list)

    for date in date_strs:
        for field in fields:
            for src in ['history', 'running']:
                df_part = load_cached_field(symbol, interval, date, field, src)
                if df_part.empty:
                    continue
                if src == 'history':
                    df_hist_daily[date].append(df_part)
                else:
                    df_run_daily[date].append(df_part)

    df_hist = pd.concat([
        pd.concat(df_list, axis=1)  # 横向拼接：同一天不同字段
        for df_list in df_hist_daily.values() if df_list
    ], axis=0).sort_index() if any(df_hist_daily.values()) else pd.DataFrame() 

    df_run = pd.concat([
        pd.concat(df_list, axis=1)
        for df_list in df_run_daily.values() if df_list
    ], axis=0).sort_index() if any(df_run_daily.values()) else pd.DataFrame()

    df_diff = df_run[fields] - df_hist[fields] if not df_run.empty and not df_hist.empty else pd.DataFrame()

    # 统计
    stats = {}
    def clean_stats(d: dict) -> dict:
        return {
            k: (
                0 if pd.isna(v) or np.isinf(v)
                else float(v)
            )
            for k, v in d.items()
        }
    for name, df in zip(['history', 'running', 'diff'], [df_hist, df_run, df_diff]):
        if not df.empty:
            stats[name] = {
                'mean': clean_stats(df[fields].mean().to_dict()),
                'std': clean_stats(df[fields].std().to_dict()),
                'max': clean_stats(df[fields].max().to_dict()),
                'min': clean_stats(df[fields].min().to_dict()),
                'count': clean_stats(df[fields].count().to_dict())
            }

    # 相关性
    if not df_run.empty and not df_hist.empty:
        corr_dict = {}
        for field in fields:
            if df_run[field].std() == 0 or df_hist[field].std() == 0:
                corr_dict[field] = 0
            else:
                corr_dict[field] = df_run[field].corr(df_hist[field])
        stats['corr'] = clean_stats(corr_dict)

    # 时间戳统一
    timestamps = pd.to_datetime(df_run.index.union(df_hist.index).union(df_diff.index).drop_duplicates().sort_values())
    timestamps_str = timestamps.strftime("%Y-%m-%d %H:%M:%S").tolist()

    # 折线图数据
    series = []
    for i, (df, prefix) in enumerate(zip([df_hist, df_run, df_diff], ['history', 'running', 'diff'])):
        if not df.empty:
            df = df.loc[~df.index.duplicated()].sort_index()
            for field in fields:
                tmp_values = df.reindex(timestamps)[field].ffill().fillna(0)
                tmp_values = tmp_values.where(np.isfinite(tmp_values))
                tmp_values = tmp_values.ffill()
                values = tmp_values.tolist()
                series.append({
                    "label": f"{prefix}_{field}",
                    "values": values,
                })

    return jsonify({
        "timestamps": timestamps_str,
        "series": series,
        "stats": stats,
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Missing credentials"}), 400

    user = User.query.filter_by(username=username, password=password).first()
    if user:
        token = create_access_token(identity=username)
        return jsonify({"success": True, "token": token})
    else:
        return jsonify({"success": False, "message": "Invalid username or password"}), 401


# === 登出接口 ===
@app.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    response = jsonify({"success": True, "message": "Logged out"})
    unset_jwt_cookies(response)  # 从服务端让 JWT cookie 失效（如果前端存 header token，可以让前端自行清除）
    return response


# === 获取用户信息 ===
@app.route('/api/getInfo', methods=['GET'])
@jwt_required()
def get_info():
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    return jsonify({
        "success": True,
        "user": {
            "username": user.username,
            "roles": ["admin"] if user.username == "admin" else ["user"],
            "introduction": f"I am {user.username}"
        }
    })

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--running', type=str, default='/data/running')
    parser.add_argument('--history', type=str, default='/data/history')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--log-level', type=str, default='INFO')
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    app.logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    running_dir = Path(args.running)
    history_dir = Path(args.history)

    app.run(host='0.0.0.0', port=args.port, debug=True, use_reloader=True, threaded=True)
