from PIL import Image
import argparse


def get_rgb_image(image_path):
    image = Image.open(image_path, "r").convert("L")
    return image


def generate_sensor_data(rgb_image):
    sensor_data = []
    width, height = rgb_image.size
    for row in range(0, height):
        for column in range(0, width):
            lightness = rgb_image.getpixel((column, row))

            if lightness > 127:
                sensor_data.append(((column * 1.0) / width, (row * 1.0) / height))

    return sensor_data


def generate_sensor_database(input_file_path, output_file_path, key_name):
    pixels = get_rgb_image(input_file_path)
    sensor_points = generate_sensor_data(pixels)

    with open(output_file_path, "w") as output_file:
        output_file.write("{0} = {{\n".format(key_name))
        output_file.write("    points = {  ")
        for x, y in sensor_points:
            output_file.write("{{ position = {{ {0} {1} }} weight = {2} }} ".format(x, y, 1.0))
        output_file.write(" }")
        output_file.write("\n}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("sensorgen")
    parser.add_argument("--input_file_path",
                        help="Path to monochrome image where black is background and white pixel is a sensor point")
    parser.add_argument("--output_file_path", help="Path to output file. The file will be overwritten")
    parser.add_argument("--key_name", help="Name of the pattern to output")

    args = parser.parse_args()

    generate_sensor_database(args.input_file_path, args.output_file_path, args.key_name)
