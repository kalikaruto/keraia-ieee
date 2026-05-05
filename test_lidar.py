"""
Test script to verify RPLIDAR A1 connection and display scan data.
"""

import rplidar
import time

# LIDAR configuration
PORT = '/dev/ttyUSB1'
BAUDRATE = 115200

def test_connection():
    """Connect to LIDAR and print scan data for verification."""
    print(f"Connecting to RPLIDAR on {PORT}...")
    lidar = rplidar.RPLidar(PORT, baudrate=BAUDRATE)

    print("Successfully connected!")
    print("Press Ctrl+C to stop\n")
    print("-" * 60)
    print(f"{'Angle':>8} | {'Distance (cm)':>14} | {'Quality':>8}")
    print("-" * 65)

    try:
        # Iterate through scans
        TARGET_ANGLE = 0
        TOLERANCE = 11  # degrees

        for scan in lidar.iter_scans():
            for quality, angle, distance in scan:

                # Normalize angle (optional safety)
                # angle = angle % 360

                if not (angle <= TOLERANCE or angle >= (360 - TOLERANCE)):
                    continue

                distance_cm = distance / 10.0
                print(f"{angle:>8.2f} | {distance_cm:>14.2f} | {quality:>8}")

            # print("-" * 60)

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    test_connection()
