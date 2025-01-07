#!/usr/bin/env python3

import threading
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import depthai as dai

class UdpStream:
    def __init__(self, host='192.168.1.26', port=400):
        Gst.init(None)
        self.host = host
        self.port = port
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
        self.pipeline = Gst.parse_launch(
            'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME ! '
            'h265parse ! tee name=t '
            't. ! queue ! rtph265pay pt=96 ! udpsink host={} port={} '
            't. ! queue ! mp4mux ! filesink location=output_video.mp4'.format(self.host, self.port)
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
    server = UdpStream(host='192.168.1.26', port=5400)
    server.setup_pipeline()

    pipeline = dai.Pipeline()

    FPS = 30
    colorCam = pipeline.create(dai.node.ColorCamera)
    colorCam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    colorCam.setInterleaved(False)
    colorCam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    colorCam.setFps(FPS)

    videnc = pipeline.create(dai.node.VideoEncoder)
    videnc.setDefaultProfilePreset(FPS, dai.VideoEncoderProperties.Profile.H265_MAIN)
    videnc.setBitrate(2000000)
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

    with dai.Device(pipeline, device_info) as device:
        encoded = device.getOutputQueue("encoded", maxSize=30, blocking=True)
        print("Setup finished, streaming video over UDP to {}:{}".format(server.host, server.port))
        while True:
            data = encoded.get().getData()
            server.send_data(data)
