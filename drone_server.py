import asyncio
import websockets
import json
from pymavlink import mavutil
import random
import time

# --- Configuration ---
# IMPORTANT: Change this to how your Raspberry Pi connects to the Flight Controller.
# Common values: '/dev/ttyAMA0' (UART), '/dev/ttyACM0' (USB).
# For testing on a computer with a simulator (SITL), use 'udp:127.0.0.1:14550'.
MAVLINK_CONNECTION = 'udp:127.0.0.1:57600'
WEBSOCKET_PORT = 8765
SIMULATION_MODE = False # This is set automatically if the MAVLink connection fails.

# --- Global State ---
# This dictionary holds the most recent data from the drone.
telemetry_data = {
    "latitude": 13.0827,       # Default to a location (e.g., Chennai)
    "longitude": 80.2707,      # Default to a location (e.g., Chennai)
    "altitude": 0.0,
    "ground_speed": 0.0,
    "battery_percent": 100,
    "flight_mode": "INITIALIZING",
    "mission_status": "Idle"
}

# --- MAVLink Communication ---
async def mavlink_loop():
    """
    Connects to the flight controller via MAVLink, continuously reads telemetry data,
    and updates the global telemetry_data dictionary.
    """
    global SIMULATION_MODE
    print(f"Attempting to connect to MAVLink on {MAVLINK_CONNECTION}...")
    try:
        master = mavutil.mavlink_connection(MAVLINK_CONNECTION, baud=57600)
        master.wait_heartbeat()
        print("MAVLink connection successful! Reading live data from drone.")
        SIMULATION_MODE = False
    except Exception as e:
        print(f"CRITICAL: MAVLink connection failed: {e}")
        print("WARNING: Could not connect to drone. Running in SIMULATION MODE.")
        SIMULATION_MODE = True
        return  # Stop this function and let the simulation take over.

    # If connection is successful, enter the main loop to read messages.
    while not SIMULATION_MODE:
        msg = master.recv_match(blocking=True)
        if not msg:
            continue

        msg_type = msg.get_type()
        
        if msg_type == 'GPS_RAW_INT' and msg.fix_type >= 3: # Check for a 3D fix
            telemetry_data['latitude'] = msg.lat / 1e7
            telemetry_data['longitude'] = msg.lon / 1e7
        elif msg_type == 'VFR_HUD':
            telemetry_data['altitude'] = msg.alt
            telemetry_data['ground_speed'] = msg.groundspeed
        elif msg_type == 'SYS_STATUS':
            telemetry_data['battery_percent'] = msg.battery_remaining
        elif msg_type == 'HEARTBEAT':
            # Decode the flight mode from the HEARTBEAT message
            mode = mavutil.mode_string_v10(msg)
            if mode:
                telemetry_data['flight_mode'] = mode

        await asyncio.sleep(0.01) # Small delay to prevent busy-waiting

# --- Simulation Mode ---
async def simulation_loop():
    """
    If the drone isn't connected, this function generates fake telemetry data
    to allow for testing the website's user interface.
    """
    start_time = time.time()
    while True:
        if SIMULATION_MODE:
            # Simulate battery drain slowly
            if telemetry_data['battery_percent'] > 0:
                telemetry_data['battery_percent'] -= 0.05
            
            # Simulate movement if a mission is active
            if telemetry_data['mission_status'] != 'Idle':
                telemetry_data['altitude'] = 15 + 2 * (random.random() - 0.5) # Fly at ~15m
                telemetry_data['ground_speed'] = 5 + (random.random() - 0.5) # Fly at ~5 m/s
                
                # Simulate a simple circular flight path for location changes
                angle = (time.time() - start_time) * 0.1
                telemetry_data['latitude'] += 0.00005 * random.cos(angle)
                telemetry_data['longitude'] += 0.00005 * random.sin(angle)

                if telemetry_data['flight_mode'] != "AUTO":
                    telemetry_data['flight_mode'] = "AUTO"
            else: # If idle on the ground
                telemetry_data['altitude'] = 0
                telemetry_data['ground_speed'] = 0
                telemetry_data['flight_mode'] = "STABILIZE"

        await asyncio.sleep(0.5) # Update simulation data every half second

# --- WebSocket Server ---
async def websocket_handler(websocket, path):
    """
    Manages a single client connection. It starts two tasks for each client:
    1. producer_handler: Sends telemetry data out to the website.
    2. consumer_handler: Listens for commands coming in from the website.
    """
    print(f"Dashboard connected from: {websocket.remote_address}")
    try:
        consumer_task = asyncio.ensure_future(consumer_handler(websocket))
        producer_task = asyncio.ensure_future(producer_handler(websocket))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except websockets.exceptions.ConnectionClosed:
        print(f"Dashboard at {websocket.remote_address} disconnected.")

async def producer_handler(websocket):
    """Sends the latest telemetry data to the connected client every 0.5 seconds."""
    while True:
        try:
            await websocket.send(json.dumps(telemetry_data))
            await asyncio.sleep(0.5)
        except websockets.exceptions.ConnectionClosed:
            break

async def consumer_handler(websocket):
    """Waits for and processes incoming commands from the website."""
    async for message in websocket:
        command_data = json.loads(message)
        command = command_data.get('command')
        
        if command == 'start_mission':
            order_id = command_data.get('orderId', 'N/A')
            print(f"Received command: 'start_mission' for Order ID: {order_id}")
            asyncio.create_task(run_mission_simulation())

async def run_mission_simulation():
    """Simulates a drone's delivery mission steps."""
    print("Mission simulation started.")
    telemetry_data['mission_status'] = 'Flying to Destination'
    await asyncio.sleep(15)  # Simulate 15-second flight to the destination
    
    print("Arrived at destination, simulating return flight.")
    telemetry_data['mission_status'] = 'Returning to Home'
    await asyncio.sleep(15)  # Simulate 15-second flight back to home
    
    print("Mission complete. Drone is now idle.")
    telemetry_data['mission_status'] = 'Idle'

# --- Main Application Entry ---
async def main():
    """Starts all necessary components: MAVLink, Simulation, and WebSocket Server."""
    # Start the MAVLink and simulation loops. They will run in the background.
    asyncio.create_task(mavlink_loop())
    asyncio.create_task(simulation_loop())

    # Start the WebSocket server to listen for website connections.
    server = await websockets.serve(websocket_handler, "0.0.0.0", WEBSOCKET_PORT)
    print(f"WebSocket server started on port {WEBSOCKET_PORT}. Waiting for connections...")
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user.")

