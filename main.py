#import libraries
import csv
from datetime import datetime, timedelta
from logzero import logger, logfile
from pathlib import Path
from time import sleep
from sense_hat import SenseHat
from PIL import Image
import os
from picamera import PiCamera
from orbit import ISS
from gpiozero import CPUTemperature

#initialize the number of images
counter = 0 
#minimum value of the RGB average of the photo's pixels to discard it (if the average is less than 60 it means that it is black, so it must be discarded)
min_value = 60
#initial size of the folder
size = 0 
#maxium folder size
max_size = 3060

#create csv for data    
def create_csv():
    #create csv file 
    with open(data_file, 'w', buffering=1) as f:
        writer = csv.writer(f)
        #write headers
        header = ("Counter","Date/time", "External temp", "CPU Temp", "Accelerometer (x,y,z)", "Magnetometer Edited",'Magnetometer Raw', 'Gyroscope')
        writer.writerow(header)
    
#append data to csv   
def append_data(ext_temp, cpu_temp, acc, magnetometer_edited, magnetometer_raw, gyroscope):
    with open(data_file, 'a', buffering=1) as f:
        writer = csv.writer(f)
        row = (counter, datetime.now(), ext_temp, cpu_temp, acc, magnetometer_edited, magnetometer_raw, gyroscope )
        writer.writerow(row)
        f.close()
        
#get data
def get_data():
    #get accelerometer data
    acceleration = sense.get_accelerometer_raw() 
    x = acceleration['x']
    y = acceleration['y']
    z = acceleration['z']
    #rounding to the number of decimal places chosen
    x=round(x, 3)
    y=round(y, 3)
    z=round(z, 3)
    acc=(x,y,z)
    #get magnetometer data edited
    north = sense.get_compass() 
    #get magnetometer data raw
    raw = sense.get_compass_raw() 
    magnetometer_raw=("x: {x}, y: {y}, z: {z}".format(**raw))
    #get gyroscope data
    orientation= sense.get_orientation_degrees() 
    gyroscope=("p: {pitch}, r: {roll}, y: {yaw}".format(**orientation))
    #get external temperature
    ext_temp = sense.get_temperature_from_humidity() 
    #get cpu temperature
    cpu_temp = CPUTemperature() 
    #write the data on csv
    append_data(ext_temp, cpu_temp, acc,north,magnetometer_raw,gyroscope)
    
#convert a `skyfield` Angle to an EXIF-appropriate representation (rationals)    
def convert(angle): 
    sign, degrees, minutes, seconds = angle.signed_dms()
    exif_angle = f"{degrees:.0f}/1,{minutes:.0f}/1,{seconds*10:.0f}/10"
    return sign < 0, exif_angle

#take all the photo's pixels and returns the average of the RGB values
def avg_color(img):
    global n_of_image
    l = []
    for x in range(0,img.width):
        for y in range(0,img.height):
            pixel = img.getpixel((x,y))
            l.append(pixel)
    totR = 0
    totG = 0
    totB = 0
    for p in l:
        totR += p[0]
        totG += p[1]
        totB += p[2]
    totR = totR / (len(l))
    totG = totG / (len(l))
    totB = totB / (len(l))
    if (totR + totG + totB) < min_value: #control point
        os.remove(f"{base_folder}/img_{counter}.jpg")
        counter -= 1
        
#checking folder size
def check_size():
    global size, base_folder, max_size
    # get size
    for path, dirs, files in os.walk(base_folder):
        for f in files:
            fp = os.path.join(path, f)
            size += os.path.getsize(fp)

    #rounds bytes to megabytes
    size=round((size/1000000),2)

    if size>= max_size:
        logger.error(f"max size reached")
        exit()


def get_iss_position():
    #use `camera` to capture an `image` file with lat/long EXIF data.
    point = ISS.coordinates()
    #convert the latitude and longitude to EXIF-appropriate representations
    south, exif_latitude = convert(point.latitude)
    west, exif_longitude = convert(point.longitude)
    #set the EXIF tags specifying the current location
    camera.exif_tags['GPS.GPSLatitude'] = exif_latitude
    camera.exif_tags['GPS.GPSLatitudeRef'] = "S" if south else "N"
    camera.exif_tags['GPS.GPSLongitude'] = exif_longitude
    camera.exif_tags['GPS.GPSLongitudeRef'] = "W" if west else "E"
    

#initialize SenseHat
sense = SenseHat()
#initialize camera
camera = PiCamera()
camera.resolution = (1296,972)
camera.start_preview()
#set path where to save files
base_folder = Path(__file__).parent.resolve()
data_file = base_folder/'data.csv'
logfile(base_folder/"events.log")
create_csv()
#record the start and the current time
start_time = datetime.now()
now_time = datetime.now()

while (now_time < start_time + timedelta(minutes=178)): #difference between current and start time mustn't be more of 178 minutes (about 3 hours) 
    try:
        check_size()
        get_data()
        get_iss_position()
        camera.capture(f"{base_folder}/img_{counter}.jpg") #take the photo
        avg_color(Image.open(f"{base_folder}/img_{counter}.jpg"))
        #log event
        logger.info(f"iteration {counter}")
        counter += 1
        #update the current time
        now_time = datetime.now()
    except Exception as e: #if there is an error record it on the log file and break the code
        logger.error(f"{e.__class__.__name__}: {e}")
        exit()
