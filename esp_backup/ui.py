def print_result(result):

    if result["type"] == "pothole":

        print(
            "[POTHOLE]",
            "Depth:",
            "{:.1f} mm".format(
                result["depth"]
            ),
            "Angle:",
            "{:.1f}°".format(
                result["angle"]
            ),
        )

    else:

        print(
            "[OBJECT]",
            "Height:",
            "{:.1f} mm".format(
                result["height"]
            ),
            "Angle:",
            "{:.1f}°".format(
                result["angle"]
            ),
        )


def display_result(oled, result):

    oled.clear_buf()

    if result["type"] == "pothole":

        oled.text("POTHOLE", 5, 5)

        oled.text(
            "{:.1f} mm".format(
                result["depth"]
            ),
            5,
            25
        )

    else:

        oled.text("OBJECT", 5, 5)

        oled.text(
            "{:.1f} mm".format(
                result["height"]
            ),
            5,
            25
        )

    oled.show()