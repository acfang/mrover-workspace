########################################################################
#
# Copyright (c) 2020, STEREOLABS.
#
# All rights reserved.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
########################################################################

# TODO: function saveMatPointCloudAs / savePointCloudAs doesn't exist in pyzed.sl
#       but exists in zed-python-api/pyzed/Utils.cpp and sl.cpp

import pyzed.sl as sl
import subprocess
import time


def main():
    # Create a Camera object
    print("beginning")

    zed = sl.Camera()

    # Create a InitParameters object and set configuration parameters
    init_params = sl.InitParameters()
    # Use HD1080 video mode
    init_params.camera_resolution = sl.RESOLUTION.RESOLUTION_HD1080
    init_params.camera_fps = 30  # Set fps at 30

    print("camera initialized")

    # Open the camera
    err = zed.open(init_params)
    if err != sl.ERROR_CODE.SUCCESS:
        exit(1)

    print("camera opened")

    time.sleep(5)

    # Capture one frame and stop
    image = sl.Mat()
    runtime_parameters = sl.RuntimeParameters()
    # Grab an image, a RuntimeParameters object must be given to grab()
    if zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
        # A new image is available if grab() returns SUCCESS
        zed.retrieve_image(image, sl.VIEW.VIEW_LEFT)
        timestamp = zed.get_timestamp(sl.TIME_REFERENCE.TIME_REFERENCE_CURRENT)
        # Get the timestamp at the time the image was captured
        print("Image resolution: {0} x {1} || Image timestamp: {2}\n".format(
              image.get_width(), image.get_height(), timestamp))
        print(sl.savePointCloudAs(zed, sl.POINT_CLOUD_FORMAT_PCD_ASCII,
                            "surroundings.pcd", False))
        subprocess.run(["scp", "surroundings.pcd",
                       "mrover@10.0.0.2:base_station/kineval_stencil/dist"])

    print("ready to close")

    # Close the camera
    zed.close()


if __name__ == "__main__":
    main()
