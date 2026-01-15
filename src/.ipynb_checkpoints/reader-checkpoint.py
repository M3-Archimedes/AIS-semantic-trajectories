# Auxiliary functions for manipulating AIS trajectory data

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString, shape, box


def read_point_dataset(file_path, col_x='x', col_y='y', crs='epsg:4326', sep=','):
    """Creates a GeoDataFrame of point locations from the x,y coordinates contained in the given CSV file. 

    Args:
        file_path (string): The path to the input CSV file.
        col_x (string): The name of the column with the x ordinates.
        col_y (string): The name of the column with the y ordinates.
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
        sep (string): The character used as separator in the CSV file. 
                
    Returns:
        A GeoDataFrame with the locations as point geometries.
    """
    
    df = pd.read_csv(file_path, sep=sep)

    # Convert the coordinates into points and create a GeoDataFrame in the specified CRS
    geometry = [Point(xy) for xy in zip(df[col_x], df[col_y])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=crs)

    return gdf


def read_ais_locations(file_path, col_lon='LONGITUDE', col_lat='LATITUDE', col_ts='TIMESTAMP', sep=',', crs='epsg:4326'):
    """Creates a GeoDataFrame from the AIS locations in lon/lat coordinates contained in the given CSV file. 

    Args:
        file_path (string): The path to the input CSV file.
        col_lon (string): The name of the column with the longitude ordinates.
        col_lat (string): The name of the column with the latitude ordinates.
        col_ts (string): The name of the column with the timestamps (in date/time format).
        sep (string): The character used as separator in the CSV file. 
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
                
    Returns:
        A GeoDataFrame with the locations as point geometries chronologically ordered by UNIX epochs (in seconds).
    """
    
    df = pd.read_csv(file_path, sep=sep).drop_duplicates()

    # Check timestamps
    if df[col_ts].astype(str).str.isnumeric().all(): # Numeric timestamps
        df[col_ts] = df[col_ts].astype(int)
    else: # Turn timestamps into UNIX epochs (seconds) in an extra column
        df[col_ts] = pd.to_datetime(df[col_ts])
        df['t'] = df[col_ts].apply(lambda x: x.timestamp()).astype(int)

    # Convert the coordinates into points and create a GeoDataFrame in WGS84
    geometry = [Point(xy) for xy in zip(df[col_lon], df[col_lat])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=crs)
    gdf.sort_values(col_ts)

    return gdf



def read_annotated_ais_locations(file_path, col_id='MMSI', col_lon='LONGITUDE', col_lat='LATITUDE', col_ts='TIMESTAMP', col_heading='HEADING', col_anno='ANNOTATION', sep=',', crs='epsg:4326'):
    """Creates a GeoDataFrame from the AIS locations in lon/lat coordinates along with their ANNOTATIONS contained in the given CSV file. 

    Args:
        file_path (string): The path to the input CSV file.
        col_id (string): The column containing the vessel identifiers.
        col_lon (string): The name of the column with the longitude ordinates.
        col_lat (string): The name of the column with the latitude ordinates.
        col_ts (string): The name of the column with the timestamps (in date/time format).
        col_heading (string): The name of the column with the heading (in degrees).
        col_anno (string): The name of the column with the annotations (e.g., STOP, GAP, etc.).
        sep (string): The character used as separator in the CSV file. 
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
                
    Returns:
        A GeoDataFrame with the locations as point geometries chronologically ordered by UNIX epochs (in seconds).
    """
    
    df = pd.read_csv(file_path, sep=sep).drop_duplicates()

    # Check timestamps
    if df[col_ts].astype(str).str.isnumeric().all(): # Numeric timestamps
        df[col_ts] = df[col_ts].astype(int)
        df.rename(columns={col_ts:'t'}, inplace=True)
    else: # Turn timestamps into UNIX epochs (seconds) in an extra column
        df[col_ts] = pd.to_datetime(df[col_ts])
        df['t'] = df[col_ts].apply(lambda x: x.timestamp()).astype(int)

    # Convert the coordinates into points and create a GeoDataFrame in WGS84
    geometry = [Point(xy) for xy in zip(df[col_lon], df[col_lat])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=crs)
    # Rename columns as required for proceesing
    gdf.rename(columns={col_id:'id', col_lon:'x', col_lat:'y', col_heading:'heading', col_anno:'annotation'}, inplace=True)
    gdf = gdf.replace(np.nan, '', regex=True)
    gdf['annotation'] = gdf['annotation'].apply(lambda x: [] if x == '' else x.split(';'))
    gdf.sort_values('t')

    return gdf

    
def ais_locations2routes(gdf_locations, col_id='MMSI', crs='epsg:4326'):
    """Creates a GeoDataFrame with a polyline per vessel (MMSI) based on the sequence of its reported AIS locations. 

    Args:
        gdf_locations (GeoDataFrame): A GeoDataFrame with the locations as point geometries chronologically ordered by UNIX epochs.
        col_id (string): The name of the column with the vessel identifiers.
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
                
    Returns:
        A GeoDataFrame with the routes as a polyline geometry per vessel.
    """
    
    # Create a GeoDataFrame with polylines in WGS84, but exclude vessels with a single location reported
    gdf_routes = gdf_locations.groupby([col_id])[gdf_locations.geometry.name].apply(lambda x: LineString(x.tolist()) if len(x)>1 else None)
    gdf_routes = gpd.GeoDataFrame(gdf_routes, geometry='geometry', crs=crs)

    return gdf_routes


def read_vessel_info_csv(file_path, col_id='MMSI', col_type='TYPE', sep=';'):
    """Creates a dictionary of the types of each vessel in the dataset as listed in the given CSV file. 

    Args:
        file_path (string): The path to the input CSV file.
        col_id (string): The column containing the vessel identifiers.
        col_type (string): The column containing the vessel types (e.g., cargo, tanker, passenger).
        sep (string): The character used as separator in the CSV file (default: ';'). 
                
    Returns:
        A dictionary of key-value pairs: the vessel identifiers are the keys and their respective types are the values.
    """

    # Create a temporary DataFrame from the input CSV file
    df_vessel_info = pd.read_csv(file_path, sep=sep)
    df_vessel_info[col_type] = df_vessel_info[col_type].replace('Default', 'Not available')
    # Convert it to dictionary
    vessel_info = pd.Series(df_vessel_info[col_type].values,index=df_vessel_info[col_id]).to_dict()
    
    return vessel_info



def line2gdf(points, id='1', crs='epsg:4326'):
    """Creates a GeoDataFrame with a single polyline based on the given sequence of point locations. 

    Args:
        points (list): A list of (chronologically ordered) point geometries.
        id (string): The identifier to be used for the constructed polyline (e.g., a vessel's MMSI).
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
                
    Returns:
        A GeoDataFrame with a single polyline geometry.
    """

    #Construct a polyline geometry from the given points
    polyline = LineString( [[p.x, p.y] for p in points] )
    
    # Create a GeoDataFrame with polyline in WGS84
    line_df = pd.DataFrame()
    line_df['id'] = [1,]
    line_gdf = gpd.GeoDataFrame(line_df, geometry=[polyline,], crs=crs)
    return line_gdf


def point2gdf(point, id='1', crs='epsg:4326'):
    """Creates a GeoDataFrame with a single point. 

    Args:
        point (Point): A point geometriy.
        id (string): The identifier to be used for the constructed point.
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
                
    Returns:
        A GeoDataFrame with a single point geometry.
    """

    # Create a GeoDataFrame with point in WGS84
    df = pd.DataFrame()
    df['id'] = [1,]
    gdf = gpd.GeoDataFrame(df, geometry=[point,], crs=crs)
    return gdf

