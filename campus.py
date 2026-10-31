"""校园位置与距离：用于「附近大学优先推荐」。

坐标是示意值（用于演示距离计算），实际部署可换成真实校区。
"""
import math

CAMPUSES = {
    "示范大学": (39.9600, 116.3400),
    "清华大学": (40.0000, 116.3264),
    "北京大学": (39.9928, 116.3055),
    "复旦大学": (31.2989, 121.5036),
    "上海交通大学": (31.2018, 121.4372),
    "浙江大学": (30.2636, 120.0905),
    "中山大学": (23.0965, 113.2980),
}

EARTH_R = 6371.0


def distance_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def nearest_campus(lat, lng):
    """返回 (校区名, 距离 km)。"""
    best = (None, None)
    for name, (clat, clng) in CAMPUSES.items():
        d = distance_km(lat, lng, clat, clng)
        if d is not None and (best[1] is None or d < best[1]):
            best = (name, d)
    return best


def campus_coords(school):
    return CAMPUSES.get(school)


def proximity(lat, lng, school, radius_km=15.0):
    """把距离转成 0–1 的亲近度：同校 1，超过 radius 衰减到 0。"""
    if lat is None or lng is None:
        return 0.0, None
    coords = campus_coords(school)
    if not coords:
        return 0.0, None
    d = distance_km(lat, lng, coords[0], coords[1])
    if d is None:
        return 0.0, None
    return max(0.0, 1.0 - d / radius_km), d
