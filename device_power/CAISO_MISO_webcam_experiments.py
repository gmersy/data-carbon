from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import random
import time
plt.style.use('seaborn-v0_8-paper')
from webcam import VideoEmbodiedCarbon

class VideoExperiment(VideoEmbodiedCarbon):
    def __init__(self, video_path, num_frames):
        super().__init__(video_path, num_frames)
    
    def set_relevant_data(self, relevant_data):
        self._relevant_data = relevant_data
    
    @staticmethod
    def get_miso_carbon_intensities():
        day = pd.read_csv("carbon_intensity_pricing/12_01_2022.csv", thousands=',')

        dfs = [day]
        for i in range(len(dfs)):
            dfs[i] = dfs[i].drop(axis=1, columns=['Other', 'Storage'])
            datetimes, grid_carbon_intensities = [], []
            for hour in dfs[i]['Hour']:
                datetimes.append(datetime(2022, 12, i+1, hour-1))
            
            dfs[i] = dfs[i].drop(axis=1, columns=['Hour'])

            dfs[i]['Time'] = datetimes


        full = pd.concat(dfs, axis=0)
        full = full.set_index('Time')
        full[full.columns] = full[full.columns].astype('float64')
        total = full['Coal'] + full['Gas'] + full['Wind'] + full['Nuclear'] + full['Solar'] + full['Hydro']

        full['MISO g CO2 e/KWh'] = (1/total)*(CARBON_INTENSITIES_MISO['Coal']*full['Coal'] + \
        CARBON_INTENSITIES_MISO['Gas']*full['Gas'] + CARBON_INTENSITIES_MISO['Wind']*full['Wind'] + \
        CARBON_INTENSITIES_MISO['Nuclear']*full['Nuclear'] \
        + CARBON_INTENSITIES_MISO['Solar']*full['Solar'] + CARBON_INTENSITIES_MISO['Hydro']*full['Hydro'])

        return full['MISO g CO2 e/KWh'].values
   
    @staticmethod
    def get_caiso_carbon_intensities():
        nov30_rens = pd.read_csv('carbon_intensity_pricing/raw CAISO/CAISO-renewables-20221130.csv', index_col=0, header=None).T
        nov30_other = pd.read_csv('carbon_intensity_pricing/raw CAISO/CAISO-supply-20221130.csv', index_col=0, header=None).T
        dec1_rens = pd.read_csv('carbon_intensity_pricing/raw CAISO/CAISO-renewables-20221201.csv', index_col=0, header=None).T
        dec1_other = pd.read_csv('carbon_intensity_pricing/raw CAISO/CAISO-supply-20221201.csv', index_col=0, header=None).T

        nov30_rens.rename(columns={nov30_rens.columns[0]: 'Time'}, inplace=True)
        nov30_other = nov30_other.rename(columns={nov30_other.columns[0]: 'Time'}, inplace=False).dropna()

        dec1_rens.rename(columns={dec1_rens.columns[0]: 'Time'}, inplace=True)
        dec1_other = dec1_other.rename(columns={dec1_other.columns[0]: 'Time'}, inplace=False).dropna()

        nov30_rens['Time'] = [datetime.combine(datetime(2022, 11, 30), time) for time in pd.to_datetime(nov30_rens['Time']).dt.time.tolist()]
        nov30_other['Time'] = [datetime.combine(datetime(2022, 11, 30), time) for time in pd.to_datetime(nov30_other['Time']).dt.time.tolist()]

        dec1_rens['Time'] = [datetime.combine(datetime(2022, 12, 1), time) for time in pd.to_datetime(dec1_rens['Time']).dt.time.tolist()]
        dec1_other['Time'] = [datetime.combine(datetime(2022, 12, 1), time) for time in pd.to_datetime(dec1_other['Time']).dt.time.tolist()]

        nov30 = pd.merge(nov30_rens, nov30_other, on='Time')
        dec1 = pd.merge(dec1_rens, dec1_other, on='Time')

        full = pd.concat([nov30, dec1], axis=0)
        full.set_index('Time', inplace=True)

        full = full.astype(float)
        full[full < 0] = 0
        full = full.loc['2022-11-30 21:00:00':'2022-12-01 20:00:00']
        full = full.resample('H').mean()

        total = full["Coal"] + full["Natural gas"] + full["Wind"] + full["Nuclear"] + full["Solar"] + full["Small hydro"] + full["Large hydro"] + full["Biomass"] + full["Geothermal"] + full["Biogas"] + full["Imports"]
        
        full["CAISO g CO2 e/kWh"] = (1/total)*(full["Coal"] * CARBON_INTENSITIES_CAISO["Coal"] + full["Natural gas"] * CARBON_INTENSITIES_CAISO["Natural gas"] \
            + full["Wind"] * CARBON_INTENSITIES_CAISO["Wind"] + full["Nuclear"] * CARBON_INTENSITIES_CAISO["Nuclear"] + full["Solar"] * CARBON_INTENSITIES_CAISO["Solar"] \
                + full["Small hydro"] * CARBON_INTENSITIES_CAISO["Small hydro"] + full["Large hydro"] * CARBON_INTENSITIES_CAISO["Large hydro"] + full["Biomass"] * CARBON_INTENSITIES_CAISO["Biomass"] \
                    + full["Geothermal"] * CARBON_INTENSITIES_CAISO["Geothermal"] + full["Biogas"] * CARBON_INTENSITIES_CAISO["Biogas"] + full["Imports"] * CARBON_INTENSITIES_CAISO["Imports"]) 
        return full["CAISO g CO2 e/kWh"].values

if __name__ == '__main__':
    wait_period = 15
    power_sample_rate = int(input("What is the power sampling rate in milliseconds?\n"))

    dec1 = pd.read_csv("carbon_intensity_pricing/12_01_2022.csv", thousands=',')
    CARBON_INTENSITIES_MISO = json.load(open("MISO_carbon_intensity.json"))
    CARBON_INTENSITIES_CAISO = json.load(open("CAISO_carbon_intensity.json"))
   

    miso_ci = VideoExperiment.get_miso_carbon_intensities()
    caiso_ci = VideoExperiment.get_caiso_carbon_intensities()
    
    video_path = 'device_power/video_frames'

    trackers, szs = [], []
    frame_options = [100, 200, 400, 800]
    for i in range(24):
        num_frames = random.choice(frame_options)
        print("Progress: {}/24, number of frames: {}".format(i, num_frames))
        tracker = VideoExperiment(video_path, num_frames)
        tracker.sense_and_encode()
        sz = 0
        for file in os.listdir(video_path):
            sz += os.path.getsize(os.path.join(video_path, file))
        szs.append(sz/1000000)
        trackers.append(tracker)
        tracker.clean_up()
        time.sleep(wait_period)


    power_file = input("First terminate the power logging. Now, what is the path of the power file?\n")
    
    trackers[0].parse_power_data(power_file, power_sample_rate)

    for i in range(1, len(trackers)):
        trackers[i].set_relevant_data(trackers[0]._relevant_data)
    energy_values = []
    for tracker in trackers:
        sensing = tracker.query_power_data(tracker._start_capture, tracker._end_capture)
        sense_energy = tracker.energy(sensing, power_sample_rate, unit='J')
        energy_values.append(sense_energy)
    
    full = pd.DataFrame()
    full['HourEnding EST (12-01-2022)'] = list(range(1, 25))
    full['Energy (J)'] = energy_values
    full['CAISO g CO2 e/kWh'] = caiso_ci
    full['MISO g CO2 e/kWh'] = miso_ci
    full['File size (MB)'] = szs
    full['Sense time (s)'] = [(tracker._end_capture - tracker._start_capture).total_seconds() for tracker in trackers]
    
    
    full['MISO (mg CO2 e)'] = (full['Energy (J)']/3600000)*(full['MISO g CO2 e/kWh'])*1000
    full['CAISO (mg CO2 e)'] = (full['Energy (J)']/3600000)*(full['CAISO g CO2 e/kWh'])*1000
    
    full.to_csv('experiment_results/results.csv', index=False)

    # plot eneregy versus carbon emissions and connect CAISO to MISO
    ax = full.plot.scatter('Energy (J)','CAISO (mg CO2 e)',c="b",label="CAISO")
    full.plot.scatter('Energy (J)','MISO (mg CO2 e)',c="r",label="MISO", ax=ax)
    for n,row in full.iterrows():
        ax.plot([row['Energy (J)']]*2,row[['CAISO (mg CO2 e)', 'MISO (mg CO2 e)']], color="gray", lw=1, zorder=0, linestyle='dotted')
    
    ax.set_ylabel('Embodied carbon (mg CO2 e)')
    plt.savefig('figs/energy_carbon_scatter_CAISO_MISO.png', dpi=600)
    plt.clf()

    ax = full.plot.scatter(x='File size (MB)', y= 'Energy (J)',c="orange")
    plt.savefig('figs/energy_file_size.png', dpi=600)
    plt.clf()
