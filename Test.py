#!/usr/bin/env python3

import threading
import gi
import os
from datetime import datetime

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import depthai as dai


class VideoHandler:
    def __init__(self, host='192.168.1.192', port=5601, save_path='recordings'):
        Gst.init(None)
        self.host = host
        self.port = port
        self.save_path = save_path
        self.pipeline_stream = None
        self.pipeline_record = None
        self.data = None

        # Tạo thư mục lưu video nếu chưa tồn tại
        if not os.path.exists(save_path):
            os.makedirs(save_path)

    def start(self):
        t = threading.Thread(target=self._thread_glib)
        t.daemon = True  # Thread sẽ tự động kết thúc khi chương trình chính kết thúc
        t.start()

    def _thread_glib(self):
        loop = GLib.MainLoop()
        loop.run()

    def send_data(self, data):
        self.data = data
        for pipeline in [self.pipeline_stream, self.pipeline_record]:
            if pipeline:
                appsrc = pipeline.get_by_name('source')
                if appsrc:
                    try:
                        buffer = Gst.Buffer.new_wrapped(self.data.tobytes())
                        retval = appsrc.emit('push-buffer', buffer)
                        if retval != Gst.FlowReturn.OK:
                            print(f"Error pushing buffer to pipeline: {retval}")
                    except Exception as e:
                        print(f"Error sending data: {e}")

    def setup_pipelines(self):
        # Pipeline cho UDP stream
        self.pipeline_stream = Gst.parse_launch(
            'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME ! '
            'h265parse ! rtph265pay pt=96 ! udpsink host={} port={}'.format(self.host, self.port)
        )

        # Pipeline cho việc lưu file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.save_path, f'video_{timestamp}.mp4')
        self.pipeline_record = Gst.parse_launch(
            'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME ! '
            'h265parse ! mp4mux ! filesink location={}'.format(filename)
        )

        # Setup callback cho cả hai pipeline
        for pipeline in [self.pipeline_stream, self.pipeline_record]:
            appsrc = pipeline.get_by_name('source')
            if appsrc:
                appsrc.connect('need-data', self.on_need_data)
            pipeline.set_state(Gst.State.PLAYING)

    def on_need_data(self, src, length):
        if self.data is not None:
            try:
                buffer = Gst.Buffer.new_wrapped(self.data.tobytes())
                retval = src.emit('push-buffer', buffer)
                if retval != Gst.FlowReturn.OK:
                    print(f"Error in need-data: {retval}")
            except Exception as e:
                print(f"Error in need-data handler: {e}")

    def cleanup(self):
        # Dọn dẹp resources
        for pipeline in [self.pipeline_stream, self.pipeline_record]:
            if pipeline:
                pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    try:
        handler = VideoHandler(host='192.168.1.192', port=5601, save_path='recordings')
        handler.setup_pipelines()

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
            print(f"Setup finished, streaming video over UDP to {handler.host}:{handler.port}")
            print(f"Recording to folder: {handler.save_path}")

            try:
                while True:
                    data = encoded.get().getData()
                    handler.send_data(data)
            except KeyboardInterrupt:
                print("\nStopping application...")
            finally:
                handler.cleanup()
                print("Application stopped")

    except Exception as e:
        print(f"Error occurred: {e}")