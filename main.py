from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent
IMAGE_PATH = ROOT / "data" / "Aerosols_2025-08-19T20_00_00_4200x3300_300dpi.png"
HOST = "127.0.0.1"
PORT = 8000


PAGE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Image pixel inspector</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      overflow: hidden;
      background: #101316;
      color: #f4f7f8;
    }

    #image {
      display: block;
      position: absolute;
      inset: 0;
      width: auto;
      height: auto;
      max-width: 100vw;
      max-height: 100vh;
      margin: auto;
      cursor: crosshair;
    }

    #readout {
      position: fixed;
      top: 1rem;
      left: 1rem;
      min-width: 13rem;
      padding: 0.8rem 1rem;
      border: 1px solid rgb(255 255 255 / 18%);
      border-radius: 0.6rem;
      background: rgb(10 14 16 / 84%);
      box-shadow: 0 0.5rem 1.5rem rgb(0 0 0 / 30%);
      pointer-events: auto;
      line-height: 1.5;
    }

    #readout strong {
      display: block;
      margin-bottom: 0.25rem;
      font-size: 0.8rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #9ed8ff;
    }

    #readout span {
      font-variant-numeric: tabular-nums;
    }

    #color-swatch {
      width: 100%;
      height: 2.5rem;
      margin: 0.75rem 0;
      border: 1px solid rgb(255 255 255 / 35%);
      border-radius: 0.35rem;
      background: #000;
    }

    .bar {
      display: grid;
      grid-template-columns: 1.5rem 1fr;
      align-items: center;
      gap: 0.45rem;
      margin-top: 0.3rem;
      font-size: 0.75rem;
    }

    .bar-track {
      height: 0.45rem;
      overflow: hidden;
      border-radius: 1rem;
      background: rgb(255 255 255 / 18%);
    }

    .bar-value {
      width: 0;
      height: 100%;
      border-radius: inherit;
      background: #f4f7f8;
    }

    #radius-control {
      display: block;
      width: 100%;
      margin-top: 0.75rem;
    }

    #radius-label {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.15rem;
      font-size: 0.75rem;
    }

    #status {
      position: fixed;
      inset: 50% auto auto 50%;
      transform: translate(-50%, -50%);
      color: #ffb4b4;
    }
  </style>
</head>
<body>
  <canvas id="image" aria-label="Aerosol map"></canvas>
  <div id="readout">
    <strong>Pixel</strong>
    <span id="coordinates">x: --, y: --</span><br>
    <span id="hsl">HSL: --</span>
    <div id="color-swatch" title="Hovered pixel color"></div>
    <div class="bar"><span>H</span><div class="bar-track"><div id="hue-bar" class="bar-value"></div></div></div>
    <div class="bar"><span>S</span><div class="bar-track"><div id="saturation-bar" class="bar-value"></div></div></div>
    <div class="bar"><span>L</span><div class="bar-track"><div id="lightness-bar" class="bar-value"></div></div></div>
    <label id="radius-label" for="radius-control">
      <span>Averaging radius</span><span id="radius-value">0 px</span>
    </label>
    <input id="radius-control" type="range" min="0" max="25" value="0">
  </div>
  <div id="status" hidden></div>

  <script>
    const canvas = document.querySelector("#image");
    const context = canvas.getContext("2d", {willReadFrequently: true});
    const readout = document.querySelector("#readout");
    const coordinates = document.querySelector("#coordinates");
    const hsl = document.querySelector("#hsl");
    const colorSwatch = document.querySelector("#color-swatch");
    const hueBar = document.querySelector("#hue-bar");
    const saturationBar = document.querySelector("#saturation-bar");
    const lightnessBar = document.querySelector("#lightness-bar");
    const radiusControl = document.querySelector("#radius-control");
    const radiusValue = document.querySelector("#radius-value");
    const status = document.querySelector("#status");
    const image = new Image();
    let lastMouseEvent = null;

    function rgbToHsl(red, green, blue) {
      red /= 255;
      green /= 255;
      blue /= 255;

      const maximum = Math.max(red, green, blue);
      const minimum = Math.min(red, green, blue);
      const lightness = (maximum + minimum) / 2;
      const difference = maximum - minimum;

      if (difference === 0) {
        return [0, 0, lightness * 100];
      }

      const saturation = difference / (1 - Math.abs(2 * lightness - 1));
      let hue;

      if (maximum === red) {
        hue = 60 * (((green - blue) / difference) % 6);
      } else if (maximum === green) {
        hue = 60 * ((blue - red) / difference + 2);
      } else {
        hue = 60 * ((red - green) / difference + 4);
      }

      return [(hue + 360) % 360, saturation * 100, lightness * 100];
    }

    function showPixel(event) {
      lastMouseEvent = event;
      const bounds = canvas.getBoundingClientRect();
      const x = Math.min(
        image.naturalWidth - 1,
        Math.max(0, Math.floor((event.clientX - bounds.left) * image.naturalWidth / bounds.width))
      );
      const y = Math.min(
        image.naturalHeight - 1,
        Math.max(0, Math.floor((event.clientY - bounds.top) * image.naturalHeight / bounds.height))
      );
      const radius = Number(radiusControl.value);
      const left = Math.max(0, x - radius);
      const top = Math.max(0, y - radius);
      const right = Math.min(image.naturalWidth - 1, x + radius);
      const bottom = Math.min(image.naturalHeight - 1, y + radius);
      const pixels = context.getImageData(
        left,
        top,
        right - left + 1,
        bottom - top + 1
      ).data;
      let red = 0;
      let green = 0;
      let blue = 0;

      for (let index = 0; index < pixels.length; index += 4) {
        red += pixels[index];
        green += pixels[index + 1];
        blue += pixels[index + 2];
      }

      const pixelCount = pixels.length / 4;
      red = Math.round(red / pixelCount);
      green = Math.round(green / pixelCount);
      blue = Math.round(blue / pixelCount);
      const [hue, saturation, lightness] = rgbToHsl(red, green, blue);

      coordinates.textContent = `x: ${x}, y: ${y}`;
      hsl.textContent = `HSL: ${hue.toFixed(1)}°, ${saturation.toFixed(1)}%, ${lightness.toFixed(1)}%`;
      colorSwatch.style.backgroundColor = `rgb(${red}, ${green}, ${blue})`;
      hueBar.style.width = `${hue / 360 * 100}%`;
      saturationBar.style.width = `${saturation}%`;
      lightnessBar.style.width = `${lightness}%`;
      readout.hidden = false;
    }

    image.addEventListener("load", () => {
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      context.drawImage(image, 0, 0);
      window.addEventListener("resize", () => context.drawImage(image, 0, 0));
    });

    image.addEventListener("error", () => {
      status.textContent = "The image could not be loaded.";
      status.hidden = false;
    });

    canvas.addEventListener("mousemove", showPixel);
    radiusControl.addEventListener("input", () => {
      radiusValue.textContent = `${radiusControl.value} px`;
      if (lastMouseEvent) {
        showPixel(lastMouseEvent);
      }
    });
    image.src = "/image";
  </script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            content = PAGE.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif path == "/image":
            if not IMAGE_PATH.is_file():
                self.send_error(404, "Image file not found")
                return
            content = IMAGE_PATH.read_bytes()
            content_type = "image/png"
        else:
            self.send_error(404, "Not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Open http://{HOST}:{PORT} in your browser")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")
    finally:
        server.server_close()