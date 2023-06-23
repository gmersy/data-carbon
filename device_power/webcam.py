import cv2
import json
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import os

plt.style.use('seaborn-v0_8-paper')

class VideoEmbodiedCarbon:
    def __init__(self, video_file, num_frames):
        self._video_file = video_file
        self._num_frames = num_frames
        self._data_item = {'file_path': self._video_file, 'embodied_carbon': 0.0, 'operational_carbon': 0.0}
    
    def capture_webcam(self, num_frames):
        cap = cv2.VideoCapture(0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        frame_id = 1
        while(cap.isOpened()):
            ret, frame = cap.read()
            if ret:
                cv2.imwrite('device_power/video_frames/frame_{}.jpg'.format(frame_id), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if frame_id-1 == num_frames:
                    break
            else:
                break
            frame_id += 1
        cap.release()
        cv2.destroyAllWindows()
    
    def clean_up(self):
        for filename in os.listdir('device_power/video_frames'):
            os.remove('device_power/video_frames/{}'.format(filename))


    def sense_and_encode(self):
        self._start_capture = datetime.now()
        self.capture_webcam(self._num_frames)
        self._end_capture = datetime.now()
    
    def parse_power_data(self, power_file, sample_rate):
        df = pd.read_csv(power_file, engine='python', delimiter='","')
        df.drop(df.tail(11).index, inplace = True)
        df.head()
        df.replace('"', '', regex=True, inplace=True)
        df.rename(columns={'"System Time': 'System Time'}, inplace=True)

        df['System Time'] = [value[:-3]+str(int(value.split(':')[-1])*1000) for value in df['System Time'].tolist()]

        df['System Time'] = pd.to_datetime(df['System Time'], format="%H:%M:%S:%f").dt.time
        # guarantees ordering 
        df = df.sort_values(by=['Elapsed Time (sec)'])
        read_times = [datetime.combine(datetime.today(), df['System Time'].values[0])]
        # assume that the sensor is read at the refresh interval and the log has a i/o delay
        for i in range(1, df.shape[0]):
            read_times.append(read_times[0] + timedelta(milliseconds=i*sample_rate))

        df['ReadTime'] = read_times
        df.rename(columns={'ReadTime': 'Time'}, inplace=True)

        self._relevant_data = df[['Time', 'System Time', 'CPU Utilization(%)', 'Processor Power_0(Watt)', 'DRAM Power_0(Watt)']]


    def query_power_data(self, start_time, end_time):
        return self._relevant_data[(self._relevant_data['Time'] >= start_time) & (self._relevant_data['Time'] <= end_time)]

    @staticmethod
    def power_plot(view, task, outfile, rot=False):
        view_copy = view.set_index('Time')
        if rot:
            view_copy.plot(kind='line', subplots=True, grid=True, layout=(3, 1), sharex=True, legend=True, rot=45)
        
        else:
            view_copy.plot(kind='line', subplots=True, grid=True, layout=(3, 1), sharex=True, legend=True)
        # plt.savefig(outfile, dpi=600, bbox_inches="tight")
        plt.savefig(outfile, dpi=600)
    
    def energy(self, view, sample_rate, unit = 'KWh'):
        joules_wattsecs = ((sample_rate/1000)*(view['Processor Power_0(Watt)'] + view['DRAM Power_0(Watt)'])).sum()
        return joules_wattsecs if unit != 'KWh' else joules_wattsecs/3600000 

    def empirical_energy(self, view, sample_rate, unit = 'KWh'):
        timestamps = view['System Time']
        timedeltas = [timedelta(hours=x.hour, minutes=x.minute, seconds=x.second, microseconds=x.microsecond) for x in timestamps.tolist()]
        deltas = [timedelta(microseconds=sample_rate).total_seconds()]
        diffs = [delta.total_seconds() for delta in pd.Series(timedeltas).diff().to_list()]
        deltas.extend(diffs[1:])
        joules_wattsecs = (deltas*(view['Processor Power_0(Watt)'] + view['DRAM Power_0(Watt)'])).sum()
        return joules_wattsecs if unit != 'KWh' else joules_wattsecs/3600000
    
    def carbon(self, energy, carbon_intensity):
        return energy*carbon_intensity
    
    def embodied(self, carbon):
        self._data_item['embodied_carbon'] += carbon
    
    def serialize_data_item(self, outfile):
        with open(outfile, 'w') as f:
            json.dump(self._data_item, f)
        
if __name__ == '__main__':
    power_sample_rate = int(input("What is the power sampling rate in milliseconds?\n"))
    current_carbon_intensity = float(input("What is the current carbon intensity?\n"))
    video_file = 'device_power/video_test.mp4'
    num_frames = 100
    provenance = VideoEmbodiedCarbon(video_file, num_frames)
    provenance.sense_and_encode()

    power_file = input("First terminate the power logging. Now, what is the path of the power file?\n")
    provenance.parse_power_data(power_file, power_sample_rate)

    print('Sense time:', provenance._end_capture-provenance._start_capture)

    sensing = provenance.query_power_data(provenance._start_capture, provenance._end_capture)
    provenance.power_plot(sensing, 'Webcam Sensing', 'figs/video_power.png')
    sense_energy = provenance.energy(sensing, power_sample_rate)
    sense_carbon = provenance.carbon(sense_energy, current_carbon_intensity)
    print('Sense energy:', sense_energy)
    print('Sense carbon:', sense_carbon)
    provenance.embodied(sense_carbon)
    provenance.serialize_data_item('carbon_accountant/video_carbon.json')
