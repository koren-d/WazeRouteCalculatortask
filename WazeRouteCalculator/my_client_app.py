import argparse
from WazeRouteCalculator import WazeRouteCalculator
from datetime import datetime

def parse_stops(stops_input):
    stops = []
    breaks = []
    items = stops_input.split(",")

    for i in range(0, len(items), 2):
        stop = items[i]
        stops.append(stop)

        if i + 1 < len(items):
            break_time = items[i + 1]
            if break_time.endswith("h"):
                breaks.append(int(break_time[:-1]) * 60)
            elif break_time.endswith("m"):
                breaks.append(int(break_time[:-1]))
            else:
                print("Invalid break format")
    return stops, breaks


def main():
    WazeRouteCalculator.load_dict()

    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    parser.add_argument("--stops", required=True)
    parser.add_argument("--arrival_time", required=True)
    args = parser.parse_args()

    src = args.src
    dst = args.dst
    stops, breaks = parse_stops(args.stops)
    desired_arrival_time = datetime.now().strftime("%Y-%m-%d") + " " + args.arrival_time + ":00"

    locations = [src] + stops + [dst]

    waze_calculator = WazeRouteCalculator(locations[0], locations[1], region="IL")
    trip_data = waze_calculator.calculate_total_trip_time_with_logs(locations, breaks, desired_arrival_time)

    departure_time = datetime.strptime(trip_data['recommended_departure_time'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
    arrival_time = datetime.strptime(desired_arrival_time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")

    print(f"Leave {src} at {departure_time} to reach {dst} by {arrival_time}.")
    WazeRouteCalculator.save_dict()


if __name__ == "__main__":
    main()
