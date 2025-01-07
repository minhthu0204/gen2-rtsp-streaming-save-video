#!/usr/bin/env python3

import threading
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import depthai as dai

class UdpStream:
    def __init__(self, host='192.168.1.192', port=5601, output_file='output.h265'):
        Gst.init(None)
        self.host = host
        self.port = port
        self.output_file = output_file
        self.pipeline = None
        self.data = None

    def start(self):
        t = threading.Thread(target=self._thread_udp)
        t.start()

    def _thread_udp(self):
        loop = GLib.MainLoop()
        loop.run()

    def send_data(self, data):
        self.data = data
        if self.pipeline:
            appsrc = self.pipeline.get_by_name('source')
            if appsrc:
                # Chuyển đổi dữ liệu thành Gst.Buffer
                buffer = Gst.Buffer.new_wrapped(self.data.tobytes())
                retval = appsrc.emit('push-buffer', buffer)
                if retval != Gst.FlowReturn.OK:
                    print("Error pushing buffer:", retval)

    def setup_pipeline(self):
        # Pipeline để ghi dữ liệu H.265 vào file
        self.pipeline = Gst.parse_launch(
            f'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME ! '
            f'h265parse ! matroskamux ! filesink location={self.output_file}'
        )
        appsrc = self.pipeline.get_by_name('source')
        if appsrc:
            appsrc.connect('need-data', self.on_need_data)
        self.pipeline.set_state(Gst.State.PLAYING)

    def on_need_data(self, src, length):
        if self.data is not None:
            # Chuyển đổi dữ liệu thành Gst.Buffer khi cần
            buffer = Gst.Buffer.new_wrapped(self.data.tobytes())
            retval = src.emit('push-buffer', buffer)
            if retval != Gst.FlowReturn.OK:
                print("Error pushing buffer:", retval)


if __name__ == "__main__":
    # Thiết lập server để lưu dữ liệu vào file output.h265
    server = UdpStream(host='192.168.1.192', port=5601, output_file='output.h265')
    server.setup_pipeline()

    # Tạo pipeline DepthAI
    pipeline = dai.Pipeline()

    FPS = 30
    colorCam = pipeline.create(dai.node.ColorCamera)
    colorCam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    colorCam.setInterleaved(False)
    colorCam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    colorCam.setFps(FPS)

    videnc = pipeline.create(dai.node.VideoEncoder)
    videnc.setDefaultProfilePreset(FPS, dai.VideoEncoderProperties.Profile.H265_MAIN)
    colorCam.video.link(videnc.input)

    veOut = pipeline.create(dai.node.XLinkOut)
    veOut.setStreamName("encoded")
    videnc.bitstream.link(veOut.input)

    # Kiểm tra thiết bị DepthAI
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
                raise ValueError(f"Incorrect value supplied: {val}")

    if device_info.protocol != dai.XLinkProtocol.X_LINK_USB_VSC:
        print(f"Running stream may be unstable due to connection... (protocol: {device_info.protocol})")

    # Chạy pipeline và ghi video
    with dai.Device(pipeline, device_info) as device:
        encoded = device.getOutputQueue("encoded", maxSize=30, blocking=True)
        print(f"Setup finished. Streaming video to {server.host}:{server.port} and saving to {server.output_file}")
        while True:
            data = encoded.get().getData()
            server.send_data(data)
