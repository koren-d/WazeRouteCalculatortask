# -*- coding: utf-8 -*-
"""Waze route calculator"""

import logging
import requests
import re
from datetime import datetime, timedelta
import json
import pytz

class WRCError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WazeRouteCalculator(object):
    """Calculate actual route time and distance with Waze API"""
    
    
    
    
    DICT_FILE = "waze_dict.json"  

    @classmethod
    def load_dict(cls):
        try:
            with open(cls.DICT_FILE, "r") as f:
                cls.dict = json.load(f)
            # print(f"[DICT LOADED] Loaded cache from {cls.DICT_FILE}.")
        except FileNotFoundError:
            # print(f"[DICT] No dict file found. Starting with an empty dict.")
            cls.dict = {}
        except json.JSONDecodeError:
            # print(f"[DICT ERROR] Could not decode dict file. Starting with an empty dict.")
            cls.dict = {}

    @classmethod
    def save_dict(cls):
        try:
            with open(cls.DICT_FILE, "w") as f:
                json.dump(cls.dict, f)
            # print(f"[DICT SAVED] dict saved to {cls.DICT_FILE}.")
        except Exception as e:
            pass
            # print(f"[DICT ERROR] Could not save dict: {e}")

    
    dict = {}  # Static attribute for caching
    WAZE_URL = "https://www.waze.com/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0",
        "referer": WAZE_URL,
    }
    VEHICLE_TYPES = ('TAXI', 'MOTORCYCLE')
    BASE_COORDS = {
        'US': {"lat": 40.713, "lon": -74.006},
        'EU': {"lat": 47.498, "lon": 19.040},
        'IL': {"lat": 31.768, "lon": 35.214},
        'AU': {"lat": -35.281, "lon": 149.128}
    }
    COORD_SERVERS = {
        'US': 'SearchServer/mozi',
        'EU': 'row-SearchServer/mozi',
        'IL': 'il-SearchServer/mozi',
        'AU': 'row-SearchServer/mozi'
    }
    ROUTING_SERVERS = {
        'US': 'RoutingManager/routingRequest',
        'EU': 'row-RoutingManager/routingRequest',
        'IL': 'il-RoutingManager/routingRequest',
        'AU': 'row-RoutingManager/routingRequest'
    }
    COORD_MATCH = re.compile(r'^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$')

    def __init__(self, start_address, end_address, region='EU', vehicle_type='', avoid_toll_roads=False, avoid_subscription_roads=False, avoid_ferries=False, log_lvl=None):
        # מאפיין לשמירת לוגים
        self.travel_logs = {}

        # וודא שהמטמון קיים ברמת המחלקה
        if not hasattr(WazeRouteCalculator, 'dict'):
            WazeRouteCalculator.dict = {}

        self.log = logging.getLogger(__name__)
        self.log.addHandler(logging.NullHandler())
        if log_lvl:
            self.log.warning("log_lvl is deprecated please check example.py ")
        self.log.info("From: %s - to: %s", start_address, end_address)
        region = region.upper()
        if region == 'NA':  # North America
            region = 'US'
        self.region = region
        self.vehicle_type = ''
        if vehicle_type and vehicle_type in self.VEHICLE_TYPES:
            self.vehicle_type = vehicle_type.upper()
        self.ROUTE_OPTIONS = {
            'AVOID_TRAILS': 't',
            'AVOID_TOLL_ROADS': 't' if avoid_toll_roads else 'f',
            'AVOID_FERRIES': 't' if avoid_ferries else 'f'
        }
        self.avoid_subscription_roads = avoid_subscription_roads
        if self.already_coords(start_address):  # See if we have coordinates or address to resolve
            self.start_coords = self.coords_string_parser(start_address)
        else:
            self.start_coords = self.address_to_coords(start_address)
        self.log.debug('Start coords: (%s, %s)', self.start_coords["lat"], self.start_coords["lon"])
        if self.already_coords(end_address):  # See if we have coordinates or address to resolve
            self.end_coords = self.coords_string_parser(end_address)
        else:
            self.end_coords = self.address_to_coords(end_address)
        self.log.debug('End coords: (%s, %s)', self.end_coords["lat"], self.end_coords["lon"])

    def already_coords(self, address):
        """test used to see if we have coordinates or address"""

        m = re.search(self.COORD_MATCH, address)
        return (m is not None)

    def coords_string_parser(self, coords):
        """Pareses the address string into coordinates to match address_to_coords return object"""

        lat, lon = coords.split(',')
        return {"lat": lat.strip(), "lon": lon.strip(), "bounds": {}}

    def address_to_coords(self, address):
        """Convert address to coordinates"""

        base_coords = self.BASE_COORDS[self.region]
        get_cord = self.COORD_SERVERS[self.region]
        url_options = {
            "q": address,
            "lang": "eng",
            "origin": "livemap",
            "lat": base_coords["lat"],
            "lon": base_coords["lon"]
        }

        response = requests.get(self.WAZE_URL + get_cord, params=url_options, headers=self.HEADERS)
        for response_json in response.json():
            if response_json.get('city'):
                lat = response_json['location']['lat']
                lon = response_json['location']['lon']
                bounds = response_json['bounds']  # sometimes the coords don't match up
                if bounds is not None:
                    bounds['top'], bounds['bottom'] = max(bounds['top'], bounds['bottom']), min(bounds['top'], bounds['bottom'])
                    bounds['left'], bounds['right'] = min(bounds['left'], bounds['right']), max(bounds['left'], bounds['right'])
                else:
                    bounds = {}
                return {"lat": lat, "lon": lon, "bounds": bounds}
        raise WRCError("Cannot get coords for %s" % address)

    def get_route(self, npaths=1, time_delta=0):
        """Get route data from waze"""

        routing_server = self.ROUTING_SERVERS[self.region]

        url_options = {
            "from": "x:%s y:%s" % (self.start_coords["lon"], self.start_coords["lat"]),
            "to": "x:%s y:%s" % (self.end_coords["lon"], self.end_coords["lat"]),
            "at": time_delta,
            "returnJSON": "true",
            "returnGeometries": "true",
            "returnInstructions": "true",
            "timeout": 60000,
            "nPaths": npaths,
            "options": ','.join('%s:%s' % (opt, value) for (opt, value) in self.ROUTE_OPTIONS.items()),
        }
        if self.vehicle_type:
            url_options["vehicleType"] = self.vehicle_type
        # Handle vignette system in Europe. Defaults to false (show all routes)
        if self.avoid_subscription_roads is False:
            url_options["subscription"] = "*"

        response = requests.get(self.WAZE_URL + routing_server, params=url_options, headers=self.HEADERS)
        response.encoding = 'utf-8'
        response_json = self._check_response(response)
        if response_json:
            if 'error' in response_json:
                raise WRCError(response_json.get("error"))
            else:
                if response_json.get("alternatives"):
                    return [alt['response'] for alt in response_json['alternatives']]
                response_obj = response_json['response']
                if isinstance(response_obj, list):
                    response_obj = response_obj[0]
                if npaths > 1:
                    return [response_obj]
                return response_obj
        else:
            raise WRCError("empty response")

    @staticmethod
    def _check_response(response):
        """Check waze server response."""
        if response.ok:
            try:
                return response.json()
            except ValueError:
                return None

    def _add_up_route(self, results, real_time=True, stop_at_bounds=False):
        """Calculate route time and distance."""

        start_bounds = self.start_coords['bounds']
        end_bounds = self.end_coords['bounds']

        def between(target, min, max):
            return target > min and target < max

        time = 0
        distance = 0
        for segment in results:
            if stop_at_bounds and segment.get('path'):
                x = segment['path']['x']
                y = segment['path']['y']
                if (
                    between(x, start_bounds.get('left', 0), start_bounds.get('right', 0)) or
                    between(x, end_bounds.get('left', 0), end_bounds.get('right', 0))
                ) and (
                    between(y, start_bounds.get('bottom', 0), start_bounds.get('top', 0)) or
                    between(y, end_bounds.get('bottom', 0), end_bounds.get('top', 0))
                ):
                    continue
            if 'crossTime' in segment:
                time += segment['crossTime' if real_time else 'crossTimeWithoutRealTime']
            else:
                time += segment['cross_time' if real_time else 'cross_time_without_real_time']
            distance += segment['length']
        route_time = time / 60.0
        route_distance = distance / 1000.0
        return route_time, route_distance

    def calc_route_info(self, real_time=True, stop_at_bounds=False, time_delta=0):
        """Calculate best route info."""

        route = self.get_route(1, time_delta)
        results = route['results' if 'results' in route else 'result']
        route_time, route_distance = self._add_up_route(results, real_time=real_time, stop_at_bounds=stop_at_bounds)
        self.log.info('Time %.2f minutes, distance %.2f km.', route_time, route_distance)
        return route_time, route_distance

    def calc_all_routes_info(self, npaths=3, real_time=True, stop_at_bounds=False, time_delta=0):
        """Calculate all route infos."""

        routes = self.get_route(npaths, time_delta)
        try:
            results = {"%s-%s" % (''.join(route.get('routeType', [])[:1]), route.get('shortRouteName', 'unkown')): self._add_up_route(route['results' if 'results' in route else 'result'], real_time=real_time, stop_at_bounds=stop_at_bounds) for route in routes}
        except KeyError:
            raise WRCError("wrong response")
        route_time = [route[0] for route in results.values()]
        route_distance = [route[1] for route in results.values()]
        self.log.info('Min\tMax\n%.2f\t%.2f minutes\n%.2f\t%.2f km', min(route_time), max(route_time), min(route_distance), max(route_distance))
        return results
    ######### 


    def get_dict_route_time(self, start, end, desired_arrival_time=None):
        if not hasattr(WazeRouteCalculator, 'dict'):
            WazeRouteCalculator.dict = {}
        start, end = start.lower(), end.lower()

        now = datetime.now(pytz.timezone("Asia/Jerusalem"))
        desired_time = datetime.strptime(desired_arrival_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone("Asia/Jerusalem")) if desired_arrival_time else now

        for existing_key, dict_entry in WazeRouteCalculator.dict.items():
            if existing_key.lower().startswith(f"{start} -> {end}"):
                exec_time_str = existing_key.split('@')[1].strip()
                exec_time = datetime.strptime(exec_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone("Asia/Jerusalem"))

                days_difference = abs((desired_time.date() - exec_time.date()).days)
                if days_difference > 14:
                    continue

                exec_hour, desired_hour = exec_time.hour, desired_time.hour
                time_difference_hours = abs(exec_hour - desired_hour)
                if time_difference_hours > 1:  
                    continue

                print(f"stage: {start} -> {end} from dict")
                return dict_entry['travel_time_minutes']

        print(f"stage: {start} -> {end} from waze server")
        route_time, _ = WazeRouteCalculator(start, end, region=self.region).calc_route_info()

        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        key = f"{start} -> {end} @ {now_str}"
        WazeRouteCalculator.dict[key] = {"travel_time_minutes": route_time, "timestamp": now_str}
        WazeRouteCalculator.save_dict()
        return route_time




    def calculate_total_trip_time_with_logs(self, locations, breaks=None, desired_arrival_time=None):
        if len(locations) < 2:
            raise ValueError("You must provide at least two locations")

        if breaks is None:
            breaks = [0] * (len(locations) - 1)
        elif len(breaks) < len(locations) - 1:
            breaks += [0] * (len(locations) - 1 - len(breaks))

        total_trip_time = 0
        # travel_logs = {}

        for i in range(len(locations) - 1):
            start, end = locations[i], locations[i + 1]
            route_time = self.get_dict_route_time(start, end, desired_arrival_time)
            
            desired_arrival_datetime = datetime.strptime(desired_arrival_time, "%Y-%m-%d %H:%M:%S")
            current_departure_time = desired_arrival_datetime - timedelta(minutes=total_trip_time + route_time) 


            if 7 <= current_departure_time.hour < 10 or 16 <= current_departure_time.hour < 18:  
                route_time += 30  
            total_trip_time += route_time + breaks[i]

        desired_arrival_datetime = datetime.strptime(desired_arrival_time, "%Y-%m-%d %H:%M:%S")
        recommended_departure_time = desired_arrival_datetime - timedelta(minutes=total_trip_time)

        return {
            "total_trip_time_minutes": total_trip_time,
            "recommended_departure_time": recommended_departure_time.strftime("%Y-%m-%d %H:%M:%S")
        }

