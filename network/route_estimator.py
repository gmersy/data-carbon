import requests
import subprocess
import geopandas as gpd
from shapely.geometry import Point, LineString
import pandas as pd
import matplotlib.pyplot as plt
import time
import json
import datetime

class RouteTracer:
    def __init__(self, co2_signal_api_key):
        # Aslan 2015 extrapolation 
        self._estimate_kWh_per_GB = 0.06 * 0.5**((datetime.date.today().year - 2015)//2)
        self._private_ip_prefixes = ['10', '172', '192']

        self.co2_signal_api_key = co2_signal_api_key

    def geolocate_ip(self, ip_address, hop_id):
        response = requests.get(f'https://ipapi.co/{ip_address}/json/').json()
        location_data = {
            "hop_id": hop_id,
            "latitude": response.get("latitude"),
            "longitude": response.get("longitude"),
        }
        return location_data
    
    def get_carbon_intensity(self, lat, long):
        response = requests.get(f'https://api.co2signal.com/v1/latest?lat={lat}&lon={long}', headers={'auth-token': self.co2_signal_api_key}).json()
        return response['data']['carbonIntensity']

    def run_traceroute(self, domain, queries):
        return subprocess.check_output(['traceroute', '-q', str(queries), domain])
    
    def parse_traceroute_single(self, traceroute_output):
        lines = traceroute_output.decode('utf-8').split('\n')
        ips = []
        rtts = []
        for line in lines:
            if '*' in line:
                continue
            elif not line:
                break

            splt = line.split()

            for s in splt:
                if '(' in s and ')' in s:
                    ip = s.replace("(", "").replace(")", "")
                    if not ip.split('.')[0] in self._private_ip_prefixes:
                        ips.append(ip)
                elif s.replace('.', '', 1).isdigit() and s.count('.') == 1:
                    rtts.append(float(s))
                else:
                    continue
        return ips, rtts
    

    def categories(self, ci):
        ci_cats = []

        for c in ci:
            if c <= 200.0:
                ci_cats.append("0 - 200")
            elif c <= 400:
                ci_cats.append("200 - 400")
            elif c <= 600:
                ci_cats.append("400 - 600")
            elif c > 600:
                ci_cats.append("> 600")
        return ci_cats

    def plot(self, outfile, lats, longs, ci, config = {'World': True, 'Continent': False, 'Country': False}, map_query = None):
        if sum(config.values()) > 1:
            raise ValueError("Only one of the following can be true: World, Continent, Country")
        
        points = [Point(x, y) for x, y in zip(longs, lats)]
        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))

        line_strings = []
        for idx, point in enumerate(points):
            if idx == 0:
                continue
            line_strings.append(LineString([points[idx-1], point]))

        gdf = gpd.GeoDataFrame(geometry=line_strings)

        cats = self.categories(ci)

        df = pd.DataFrame({"Points": points, "Carbon Intenisty (g CO2 e/kWh)": ci, "Carbon Intensity Category": cats})
        gdf2 = gpd.GeoDataFrame(df, geometry="Points")
        
        fig, ax = plt.subplots(figsize=(10, 10))
        if config['World']:
            world.plot(ax=ax, color="silver")
        
        elif config['Continent']:
            world.query(f"continent == '{map_query}'").plot(ax=ax, color="grey")
        
        else:
            world.query(f"name == '{map_query}'").plot(ax=ax, color="grey")
        
        gdf.plot(ax = ax, color='black', linestyle="dashed")

        gdf2.plot(ax = ax, column = "Carbon Intensity Category",
                markersize = gdf2['Carbon Intenisty (g CO2 e/kWh)']/2.0 +50,
                categorical=True, legend=True)
        leg1 = ax.get_legend()
        leg1.set_title("Carbon Intensity (g CO2 e/kWh)")
        plt.tick_params(left = False, right = False , labelleft = False ,
                        labelbottom = False, bottom = False)

        data_transfer_carbon_intenisty =  sum(ci)/len(ci)*self._estimate_kWh_per_GB

        with open('network/result.json', 'w') as fd:
            json.dump({'g CO2 e/GB': data_transfer_carbon_intenisty}, fd)

        print('g CO2 e/GB: {}'.format(data_transfer_carbon_intenisty))
        plt.savefig(outfile, dpi=600, bbox_inches="tight")

        

    
    def run(self, domain, queries, outfile, map_query = None, config = {'World': True, 'Continent': False, 'Country': False}):
        traceroute_output = self.run_traceroute(domain, queries)
        ips, rtts = self.parse_traceroute_single(traceroute_output)
        lats, longs, ci = [], [], []
        for idx, ip in enumerate(ips):
            location_data = self.geolocate_ip(ip, idx)
            lats.append(location_data['latitude'])
            longs.append(location_data['longitude'])
            ci.append(self.get_carbon_intensity(location_data['latitude'], location_data['longitude']))
            #no more than 1 request per second
            time.sleep(1.1)
        self.plot(outfile, lats, longs, ci, config, map_query)


    def parse_traceroute_multiple(self, traceroute_output):
        lines = traceroute_output.decode('utf-8').split('\n')
        ips = []
        avg_rtt = []
        redundant_links, star_lines = 0, 0
        for idx, line in enumerate(lines):
            if '*' in line:
                star_lines += 1
                continue
            elif not line:
                break

            splt = line.split()

            rtts = []
            for s in splt:
                if '(' in s and ')' in s:
                    ip = s.replace("(", "").replace(")", "")
                elif s.replace('.', '', 1).isdigit() and s.count('.') == 1:
                    rtts.append(float(s))

            if splt[0].isdigit() and len(splt[0]) == 1:
                last_num_idx = idx - star_lines - redundant_links
                ips.append([ip])
                avg_rtt.append([sum(rtts)/len(rtts)])
            else:
                ips[last_num_idx].append(ip)
                avg_rtt[last_num_idx].append(sum(rtts)/len(rtts))
                redundant_links += 1
        return ips, avg_rtt



        

if __name__ == '__main__':
    key = input("What is your co2signal API key?")
    tracer = RouteTracer(key)
    tracer.run('instagram.com', 1, 'figs/route.png', map_query = 'North America', config = {'World': True, 'Continent': False, 'Country': False})
