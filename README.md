# WazeRouteCalculatortask

An advanced version of **WazeRouteCalculator** with the ability to accept a starting point, destination, stops, stop durations, and desired arrival time, and return the departure time.  
The current version includes a cache that reduces the number of requests to the Waze API.

---

## Key Features

- Calculate optimal departure time to meet a target arrival time.
- Support for multiple stops with configurable break durations.
- Intelligent caching to minimize Waze API requests.
- Real-time adjustments for traffic during peak hours.
- Easy-to-use CLI interface.

---

## Example Usage

### **Trip with Stops**

Add intermediate stops with configurable break durations:

```bash
C:\Users\koren\WazeRouteCalculatortask\waze_calculator>python my_client_app.py --src eilat --dst haifa --stops tel-aviv,1h,hadera,15m --arrival_time 16:40
```
Leave eilat at 10:27 to reach haifa by 16:40.

### **Trip without Stops**

Calculate the optimal departure time for a trip without intermediate stops:

```bash
C:\Users\koren\WazeRouteCalculatortask\waze_calculator>python my_client_app.py --src ariel --dst tel-aviv --arrival_time 14:46
```

Leave ariel at 14:00 to reach tel-aviv by 14:46.
