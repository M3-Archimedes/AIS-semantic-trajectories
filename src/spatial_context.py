############################################################################################################################
# Functions for reading spatio-temporal datasets for geographical context (ports, capes, protected zones, placemarks, etc.)
############################################################################################################################

import pandas as pd
import geopandas as gpd
from geopandas import GeoSeries
import shapely
from shapely.geometry import Point, Polygon, LineString, shape, box
from shapely import get_coordinates, frechet_distance
from haversine import haversine, Unit
from transliterate import translit, get_available_language_codes
import re
import math

import sys
sys.path.append('.')

import reader 
import spatiotemporal
import netcdf_context


def read_csv_dataset(file_path, col_x='x', col_y='y', crs='epsg:4326', col_name='name', sep=','):
    """Creates a GeoDataFrame of POINT locations from the x,y coordinates contained in the given CSV file. 

    Args:
        file_path (string): The path to the input CSV file.
        col_x (string): The name of the column with the x ordinates.
        col_y (string): The name of the column with the y ordinates.
        crs (string): The Coordinate Reference System of the dataset (default: EPSG:4326).
        col_name (string): The column containing the names.
        sep (string): The character used as separator in the CSV file. 
                
    Returns:
        A GeoDataFrame with the locations as point geometries.
    """
    
    df = pd.read_csv(file_path, sep=sep)

    # Convert the coordinates into points and create a GeoDataFrame in the specified CRS
    geometry = [Point(xy) for xy in zip(df[col_x], df[col_y])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=crs)

    # Eliminate extra text within parentheses in the name
    gdf['name_int'] =  gdf[col_name].apply(lambda x: re.sub(r'\([\s\S]*\)','', str(x))).str.strip()

    return gdf


def read_osm_shp_dataset(shapefile_path, local_crs='epsg:25832', iso_lang=None, col_name='name'):
    """Creates a GeoDataFrame of spatial features extracted from OpenStreetMap and contained in the given shapefile. 

    Args:
        shapefile_path (string): The path to the input SHP file that contains features extracted from OpenStreetMap.
        local_crs (string): The Coordinate Reference System generally used in the local area (OPTIONAL); used to calculate areas in square kilometers.
        iso_lang (string): The ISO-639-1 language code (e.g., 'el','de','fr','da') of the names (OPTIONAL); used to transliterate names in Latin characters.
        col_name (string): The column containing the names.
                
    Returns:
        A GeoDataFrame with the extracted geometries.
    """

    gdf = gpd.read_file(shapefile_path)
    
    # Keep named features only
    gdf = gdf[~gdf[col_name].isnull()]
    # OPTIONAL: Keep only features (e.g., islands) with inhabitants
    #gdf = gdf_places[gdf['population']>0]

    if not set(list(gdf.geom_type.unique())).isdisjoint(['Polygon', 'MultiPolygon']):  
        # For POLYGONS, also calculate approximate area in km2, using geometries in an equal-area projection
        gdf['area_km2'] = gdf['geometry'].to_crs({'init': local_crs}).map(lambda p: p.area / 10**6)
    elif not set(list(gdf.geom_type.unique())).isdisjoint(['LineString', 'MultiLineString']): 
        # For LINES, also include the endpoint geometries to facilitate route similarity search
        gdf['from_point'] = shapely.get_point(gdf.geometry, 0)
        gdf['to_point'] = shapely.get_point(gdf.geometry, -1)

    # Transliterate local name to Latin
    if iso_lang:
        gdf['name_int'] = gdf.apply(lambda row: translit(row[col_name], iso_lang, reversed=True), axis=1)
    else:
        gdf['name_int'] = gdf[col_name]
    # Build spatial index
    gdf.sindex
    
    return gdf


############################################################################################################################
# Functions for manipulating contextual geographical data (ports, capes, protected zones, placemarks, etc.)
############################################################################################################################

def find_nearest_port(gdf_ports, q):    
    """Calculates the nearest port in the GeoDataFrame from the given location. 

    Args:
        gdf_ports (GeoDataFrame): A GeoDataFrame containing geometries and names of ports.

    Returns:
        The name of the nearest port and its distance (in decimal degrees) from the given location; if not found, the name is None.
    """
    dist = 180 # Distance in decimal degrees
    port = None
    #Create a temporary DataFrame from the given point
    gdf_loc = reader.point2gdf(q)
    # Distance join to select the nearest port
    dist_join = gpd.sjoin_nearest(gdf_loc, gdf_ports, distance_col='distance', how='left')
    if len(dist_join) > 0:
        port = dist_join.loc[0]['name_int']
        dist = dist_join.loc[0]['distance']
            
    return port.upper(), dist


def find_nearby_placemarks(points, gdf_places, max_distance=0.05):
    """Identifies any placemarks nearby the given list of point locations. 

    Args:
        points (list): A (chronologically ordered) list of point lon/lat geometries.
        gdf_places (GeoDataFrame): A GeoDataFrame containing geometries representing places (islands, straits, peninsulae, etc.).
        max_distance (float): The maximum distance (in decimal degrees) to consider nearby placemarks.

    Returns:
        A list of the names of any placemarks nearby the given list of point locations.
    """

    if len(points)<=1:
        return []
    else:       
        gdf_line = reader.line2gdf(points)
        # Spatial join with PLACES: identify proximity to known landmarks
        gdf_join = gpd.sjoin_nearest(gdf_places, gdf_line, distance_col='distance', max_distance=max_distance).sort_values('distance')
        if 'area_km2' in gdf_join.columns:
            gdf_join = gdf_join[gdf_join['area_km2']>=1]
        placenames = gdf_join['name_int'].tolist()
        return placenames


def find_crossing_areas(points, context):
    """Identifies any polygon areas crossed along the course of the given list of point locations. 

    Args:
        points (list): A (chronologically ordered) list of point lon/lat geometries.
        context (dictionary): A dictionary of ... containing (polygon) geometries of areas, e.g., representing protected zones.

    Returns:
        A list of the names of any areas (typically: PROTECTED AREAS or SEPARATION ZONES) crossed by the given sequence of point locations.
    """

    areanames = []
    if len(points)>1:       
        gdf_line = reader.line2gdf(points)
        if 'protected_areas' in context:
            # Spatial join with PROTECTED AREAS: identify crossing of PROTECTED AREAS
            gdf_join = gpd.sjoin(context['protected_areas'], gdf_line, predicate='intersects')
            if 'area_km2' in gdf_join.columns:
                gdf_join = gdf_join[gdf_join['area_km2']>=1]
            areanames += gdf_join['name_int'].tolist()
        if 'separation_zones' in context:
            # Spatial join with SEPARATION ZONES: identify crossing of SEPARATION ZONES
            gdf_join = gpd.sjoin(context['separation_zones'], gdf_line, predicate='intersects')
            areanames += gdf_join['name_int'].tolist()
        
    return areanames


def calc_movement_features(points, context, params, max_distance=0.05):
    """Calculates the spatiotemporal features from the given list of point locations. 

    Args:
        points (list): A (chronologically ordered) list of point lon/lat geometries.
        context (dictionary): A dictionary with the datasets used to provide spatio-temporal context for enriching the semantic descriptions.
        params (dictionary): A dictionary containing parameter values.
        max_distance (float): The maximum distance (in decimal degrees) to consider nearby placemarks.

    Returns:
        Spatiotemporal features (speed in knots, distance, travel time, heading) computed along the course, as well as any placenames nearby.
    """
    last = None
    dist = 0
    t = 0
    heading = 0
    if len(points)<=1:
        print('INSUFFICIENT POINTS', points)
        return 0, 0, 0, 0, []
    else:
        for p in points:
            if last is not None:
                dist += haversine((p['y'], p['x']), (last['y'], last['x']), unit=Unit.NAUTICAL_MILES)   # Haversine distance in nautical miles
                t += p['t'] - last['t']   # duration in seconds
            last =p

        # Heading of movement between first and last point location
        heading = spatiotemporal.get_bearing(points[0]['x'], points[0]['y'], points[-1]['x'], points[-1]['y'])
        
        # Also identify any placemarks nearby
        placenames = find_nearby_placemarks(points, context['placemarks'], max_distance=0.05)

        # Construct a listring from the sequence of points
        polyline = LineString([[p.x, p.y] for p in points])
        
        # Calculate wind-related features along this path from NetCDF data 
        if context['meteo_netcdf']:
            wind_speed_Beaufort, wind_direction = netcdf_context.calc_wind_conditions_polyline(context['meteo_netcdf'], polyline)
        else:
            wind_speed_Beaufort, wind_direction = None,''   # N/A

        # Calculate bythometry features along this path from NetCDF data 
        if context['bytho_netcdf']:
            sea_depth = netcdf_context.calc_bythometry_polyline(context['bytho_netcdf'], polyline)
        else:
            sea_depth = None  # N/A
            
    speed_knots = round(((3600 * dist) / (1.0* t)),1)
    
    return speed_knots, dist, t, heading, wind_speed_Beaufort, wind_direction, sea_depth, placenames


def find_ferry_routes(gdf_ferry_routes, origin_port_point, destination_port_point, max_distance=0.05):
    """Find ferry routes that connect the two given port locations. 

    Args:
        gdf_ferry_routes (GeoDataFrame): A GeoDataFrame containing line geometries and names of ferry routes in the area.
        start_port_point (Point): The location of the origin port (assuming the same CRS as the ferry routes, typically EPSG:4326).
        destination_port_point (Point): The location of the destination port (assuming the same CRS as the ferry routes, typically EPSG:4326).
        max_distance (float):  The maximum distance around the port to search for nearby ferry routes.

    Returns:
        A GeoDataFrame that contains the qualifying ferry routes that mach BOTH the origin and the destination port.
    """

    # Construct temporary GeoDataFrames from the point locations
    gdf_origin_port = reader.point2gdf(origin_port_point)
    gdf_destination_port = reader.point2gdf(destination_port_point)

    # Construct temporary GeoDataFrames for origin and destination ports of the ferry routes
    gdf_ferry_origins = gpd.GeoDataFrame(gdf_ferry_routes, geometry='from_point')
    gdf_ferry_destinations = gpd.GeoDataFrame(gdf_ferry_routes, geometry='to_point')

    #Spatial join with the origin port
    gdf_join_origin = gpd.sjoin_nearest(gdf_ferry_origins, gdf_origin_port, distance_col='distance', max_distance=max_distance).sort_values('distance')
    idx_origin = gdf_join_origin['osm_id'].tolist()

    #Spatial origin with the destination port
    gdf_join_destination = gpd.sjoin_nearest(gdf_ferry_destinations, gdf_destination_port, distance_col='distance', max_distance=max_distance).sort_values('distance')
    idx_destination = gdf_join_destination['osm_id'].tolist()

    # Routes matching both origin and destination
    idx= list(set(idx_origin) & set(idx_destination))
    sel_routes = gdf_ferry_routes[gdf_ferry_routes['osm_id'].isin(idx)]
    
    return sel_routes

