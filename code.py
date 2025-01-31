import time
import requests

import framebufferio
import terminalio
import rgbmatrix
import displayio
import board

import adafruit_display_text.label
from adafruit_bitmap_font import bitmap_font

from pprint import pprint
from datetime import datetime, timezone, timedelta

VERSION = "v1.0"

# Replace with your TfNSW OpenData API key
API_KEY = ""
STOP_ID = "" # Its recommended you fill stop ID out in advance to make refreshes faster
STATION = "" # Fill this with your station if you do not know your stop ID
PLATFORM = "" # What platform do you want the display to show?

TIME_MS = 0.1 # How much delay to perform on each tick
TIME_RE = 50 # How many ticks until the time refreshes
DATA_RE = 200 # How many ticks until the data refreshes

# tzdata module not available, so offsets are hardcoded
# (not good!!!)
TIME_ZN = 10 # How many hours to add onto UTC time
TIME_DT = 11 # How many hours to add when using daylight savings
USES_DT = True # Use daylight savings time

# Icons

icons = {
    "T": displayio.OnDiskBitmap("T.bmp"),
    "T1": displayio.OnDiskBitmap("T1.bmp"),
    "T2": displayio.OnDiskBitmap("T2.bmp"),
    "T4": displayio.OnDiskBitmap("T4.bmp"),
    "T5": displayio.OnDiskBitmap("T5.bmp"),
    "T6": displayio.OnDiskBitmap("T6.bmp"),
    "T7": displayio.OnDiskBitmap("T7.bmp"),
    "T8": displayio.OnDiskBitmap("T8.bmp"),
    "T9": displayio.OnDiskBitmap("T9.bmp")
}

# Headers

headers = {
    "Authorization": f"apikey {API_KEY}"
}

# Initialisation

current_event = {}

displayio.release_displays()

matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=1,
    rgb_pins=[board.D6, board.D5, board.D9, board.D11, board.D10, board.D12],
    addr_pins=[board.A5, board.A4, board.A3, board.A2],
    clock_pin=board.D13, latch_pin=board.D0, output_enable_pin=board.D1)

display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)

def draw_splash(version=None):
    if version == None:
        icon = displayio.TileGrid(icons["T"], pixel_shader=icons["T"].pixel_shader)
        icon.x = 28
        icon.y = 12
        group = displayio.Group()
        group.append(icon)
    else:
        text = adafruit_display_text.label.Label(
            small_font,
            color=0xffffff,
            text = version,
            anchor_point = (0.5, 0.5),
            anchored_position = (32.0, 16.0)
        )
        group = displayio.Group()
        group.append(text)
    
    display.root_group = group
    display.refresh(minimum_frames_per_second=0)

def time_left(target_iso):
    target_time = datetime.fromisoformat(target_iso.replace("Z", "+00:00"))
    current_time = datetime.now(timezone.utc)
    time_diff = target_time - current_time

    if time_diff.total_seconds() <= 0:
        return 0, 0

    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return hours, minutes

def get_time():
    if USES_DT:
        now = datetime.now() + timedelta(hours=TIME_DT)
    else:
        now = datetime.now() + timedelta(hours=TIME_ZN)
        
    return now.strftime("%H:%M")

# Get global station ID from string if stop_id not provided

def get_stop_id(station):
    url = "https://api.transport.nsw.gov.au/v1/tp/stop_finder"
        
    params = {
        'outputFormat': 'rapidJSON',
        'type_sf': 'stop',
        'name_sf': station,
        'coordOutputFormat': 'EPSG:4326'
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        locations = data.get("locations", [])
        if locations:
            id = locations[0].get("id")
            print(f"Found stop ID: {id} for {station}")
            return id
        else:
            print("Failed to obtain STOP_ID")
            return None
    else:
        print(f"Response returned {response.status_code}")
        return None


# Get departures

def update_departures(id, platform):
    url = "https://api.transport.nsw.gov.au/v1/tp/departure_mon"

    params = {
        # https://opendata.transport.nsw.gov.au/data/dataset/trip-planner-apis/resource/917c66c3-8123-4a0f-b1b1-b4220f32585d/view/7c21e37e-5c4c-4085-91b7-5cffee8a44c0
        "outputFormat": "rapidJSON",
        "coordOutputFormat": "EPSG:4326",
        "mode": "direct",
        "type_dm": "platform",
        "name_dm": id,
        "departureMonitorMacro": "true",
        "excludedMeans": "checkbox", # Enable multiple exclusions
        "exclMOT_2": "1", # Exclude metro
        "exclMOT_4": "1", # Exclude light rail
        "exclMOT_5": "1", # Exclude bus
        "exclMOT_7": "1", # Exclude coach
        "exclMOT_9": "1", # Exclude ferry
        "exclMOT_11": "1", # Exclude school bus
        "TfNSWDM": "true",
        "version": "10.2.1.42"
    }

    response = requests.get(url, headers=headers, params=params)
    json = response.json()
    if json["locations"] != []:
        events = []
        for event in json["stopEvents"]:
            name = event["location"]["parent"]["disassembledName"].split(", ")
            station_platform = name[1].replace("Platform ", "")
            if station_platform == platform:
                events.append(event)

        if events != []:
            global current_event
            current_event = events[0]
        else:
            print("no events found")

def get_stops(origin_id, stop_id, line):
    url = "https://api.transport.nsw.gov.au/v1/tp/trip"

    print(origin_id, stop_id)
    
    params = {
        "outputFormat": "rapidJSON",
        "coordOutputFormat": "EPSG:4326",
        "depArrMacro": "dep",
        "mode": "direct",
        "type_origin": "any",
        "name_origin": origin_id,
        "type_destination": "any",
        "name_destination": stop_id,
        "excludedMeans": "checkbox", # Enable multiple exclusions
        "exclMOT_2": "1", # Exclude metro
        "exclMOT_4": "1", # Exclude light rail
        "exclMOT_5": "1", # Exclude bus
        "exclMOT_7": "1", # Exclude coach
        "exclMOT_9": "1", # Exclude ferry
        "exclMOT_11": "1", # Exclude school bus
        "version": "10.2.1.42"
    }
    
    # Make the request
    response = requests.get(url, params=params, headers=headers)
    
    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        # Extract and print the list of stops
        stops = []
        best_fit_journey = None
        if data.get("journeys"):
            for journey in data.get('journeys', []):
                print(journey["legs"][0]["transportation"].get("disassembledName"))
                if journey.get("interchanges") == 0 and journey["legs"][0]["transportation"].get("disassembledName") == line:
                    best_fit_journey = journey
                    break

            if best_fit_journey == None:
                return []

            for leg in best_fit_journey.get('legs', []):
                for stop in leg.get('stopSequence', []):
                    stops.append(stop.get("name").split(",")[0].replace("Station", ""))

        stops.pop(0)
        print(stops)
        return stops
    else:
        print(f"Error: {response.status_code}")
        return []
               

# draw!!

draw_splash()

small_font = bitmap_font.load_font("lemon.bdf")
eta_text = None
time_text = None
station_list = None
station_list_height = 0
bottom_clip = None

def draw_display(event):
    print("draw", event)
    if event != {}:
        if icons.get(event["transportation"]["disassembledName"]): # disassembledName is T1, T2, T3... etc
            icon = icons[event["transportation"]["disassembledName"]]
        else:
            print("No icon implemented", event["transportation"]["disassembledName"])
            icon = icons["T"]

        if event.get("departureTimeEstimated"):
            print("estimated")
            hours, minutes = time_left(event["departureTimeEstimated"])
        else:
            print("planned")
            hours, minutes = time_left(event["departureTimePlanned"])

        stops = get_stops(STOP_ID, current_event["transportation"]["destination"]["id"], event["transportation"]["disassembledName"])

        global station_list
        station_list = displayio.Group()
        station_list.y = 15

        global station_list_height
        station_list_height = 9 * len(stops)
        
        for index, stop in enumerate(stops):
            stop_text = adafruit_display_text.label.Label(
                small_font,
                color=0xc8c8c8,
                text=stop
            )
            stop_text.x = 0
            stop_text.y = 9 * index
            station_list.append(stop_text)

        top_bitmap = displayio.Bitmap(64, 10, 1)
        bottom_bitmap = displayio.Bitmap(64, 8, 1)
        
        palette = displayio.Palette(1)
        palette[0] = 0x000000
        
        top_clip = displayio.TileGrid(top_bitmap, pixel_shader=palette)
        top_clip.x = 0
        top_clip.y = 0

        global bottom_clip
        bottom_clip = displayio.TileGrid(bottom_bitmap, pixel_shader=palette)
        bottom_clip.x = 0
        bottom_clip.y = 24

        destination = event["transportation"]["destination"]["name"].split("via")[0].replace("Station", "")
        destination_text = adafruit_display_text.label.Label(
            small_font,
            color=0xffffff,
            text=destination
        )
        destination_text.x = 9
        destination_text.y = 4
        
        icon = displayio.TileGrid(icon, pixel_shader=icon.pixel_shader)
        icon.x = 1
        icon.y = 1

        global time_text
        time_text = adafruit_display_text.label.Label(
            small_font,
            color=0xffffff,
            text = "12:00",
        )
        time_text.y = 27
        time_text.text = get_time()

        if hours != 0:
            bottom_clip.hidden = False
            time_text.text = "" 
            eta_string = f"{hours} hr {minutes} min"
        elif minutes != 0:
            bottom_clip.hidden = False
            eta_string = f"{minutes} min"
        else:
            bottom_clip.hidden = True
            eta_string = ""
        
        global eta_text
        eta_text = adafruit_display_text.label.Label(
            small_font,
            color=0xffffff,
            text = eta_string,
            anchor_point = (1.0, 1.0),
            anchored_position = (63.0, 31.0)
        )
        
        group = displayio.Group()
        group.append(station_list)
        group.append(top_clip)
        group.append(bottom_clip)
        group.append(destination_text)
        group.append(icon)
        group.append(eta_text)
        group.append(time_text)
        
        display.root_group = group
    else:
        icon = displayio.TileGrid(icons["T"], pixel_shader=icons["T"].pixel_shader)
        icon.x = 56
        icon.y = 24

        body_text = adafruit_display_text.label.Label(
            small_font,
            color=0xffffff,
            text="No Data")
        body_text.x = 0
        body_text.y = 27

        group = displayio.Group()
        group.append(icon)
        group.append(body_text)
        display.root_group = group

if STOP_ID == "":
    STOP_ID = get_stop_id(STATION)

time_ticks = 0
data_ticks = 0

update_departures(STOP_ID, PLATFORM)

draw_splash(VERSION)

draw_display(current_event)

while True:
    if current_event != {}:
        if time_ticks >= TIME_RE:
            time_text.text = get_time()
            
            if current_event.get("departureTimeEstimated"):
                print("estimated")
                hours, minutes = time_left(current_event["departureTimeEstimated"])
            else:
                print("planned")
                hours, minutes = time_left(current_event["departureTimePlanned"])
    
            if hours != 0:
                bottom_clip.hidden = False
                time_text.text = "" 
                eta_text.text = f"{hours} hr {minutes} min"
            elif minutes != 0:
                bottom_clip.hidden = False
                eta_text.text = f"{minutes} min"
            else:
                bottom_clip.hidden = True
                eta_text.text = ""
                time_text.text = ""
                
            time_ticks = 0
    
        if data_ticks >= DATA_RE:
            prev_event = current_event
            update_departures(STOP_ID, PLATFORM)
            if prev_event["properties"]["RealtimeTripId"] != current_event["properties"]["RealtimeTripId"]:
                print("update")
                draw_display(current_event)
            data_ticks = 0
 
        station_list.y = station_list.y - 1

        if station_list.y * -1 > station_list_height:
            station_list.y = 64
        
        time_ticks += 1
        data_ticks += 1

    time.sleep(TIME_MS)
    display.refresh(minimum_frames_per_second=0)