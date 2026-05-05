import rplidar
import numpy as np
import matplotlib.pyplot as plt
import time

PORT = '/dev/ttyUSB1'
BAUDRATE = 115200

ANGLE_MIN = -30
ANGLE_MAX = 30


def polar_to_cartesian(scan):
    pts = []

    for quality, angle, dist in scan:
        if dist == 0:
            continue

        # convert to [-180, 180]
        if angle > 180:
            angle -= 360

        if ANGLE_MIN <= angle <= ANGLE_MAX:
            theta = np.deg2rad(angle)
            r = dist / 1000.0  # mm → meters

            x = r * np.cos(theta)
            y = r * np.sin(theta)

            pts.append((x, y))

    return np.array(pts)


def fit_line(points):
    x = points[:, 0]
    y = points[:, 1]

    A = np.vstack([x, np.ones(len(x))]).T
    a, b = np.linalg.lstsq(A, y, rcond=None)[0]

    return a, b


def rotate(points, angle):
    R = np.array([
        [np.cos(angle), -np.sin(angle)],
        [np.sin(angle),  np.cos(angle)]
    ])
    return points @ R.T


def process(points):
    # baseline fit
    a, b = fit_line(points)

    # tilt angle
    alpha = np.arctan(a)

    # rotate
    rotated = rotate(points, -alpha)

    x = rotated[:, 0]
    y = rotated[:, 1]

    # height deviation
    h = y - np.mean(y)

    # sort for profile
    idx = np.argsort(x)
    return x[idx], h[idx]


def main():
    lidar = rplidar.RPLidar(PORT, baudrate=BAUDRATE)

    plt.ion()
    fig, ax = plt.subplots()

    try:
        for scan in lidar.iter_scans():
            pts = polar_to_cartesian(scan)

            if len(pts) < 20:
                continue

            x, h = process(pts)

            ax.clear()
            ax.plot(x, h)

            ax.set_title("Surface Profile")
            ax.set_xlabel("Distance along scan (m)")
            ax.set_ylabel("Height deviation (m)")
            ax.set_ylim(-0.05, 0.05)

            plt.pause(0.01)

    except KeyboardInterrupt:
        pass

    finally:
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()


if __name__ == "__main__":
    main()
