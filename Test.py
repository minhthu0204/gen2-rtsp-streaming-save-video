#!/usr/bin/env python3

import depthai as dai
import signal
import sys


# Hàm để xử lý tín hiệu kết thúc (Ctrl+C)
def signal_handler(sig, frame):
    print("\nTerminating...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    pipeline = dai.Pipeline()

    FPS = 30
    colorCam = pipeline.create(dai.node.ColorCamera)
    colorCam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    colorCam.setInterleaved(False)
    colorCam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    colorCam.setFps(FPS)

    videnc = pipeline.create(dai.node.VideoEncoder)
    videnc.setDefaultProfilePreset(FPS, dai.VideoEncoderProperties.Profile.MJPEG)
    colorCam.video.link(videnc.input)

    veOut = pipeline.create(dai.node.XLinkOut)
    veOut.setStreamName("encoded")
    videnc.bitstream.link(veOut.input)

    device_infos = dai.Device.getAllAvailableDevices()
    if len(device_infos) == 0:
        raise RuntimeError("No DepthAI device found!")
    else:
        print("Available devices:")
        for i, info in enumerate(device_infos):
            print(f"[{i}] {info.getMxId()} [{info.state.name}]")
        if len(device_infos) == 1:
            device_info = device_infos[0]
        else:
            val = input("Which DepthAI Device you want to use: ")
            try:
                device_info = device_infos[int(val)]
            except:
                raise ValueError("Incorrect value supplied: {}".format(val))

    if device_info.protocol != dai.XLinkProtocol.X_LINK_USB_VSC:
        print("Running stream may be unstable due to connection... (protocol: {})".format(device_info.protocol))

    # Mở tệp để lưu video
    output_file = open("output.mp4", "wb")

    try:
        with dai.Device(pipeline, device_info) as device:
            encoded = device.getOutputQueue("encoded", maxSize=30, blocking=True)

            print("Recording video to 'output.h265'. Press Ctrl+C to stop.")
            while True:
                data = encoded.get().getData()
                output_file.write(data)
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        output_file.close()
        print("Video recording stopped.")
