#!/bin/sh
# Keep 4K capture off the GPU tiled raster path; no system or browser-profile changes.
exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --disable-gpu --disable-gpu-rasterization "$@"
