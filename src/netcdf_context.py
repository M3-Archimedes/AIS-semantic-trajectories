# Manipulate features from netCDF datasets

import os
import glob
import xarray as xr
import math
import shapely
import numpy as np

import sys
sys.path.append('.')

import spatiotemporal


def read_netcdf_data(netcdf_path):
    """Reads multiple netCDF files (meteorological, bythometry, etc.) from the given path. 

    Args:
        netcdf_path (string): The path where the NetCDF files are available.

    Returns:
        A dataset containing all features extracted from the input netCDF file(s).
    """ 
    return xr.merge([xr.open_dataset(f) for f in glob.glob(os.path.join(netcdf_path,'*.nc'))])


def msToBeaufort(wind_speed_ms):
    """Converts the given wind speed from meters/sec to Beaufort scale. 

    Args:
        wind_speed_ms (float): The wind speed in meters/sec.

    Returns:
        A float indicating the wind speed in the Beaufort scale.
    """  
    return math.ceil(math.cbrt(math.pow(wind_speed_ms/0.836, 2)))


def calc_wind_conditions_polyline(cdfData, line_geom, CELL_SIZE=0.111):
    """Outlines the wind conditions (wind force in Beaufort scale, direction) across the given polyline that represents the course of a vessel. 

    Args:
        cdfData (Dataset): The dataset containing all meteorological features available in the NetCDF files.
        line_geom (LineString): A polyline geometry that represents (a part of) the course of a vessel at sea.
        CELL_SIZE (float): The granularity of the meteorological data; default cell size (in degrees) is 0.111 (copernicus).

    Returns:
        A tuple of two values: the wind force in the Beaufirt scale, and the general direction of the wind along the given course.
    """  

    # Extract features from the NetCDF data
    X = cdfData.lon               #longitude array
    Y = cdfData.lat               #latitude array
    S = cdfData.wind_speed[0]     #wind speed array (values in meters/sec)
    W = cdfData.wind_to_dir[0]    #wind direction (in degrees)

    B = []    # List of Beaufort values for wind speed across the given course
    D = []    # List of wind directions across the given course
    # Sample the polyline based on the given granularity
    for k in range(math.ceil(line_geom.length/CELL_SIZE)):
        p = shapely.line_interpolate_point(line_geom, k*CELL_SIZE)  # sample point
        s = S.sel(lat=p.y, lon=p.x,method='nearest').data.item()  # wind speed in m/s
        if not np.isnan(s):
            b = msToBeaufort(s) #Convert wind speed to Beaufort
            B.append(b)  
            w = W.sel(lat=p.y, lon=p.x,method='nearest').data.item()  # wind direction in degrees
            D.append(spatiotemporal.bearing2direction(w))  # wind direction

    if len(B)>0:
        # Report the most frequent values from the two lists
        return max(set(B), key = B.count), max(set(D), key = D.count)
    else:
        return None,''


def calc_bythometry_polyline(cdfData, line_geom, CELL_SIZE=0.111):
    """Outlines the seabed depth across the given polyline that represents the course of a vessel. 

    Args:
        cdfData (Dataset): The dataset containing bythometry (sea depth) features available in the NetCDF files.
        line_geom (LineString): A polyline geometry that represents (a part of) the course of a vessel at sea.
        CELL_SIZE (float): The granularity of the bythometry data; default cell size (in degrees) is 0.111 (copernicus).

    Returns:
        A tuple of two values: the wind force in the Beaufirt scale, and the general direction of the wind along the given course.
    """  

    X = cdfData.lon               #longitude array
    Y = cdfData.lat               #latitude array
    E = cdfData.elevation         #sea depth (values in meters)

    B = []           # List of sea depth values across the given course
    # Sample the polyline based on the given granularity
    for k in range(math.ceil(line_geom.length/CELL_SIZE)):
        p = shapely.line_interpolate_point(line_geom, k*CELL_SIZE)  # sample point
        e = E.sel(lat=p.y, lon=p.x,method='nearest').data.item()  # sea depth in meters
        if not np.isnan(e) and e<0:  # Allow only negative values for sea depth
            B.append(e)  
    
    if len(B)>0:
        # Report the minimum depth value across this course
        return max(B)  # minimum depth = maximum of negative values
    else:
        return None

