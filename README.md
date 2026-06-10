A lightweight Python backend that bridges a drone's flight controller to a real-time web dashboard using MAVLink and WebSockets.
What It Does
Runs on a Raspberry Pi (or any computer) and connects to an ArduPilot/PX4 flight controller over UART or USB. It continuously reads live telemetry — GPS position, altitude, ground speed, battery level, and flight mode — and streams it to a web dashboard over WebSockets. It also listens for commands from the dashboard, such as triggering a delivery mission.
If no flight controller is detected at startup, it automatically switches to simulation mode, generating realistic fake telemetry so you can develop and test the UI without any hardware.
Features

Live telemetry over WebSockets (updates every 0.5s)
Reads GPS, altitude, speed, battery, and flight mode via MAVLink
Supports UART (/dev/ttyAMA0), USB (/dev/ttyACM0), and SITL (udp:127.0.0.1:14550)
Auto-fallback simulation mode with animated flight path and battery drain
Handles multiple dashboard clients simultaneously
Mission command support (start_mission) with simulated flight stages
