# Waze Enhanced Trip Planner

A Python-based tool for calculating optimal departure times to meet a desired arrival time, with support for stopovers and traffic patterns. The system minimizes calls to Waze API using a caching mechanism to enhance efficiency.

---

## Features
- **Optimal Departure Calculation**: Calculates the latest possible departure time to arrive at the destination without delay.
- **Stopovers and Break Times**: Supports intermediate stops with customizable break durations.
- **Traffic Awareness**: Adjusts travel time based on peak hours (morning and afternoon).
- **Caching Mechanism**: Reduces redundant calls to the Waze API by storing and reusing route data.

---

## Installation
Ensure you have Python 3.8 or higher installed.

1. Clone the repository:
   ```bash
   git clone https://github.com/koren-d/WazeRouteCalculatortask.git