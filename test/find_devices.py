# find_devices.py
import pyaudio

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

print("PyAudio 可识别的音频设备列表:")
for i in range(0, numdevices):
    dev_info = p.get_device_info_by_index(i)
    if (dev_info.get('maxInputChannels')) > 0:
        print(f"  输入设备 ID {i} - 名称: {dev_info.get('name')}")
    if (dev_info.get('maxOutputChannels')) > 0:
        print(f"  输出设备 ID {i} - 名称: {dev_info.get('name')}")

p.terminate()