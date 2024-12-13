# -*- coding: utf-8 -*-
"""Waze route calculator"""

import logging
import requests
import re
from datetime import datetime, timedelta

class WRCError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WazeRouteCalculator(object):
    """Calculate actual route time and distance with Waze API"""
    cache = {}  # Static attribute for caching
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
        if not hasattr(WazeRouteCalculator, 'cache'):
            WazeRouteCalculator.cache = {}  # Static cache attribute

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
    def calculate_departure_time(self, desired_arrival_time):
        arrival_time = datetime.strptime(desired_arrival_time, '%H:%M')
        route_time, _ = self.calc_route_info()  # route_time is in minutes
        departure_time = arrival_time - timedelta(minutes=route_time)
        return departure_time.strftime('%H:%M')
    
    def calculate_trip_time(self, locations, desired_arrival_time):

        if len(locations) < 2:
            raise ValueError("You must provide at least two locations: a start and an end.")

        results = []
        current_arrival_time = datetime.strptime(desired_arrival_time, '%H:%M')

        # Loop through the locations in reverse order to calculate departure times
        for i in range(len(locations) - 1, 0, -1):
            # Create an instance for the current leg of the trip
            self.__init__(locations[i - 1], locations[i], region=self.region)

            # Calculate travel time for the current leg
            route_time, _ = self.calc_route_info()  # Get travel time in minutes
            departure_time = current_arrival_time - timedelta(minutes=route_time)

            # Add results for the current leg
            results.insert(0, {
                "from": locations[i - 1],
                "to": locations[i],
                "departure_time": departure_time.strftime('%H:%M'),
                "arrival_time": current_arrival_time.strftime('%H:%M'),
                "travel_time_minutes": route_time
            })

            # Update the arrival time for the next leg
            current_arrival_time = departure_time

        # Calculate total trip time
        total_trip_time = (datetime.strptime(desired_arrival_time, '%H:%M') - current_arrival_time).total_seconds() / 60

        return {
            "legs": results,
            "total_trip_time_minutes": total_trip_time
        }
    

    def get_cached_route_time(self, start, end):

        if not hasattr(WazeRouteCalculator, 'cache'):
            WazeRouteCalculator.cache = {}

        route_key = f"{start} -> {end}"
        if route_key in WazeRouteCalculator.cache:
            cache_entry = WazeRouteCalculator.cache[route_key]
            cache_time = datetime.strptime(cache_entry['timestamp'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - cache_time < timedelta(minutes=10):
                print(f"[CACHE HIT] Using cached data for {route_key}")
                return cache_entry['travel_time_minutes']
            else:
                print(f"[CACHE EXPIRED] Removing outdated cache for {route_key}")
                del WazeRouteCalculator.cache[route_key]
        return None

    def calculate_total_trip_time_with_logs(self, locations, breaks=None):

        if len(locations) < 2:
            raise ValueError("You must provide at least two locations: a start and an end.")

        if breaks is None:
            breaks = [0] * (len(locations) - 1)
        elif len(breaks) != len(locations) - 1:
            raise ValueError("Breaks list must have exactly len(locations) - 1 elements.")

        total_trip_time = 0
        self.travel_logs = {}

        for i in range(len(locations) - 1):
            start, end = locations[i], locations[i + 1]
            route_key = f"{start} -> {end}"

            route_time = self.get_cached_route_time(start, end)
            if route_time is not None:
                print(f"[CACHE] Using cached route time for {route_key}: {route_time} minutes")
            else:

                print(f"[API REQUEST] Calculating route time for {route_key}...")
                temp_calculator = WazeRouteCalculator(start, end, region=self.region)
                route_time, _ = temp_calculator.calc_route_info()
                print(f"[CACHE UPDATE] Storing data for {route_key}: {route_time} minutes")
                WazeRouteCalculator.cache[route_key] = {
                    "travel_time_minutes": route_time,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

            total_trip_time += route_time + breaks[i]

            self.travel_logs[route_key] = {
                "travel_time_minutes": route_time,
                "break_time_minutes": breaks[i],
                "timestamp": WazeRouteCalculator.cache[route_key]["timestamp"]
            }

        return {
            "total_trip_time_minutes": total_trip_time,
            "travel_logs": self.travel_logs
        }


    
