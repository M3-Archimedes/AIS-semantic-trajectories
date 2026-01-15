# Functions for computing auxiliary spatio-temporal features

import math
import numpy as np
from shapely.geometry import Point, Polygon, LineString, shape, box
from haversine import haversine, Unit


def get_bbox(df, col_x='x', col_y='y'):
    """Calculates the Minimum Bounding Box enclosing all points in the given DataFrame. 
        Assuming that columns named x, y represent lon/lat coordinates.

    Args:
        df (DataFrame): A DataFrame containing the (lon/lat) coordinates of the points.
        col_x (string): The name of the column with x-ordinates (longitude values).
        col_y (string): The name of the column with y-ordinates (latitude values).

    Returns:
        A rectangle (box) that represents the MBR of the given DataFrame.
    """
    
    # Calculate bounding box
    minx = df.min(axis=0)[col_x]
    miny = df.min(axis=0)[col_y]
    maxx = df.max(axis=0)[col_x]
    maxy = df.max(axis=0)[col_y]
    
    return box(minx, miny, maxx, maxy)


def get_bbox(gdf):
    """Calculates the Minimum Bounding Box enclosing all points in the given GeoDataFrame. 

    Args:
        gdf (GeoDataFrame): A GeoDataFrame containing spatial geometries.

    Returns:
        A rectangle (box) that represents the MBR of the given GeoDataFrame.
    """
    
    # Calculate bounding box
    minx, miny, maxx, maxy = gdf.geometry.total_bounds
    
    return box(minx, miny, maxx, maxy)


def get_centroid(points):
    """Calculates the coordinates of the centroid of the given list of point lon/lat locations. 

    Args:
        points (list): A list of point geometries.

    Returns:
        A pair of lon/lat coordinates representing the calculated centroid.
    """
    x = 0
    y = 0
    for p in points:
        x += p.x
        y += p.y
    return Point(x/len(points), y/len(points))


def length_haversine(polyline):
    """Calculates the length of the given polyline in nutical miles according to the Haversine distance between consecutive points in the sequence. 

    Args:
        polyline (LineString): A polyline geometry.

    Returns:
        The length of the polyline in nautical miles.
    """

    d = 0.0
    q = None
    # Calculate the haversine distance between each pair of consecutive points
    for p in polyline.coords:
        if q:
            d += haversine((p[1], p[0]), (q[1], q[0]), unit=Unit.NAUTICAL_MILES)   
        q = p
        
    return d   # Haversine distance in NAUTICAL MILES


def get_bearing(lon1, lat1, lon2, lat2):
    """Calculates the bearing (i.e., direction of movement) from a point location to another point location. Both locations are given in lon/lat coordinates. 

    Args:
        lon1 (float): Longitude of the first point.
        lat1 (float): Latitude of the first point.
        lon2 (float): Longitude of the second point.
        lat2 (float): Loatitude of the second point.

    Returns:
        A float (ranging from -180 to 180) indicating the calculated bearing.
    """    
    dLon = (lon2 - lon1)
    x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
    y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(dLon))
    brng = np.arctan2(x,y)
    brng = np.degrees(brng)

    return float(brng)


def get_direction(lon1, lat1, lon2, lat2):
    """Calculates the general direction of movement from a point location to another point location. Both locations are given in lon/lat coordinates. 

    Args:
        lon1 (float): Longitude of the first point.
        lat1 (float): Latitude of the first point.
        lon2 (float): Longitude of the second point.
        lat2 (float): Loatitude of the second point.

    Returns:
        A string indicating the calculated direction.
    """  
    # Assuming 8 basic directions of interest
    directions = ["North", "North East", "East", "South East", "South", "South West", "West", "North West"]
    
    bearing = get_bearing(lon1, lat1, lon2, lat2)
    bearing += 22.5
    bearing = bearing % 360
    bearing = int(bearing / 45) # values 0 to 7
    direction = directions [bearing]

    return direction.upper()


def bearing2direction(bearing):
    """Converts the given bearing to a general direction of movement. 

    Args:
        bearing (float): The bearing of movement.

    Returns:
        A string indicating the general direction of movement.
    """  
    # Assuming 8 basic directions of interest
    directions = ["North", "North East", "East", "South East", "South", "South West", "West", "North West"]
    
    bearing += 22.5
    bearing = bearing % 360
    bearing = int(bearing / 45) # values 0 to 7
    direction = directions [bearing]

    return direction.upper()


