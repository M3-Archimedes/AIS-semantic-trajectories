# Functions for extracting trip descriptions from vessel trajectories and enriching them with geographical & spatiotemporal context

import os
from tqdm import tqdm
import uuid
import json
import random
import copy
import itertools
import datetime
from itertools import product
from fastdtw import fastdtw
from shapely.geometry import Point, Polygon, LineString, shape, box
from shapely import get_coordinates
from scipy.spatial.distance import euclidean
import pygeohash as pgh

import sys
sys.path.append('.')

import reader 
import spatiotemporal
import spatial_context
import netcdf_context

def construct_context(context_params, local_crs='epsg:25832', col_name='name', iso_lang=None):
    """Creates a dictionary of GeoDataFrames or xArray datasets of spatio-temporal context data to be used for enrichment of semantic trajectories. 

    Args:
        context_params (dictionary): A dictionary with the path names for each dataset specified for spatio-temporal context.
        local_crs (string): The Coordinate Reference System generally used in the local area (OPTIONAL); used to calculate areas in square kilometers.
        col_name (string): The name of the column containing names in each dataset.
        iso_lang (string): The ISO-639-1 language code (e.g., 'el','de','fr','da') of the names (OPTIONAL); used to transliterate names in Latin characters.
                
    Returns:
        A dictionary of GeoDataFrames or xArray datasets of spatio-temporal context data.
    """

    context = {}

    # VESSEL INFO
    context['vessel_info'] = reader.read_vessel_info_csv(context_params['vessel_info'], col_id='MMSI', col_type='TYPE', sep=';') if 'vessel_info' in context_params else None

    # PORTS
    context['ports'] = spatial_context.read_csv_dataset(context_params['ports'], col_x='LON', col_y='LAT', crs='epsg:4326', col_name='NAME', sep=',') if 'ports' in context_params else None

    # PLACEMARKS
    context['placemarks'] = spatial_context.read_osm_shp_dataset(context_params['placemarks'], local_crs=local_crs, col_name=col_name) if 'placemarks' in context_params else None

    # FERRY ROUTES
    context['ferry_routes'] = spatial_context.read_osm_shp_dataset(context_params['ferry_routes'], col_name=col_name) if 'ferry_routes' in context_params else None

    # PROTECTED AREAS
    context['protected_areas'] = spatial_context.read_osm_shp_dataset(context_params['protected_areas'], local_crs=local_crs, col_name=col_name) if 'protected_areas' in context_params else None

    # SEPARATION ZONES
    context['separation_zones'] = spatial_context.read_osm_shp_dataset(context_params['separation_zones'], col_name=col_name) if 'separation_zones' in context_params else None
    
    # CAPES
    context['capes'] = spatial_context.read_osm_shp_dataset(context_params['capes'], iso_lang=iso_lang, col_name=col_name) if 'capes' in context_params else None

    # METEOROLOGICAL (WIND) FEATURES FROM NET
    context['meteo_netcdf'] = netcdf_context.read_netcdf_data(context_params['meteo_netcdf']) if 'meteo_netcdf' in context_params else None

    # BYTHOMETRY (SEA DEPTH) FEATURES 
    context['bytho_netcdf'] = netcdf_context.read_netcdf_data(context_params['bytho_netcdf']) if 'bytho_netcdf' in context_params else None
    
    return context



def format_timestamp(t, epoch=True):
    """Format the given timestamp as string. 

    Args:
        t (integer): The timestamp as UNIX epoch (in seconds).
        epoch (bool): If True, format the timestamp as UNIX epoch; otherwise, in date/time format.

    Returns:
        A string with the formatted timestamp.
    """  
    if epoch:  
        return str(t)  #As UNIX epoch (in seconds)
    else:
        return datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')  # In date/time format


def format_location(p):
    """Format the given point location as string. 

    Args:
        p (Point): The point geometry.

    Returns:
        A string with the formatted location as a pair (x, y) of coordinates.
    """ 
    return 'location (' + str(round(p.x,5)) + ', ' + str(round(p.y,5)) +')'


def format_WKT_point(p):
    """Format the given location as a point in Well-Known Text. 

    Args:
        p (Point): The point geometry.

    Returns:
        A string with the point location expressed in WKT.
    """ 
    return 'POINT(' + str(round(p.x,5)) + ' ' + str(round(p.y,5)) +')'


def format_WKT_line(p1, p2):
    """Format the given line segment defined by its two endpoints as a linestring in Well-Known Text. 

    Args:
        p1 (Point): The starting point of the line segment.
        p2 (Point): The end point of the line segment.

    Returns:
        A string with the line segment expressed in WKT.
    """ 
    return 'LINESTRING(' + str(round(p1.x,5)) + ' ' + str(round(p1.y,5)) +', ' + str(round(p2.x,5)) + ' ' + str(round(p2.y,5)) + ')'


def format_WKT_line(points):
    """Format the given polyline defined by a sequence of points as a linestring in Well-Known Text. 

    Args:
        points (list): The sequence of points (vertices) of the polyline.

    Returns:
        A string with the polyline expressed in WKT.
    """ 
    #Construct a polyline geometry from the given points
    polyline = LineString( [[p.x, p.y] for p in points] )
    return polyline.wkt


def encode_geohash_point(p, num_digits=12):
    """Encode the given point location into a short alphanumeric string (geohash). 

    Args:
        p (Point): The point geometry.
        num_digits (integer): The length of the geohash string defining the encoding resolution (default: 12).

    Returns:
        A string encoding the given location.
    """ 
    return pgh.encode(latitude=p.y, longitude=p.x, precision=num_digits)



def describe_episode(episode, ts_start, ts_end, locations, direction, heading, distance, speed, wind_beaufort, wind_direction, sea_depth, placemarks, mode='CSV', sep=';'):
    """Provide a description of a SINGLE movement episode based on the given features and statistics in the specified format. 

    Args:
        episode (string): The characterization of the movement episode (e.g., SAILING, STOPPED, COMUNICATION GAP, TURNING, etc.
        ts_start (timestamp): The start timestamp of this episode (UNIX epoch in seconds).
        ts_end (timestamp): The end timestamp of this episode (UNIX epoch in seconds).
        locations (list): The sequence of point locations for this episode.
        direction (float): The average direction (e.g., NORTH, SOUTH WEST) during this episode.
        heading (float): The average direction (in degrees) during this episode; in case of TURN, this expresses the cumulative angle during this turn. 
        distance (float): The travelled distance (in NAUTICAL MILES).
        speed (float): The average speed (in KNOTS).
        wind_beaufort: The wind intensity (in Beaufort scale) during this episode.
        wind_direction (string): The wind direction (e.g., NORTH, SOUTH WEST) during this episode.
        sea_depth (float): The minimum sea depth along the course of the vessel during this episode.
        placemarks (string): All textual placemarks (capes, islands, etc.) identified in proximity of the course during this episode.
        mode (string): The format of the description: 'CSV' (default), 'MAP', 'JSON', TXT'.
        sep (string): The character used as column separator in case of CSV or MAP format (default: ';').
        
    Returns:
        A description of this movement episode in the specified format.
    """
    
    if mode == 'CSV':
        return format_timestamp(ts_start) +sep+ format_timestamp(ts_end) +sep+ format_WKT_point(locations[0]) +sep+ format_WKT_point(locations[-1]) +sep+ episode +sep+ direction +sep+ (str(round(heading)) if heading is not None else '') +sep+ str(ts_end-ts_start) +sep+ (str(round(distance,2)) if distance is not None else '') +sep+ (str(speed) if speed is not None else '') +sep+ (str(wind_beaufort) if wind_beaufort is not None else '') +sep+ wind_direction +sep+ (str(sea_depth) if sea_depth is not None else '') +sep+ placemarks
    elif mode == 'MAP':
        return format_timestamp(ts_start) +sep+ format_timestamp(ts_end) +sep+ format_WKT_line(locations) +sep+ episode +sep+ direction +sep+ (str(round(heading)) if heading is not None else '') +sep+ str(ts_end-ts_start) +sep+ (str(round(distance,2)) if distance is not None else '') +sep+ (str(speed) if speed is not None else '') +sep+ (str(wind_beaufort) if wind_beaufort is not None else '') +sep+ wind_direction +sep+ (str(sea_depth) if sea_depth is not None else '') + sep+ placemarks
    elif mode == 'JSON':
        val = {'direction': direction, 'heading': (str(round(heading)) if heading is not None else ''), 'duration_seconds': (ts_end-ts_start+1),
              'distance_miles': (str(round(distance,2)) if distance is not None else ''), 'speed_knots': (str(speed) if speed is not None else '') , 
              'movement': episode,  'wind_beaufort': wind_beaufort, 'wind_direction':wind_direction, 'sea_depth':sea_depth, 'placemarks': placemarks,
              'start_location': {'geohash': encode_geohash_point(locations[0], 9), 'longitude':round(locations[0].x,5), 'latitude':round(locations[0].y,5), 'timestamp':format_timestamp(ts_start)}, 
              'end_location': {'geohash': encode_geohash_point(locations[-1], 9), 'longitude':round(locations[-1].x,5), 'latitude':round(locations[-1].y,5), 'timestamp':format_timestamp(ts_end)}}
        return str(val).replace('\'','\"')+','
    else: # TXT
        if episode == 'STOPPED':
            return 'From ' + format_timestamp(ts_start, epoch=False) + ' until ' + format_timestamp(ts_end, epoch=False) + ' ' + episode + ' in ' + format_location(locations[-1]) + ' ' + placemarks + (' at sea depth '+ str(sea_depth)+'meters' if sea_depth is not None else '') + ' and remained stationary for ' + str(ts_end-ts_start+1) + ' seconds. '
        elif episode == 'COMMUNICATION GAP':
            if ts_start is not None:
                return episode + ' for ' + str(ts_end-ts_start+1) + ' seconds started at ' + format_timestamp(ts_start, epoch=False) + ' in ' +  format_location(locations[0]) + ' and ended at ' + format_timestamp(ts_end, epoch=False) + ' in ' +  format_location(locations[-1]) + '. '
            else:
                return episode + ' ended at ' + format_timestamp(ts_end, epoch=False) + ' in ' +  format_location(locations[-1]) + ' with unknown duration. '
        else:
            return 'From ' + format_timestamp(ts_start, epoch=False) + ' until ' + format_timestamp(ts_end, epoch=False) + ' ' + episode + ' ' +  direction + (' by ' if episode=='TURNING' else ' at ') + str(round(heading)) + ' degrees ' + placemarks + ', covering ' + str(round(distance,2)) + ' nautical miles in ' + str(ts_end-ts_start+1) + ' seconds at speed ' + str(speed) + ' knots ' + ( 'at minimum sea depth of ' + str(sea_depth)+ ' meters ' if sea_depth is not None else '') + ( 'while ' + wind_direction + ' winds of intensity ' + str(wind_beaufort)+ 'B were blowing. ' if wind_beaufort is not None else '. ')



def extract_semantic_trips(vessel_id, vessel_type, gdf_trajectory, context, params):
    """Extract semantic trips from the trajectory of a SINGLE vessel given in the GeoDataFrame. 

    Args:
        vessel_id (string): The unique identifier of the vessel (usually its MMSI).
        vessel_type (string): The type of vessel according to AIS classification.
        gdf_trajectory (GeoDataFrame): A GeoDataFrame containing the (chronologically ordered) locations of a SINGLE trajectory (i.e., the same moving object).
        context (dictionary): A dictionary with the datasets used to provide spatio-temporal context for enriching the semantic descriptions.
        params (dictionary): A dictionary containing parameter values.
        
    Returns:
        A dictionary containing the trips identified along the entire trajectory. Each trip (i.e., movement between stops or long gaps) includes statistics (average speed and heading, traveled distance, travel time), as well as annotations regarding anchorage in ports, communication gaps, proximity to known landmarks (like capes or islands), and turning manoeuvres.
    """

    # Parameters
    #The maximum allowed interval (in seconds) with no positional report; if no signal is relayed for a period longer than this threshold, a new trip will be assigned.
    MIN_GAP_SIZE = params['MIN_GAP_SIZE'] if 'MIN_GAP_SIZE' in params else 3600
    #The minimum duration of smooth turns (in seconds); allow non-annotated intermediate locations after a turning point, in order to capture long-lasting turns
    MIN_TURN_DURATION = params['MIN_TURN_DURATION'] if 'MIN_TURN_DURATION' in params else 60 
    #The minimum angle (in degrees) for a TURN event; turns of lesser magnitude are characterized as MANEUVERS
    MIN_TURN_ANGLE = params['MIN_TURN_ANGLE'] if 'MIN_TURN_ANGLE' in params else 5
    #Determine whether to assign trip identifiers: If True, a unique (randomly chosen) UUID will be assigned in each trip; otherwise, the original trip identifier will be used in the description. 
    assign_trip_id = params['assign_trip_id'] if 'assign_trip_id' in params else True
    #The column containing trip identifiers; if not available, parameter 'assign_trip_id' must be set to True.
    col_trip_id = params['col_trip_id'] if 'col_trip_id' in params else 'trip_id'
    #The column containing timestamp values (as UNIX epochs in seconds)
    col_ts = params['col_ts'] if 'col_ts' in params else 't'
    
    # Variables
    stopped = False
    moving = False
    t_stop_start = None
    gap = False
    t_gap_start = None
    t_move_start = None
    move_points = []
    stop_points = []
    last = None
    turning = False
    turn_points = []
    trip_id = -1
    trip_episodes = []
    semantic_trips = {}
   
    # Chronologically iterate over the locations of a given trajectory
    for index, row in gdf_trajectory.iterrows():
        if 'NOISE' in row['annotation']:  # Ignore any locations annotated as NOISE
            continue
        if stopped:
            stop_points.append(row['geometry'])
        if stopped and ('STOP_END' in row['annotation'] or 'GAP_END' in row['annotation']):
            last = spatiotemporal.get_centroid(stop_points)
            # Identify the port where the vessel is anchored
            port, d = spatial_context.find_nearest_port(context['ports'], last)
            # Calculate bythometry features at this stop
            if 'bytho_netcdf' in context:
                e = netcdf_context.calc_bythometry_polyline(context['bytho_netcdf'], LineString([[p.x, p.y] for p in stop_points]))
            else:
                e = None
            event = ('STOPPED', t_stop_start, row[col_ts], [last, last], '', 0, 0, 0, None, '', e, ('in ' + port + ' port ' if port is not None else ''))
            trip_episodes.append(event) 
            if assign_trip_id:
                trip_id = uuid.uuid1().int>>64
            else:
                trip_id = row[col_trip_id]
            # A NEW trip is starting after the STOP          
            semantic_trips[trip_id] = trip_episodes 
            trip_episodes = []
            stopped = False
            stop_points = []
        if 'STOP_START' in row['annotation']:
            if moving:
                if len(turn_points)<2:  # Not enough points for turning manoeuvre 
#                    move_points.extend(turn_points)
                    Turning = False
                    turn_points = []
                if len(move_points) > 0:
                    move_points.append(row)  # Include current point to avoid gaps in distance calculations
                    move_first, move_last = [move_points[0], move_points[-1]]
                    s, d, t, h, b, w, e, placenames = spatial_context.calc_movement_features(move_points, context, params)
                    # Get extra placenames from protected areas or separation zones
                    areas = spatial_context.find_crossing_areas([m['geometry'] for m in move_points], context)
                    event = ('SAILING', move_first[col_ts], move_last[col_ts], [move_first['geometry'], move_last['geometry']], spatiotemporal.bearing2direction(h), h, d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                    trip_episodes.append(event)   
                if len(turn_points) >= 2:   # LONG-lasting turn    
                    turn_first, turn_last = [turn_points[0], turn_points[-1]]
                    diff_heading = abs(round(turn_last['heading'] - turn_first['heading']))
                    s, d, t, h, b, w, e, placenames = spatial_context.calc_movement_features(turn_points, context, params)
                    # Get extra placenames from capes
                    placenames += spatial_context.find_nearby_placemarks([t['geometry'] for t in turn_points], context['capes'], max_distance=0.1)
                    # Get extra placenames from protected areas or separation zones
                    areas = spatial_context.find_crossing_areas([t['geometry'] for t in turn_points], context)
                    if (diff_heading >= MIN_TURN_ANGLE):  # Turns of less than MIN_TURN_ANGLE (in degrees) are considered as manueuvers                 
                        event = ('TURNING', turn_first[col_ts], turn_last[col_ts], [t['geometry'] for t in turn_points], spatiotemporal.bearing2direction(turn_last['heading']), diff_heading, d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                    else:
                        event = ('MANEUVERING', turn_first[col_ts], turn_last[col_ts], [t['geometry'] for t in turn_points], spatiotemporal.bearing2direction(turn_last['heading']), turn_last['heading'], d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                    trip_episodes.append(event) 
                    turning = False
                    turn_points = []
                moving = False
                last = row['geometry']
                move_points = []
            t_stop_start = row['t']
            stop_points.append(row['geometry'])
            stopped = True
        if gap and ('GAP_END' in row['annotation'] or 'STOP_END' in row['annotation']):
            event = ('COMMUNICATION GAP', t_gap_start, row[col_ts], [last, row['geometry']], '', None, None, None, None, '', None, '')
            trip_episodes.append(event) 
            if row[col_ts] - t_gap_start > MIN_GAP_SIZE:  # GAP is longer than the MIN_GAP_SIZE, so make it another trip
                # A NEW trip will start after the GAP
                if assign_trip_id:  
                    trip_id = uuid.uuid1().int>>64  
                else:
                    trip_id = row[col_trip_id]
                semantic_trips[trip_id] = trip_episodes
                trip_episodes = []
            gap = False
            moving = True
            move_points = []
        if not stopped and 'GAP_START' in row['annotation']:
            if moving:
                if len(turn_points)<2:  # Not enough points for turning manoeuvre 
#                    move_points.extend(turn_points)
                    Turning = False
                    turn_points = []
                if len(move_points) > 0:
                    move_points.append(row)  # Include current point to avoid gaps in distance calculations
                    move_first, move_last = [move_points[0], move_points[-1]]
                    s, d, t, h, b, w, e, placenames = spatial_context.calc_movement_features(move_points,context, params)
                    # Get extra placenames from protected areas or separation zones
                    areas = spatial_context.find_crossing_areas([m['geometry'] for m in move_points], context)
                    event = ('SAILING', move_first[col_ts], move_last[col_ts], [move_first['geometry'], move_last['geometry']], spatiotemporal.bearing2direction(h), h, d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                    trip_episodes.append(event) 
                move_points = []
            last = row['geometry']
            t_gap_start = row[col_ts]
            gap = True
        if moving:
            if 'CHANGE_IN_HEADING' in row['annotation']:
                turn_points.append(row)
                turning = True
            elif turning and ((len(turn_points)<1) or (row[col_ts] - turn_points[-1][col_ts] < MIN_TURN_DURATION)):   # Ignore incomplete turns
                pass
            else:
                if len(turn_points)>=1:
                    if len(move_points) > 0:
                        move_points.append(turn_points[0])  # Include the start of the turning manoeuvre to avoid gaps in distance calculations
                        move_first, move_last = [move_points[0], move_points[-1]]
                        s, d, t, h, b, w, e, placenames = spatial_context.calc_movement_features(move_points, context, params)
                        # Get extra placenames from protected areas or separation zones
                        areas = spatial_context.find_crossing_areas([m['geometry'] for m in move_points], context)
                        event = ('SAILING', move_first[col_ts], move_last[col_ts], [move_first['geometry'], move_last['geometry']], spatiotemporal.bearing2direction(h), h, d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                        trip_episodes.append(event) 
                    move_points = [turn_points[-1]]    # Include the end of the turning manoeuvre to avoid gaps in subsequent distance calculations
                    if len(turn_points) >= 2:   # LONG-lasting turn    
                        turn_first, turn_last = [turn_points[0], turn_points[-1]]
                        diff_heading = abs(round(turn_last['heading'] - turn_first['heading']))
                        s, d, t, h, b, w, e, placenames = spatial_context.calc_movement_features(turn_points, context, params)
                        # Get extra placenames from capes
                        placenames += spatial_context.find_nearby_placemarks([t['geometry'] for t in turn_points], context['capes'], max_distance=0.1)
                        # Get extra placenames from protected areas or separation zones
                        areas = spatial_context.find_crossing_areas([t['geometry'] for t in turn_points], context)
                        if (diff_heading >= MIN_TURN_ANGLE):  # Turns of less than MIN_TURN_ANGLE (in degrees) are considered as manueuvers                 
                            event = ('TURNING', turn_first[col_ts], turn_last[col_ts], [t['geometry'] for t in turn_points], spatiotemporal.bearing2direction(turn_last['heading']), diff_heading, d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                        else:
                            event = ('MANEUVERING', turn_first[col_ts], turn_last[col_ts], [t['geometry'] for t in turn_points], spatiotemporal.bearing2direction(turn_last['heading']), turn_last['heading'], d, s, b, w, e, ('off ' + ' and '.join(placenames) if len(placenames)>0 else '')+(' crossing ' + ' and '.join(areas) if len(areas)>0 else ''))
                        trip_episodes.append(event) 
                turning = False
                turn_points = []
                move_points.append(row)
        if not stopped and not gap and not moving:
            moving = True
            move_points = []
            t_move_start = row[col_ts]
            move_points.append(row)

    # Description of the LAST trip (possibly incomplete)
    if len(trip_episodes) > 0:
        if assign_trip_id:  
            trip_id = uuid.uuid1().int>>64  
        else:
            trip_id = gdf_trajectory.iloc[-1][col_trip_id]
        semantic_trips[trip_id] = trip_episodes 
        
    return semantic_trips   # dictionary of all trips identified along the input trajectory


def describe_trajectory(vessel_id, vessel_type, gdf_trajectory, context, params):
    """Extract a textual description from the trajectory of a SINGLE vessel given in the GeoDataFrame. 

    Args:
        vessel_id (string): The unique identifier of the vessel (usually its MMSI).
        vessel_type (string): The type of vessel according to AIS classification.
        gdf_trajectory (GeoDataFrame): A GeoDataFrame containing the (chronologically ordered) locations of a SINGLE trajectory (i.e., the same moving object).
        context (dictionary): A dictionary with the datasets used to provide spatio-temporal context for enriching the semantic descriptions.
        params (dictionary): A dictionary containing parameter values.

    Returns:
        A description of the entire trajectory separated in trips (i.e., movements between stops or long gaps) in CSV, JSON or TXT format. The description includes annotations regarding anchorage in ports, communication gaps, proximity to known landmarks (like capes or islands), and turning manoeuvres.
    """

    # The description format and separator character (if applicable)
    # Format: If 'CSV' is specified, then description will be returned in CSV format with the designated separator; if 'JSON' is specified, then a JSON array will be returned, with each item representing a separate trip; otherwise, a description in plain text (TXT) will be given.
    mode = params['format'] if 'format' in params else 'CSV'
    # Separator: A character dpecifying the separator between columns if the description will be given in CSV format; ';' is the default separator.
    sep = params['sep'] if 'sep' in params else ';'

    # Extract semantic trips (i.e., split the entire trajectory into trips and identify its movement episodes)
    semantic_trips = extract_semantic_trips(vessel_id, vessel_type, gdf_trajectory, context, params)

    # Iterate over all idenitified trips to generate their description in the requested format        
    trip_descriptions = '' if mode=='CSV' or mode =='MAP' else {}
    for trip_id, trip_episodes in semantic_trips.items():
        trip_desc = [] if mode=='JSON' else '' 
        trip_points = []  # List to collect all critical locations along this trip
        # Extract time duration of the trip
        t_min = gdf_trajectory[params['col_ts']].max()
        t_max = 0
        for ep in trip_episodes:
            t_min = min(t_min, ep[1])
            t_max = max(t_max, ep[2])
            episode_desc = describe_episode(ep[0], ep[1], ep[2], ep[3], ep[4], ep[5], ep[6], ep[7], ep[8], ep[9], ep[10], ep[11], mode=mode, sep=sep)
            trip_points.append(ep[3])  # Locations in this episode
            if mode=='JSON':
                trip_desc.append(eval(episode_desc[:-1]))   # remove last comma from description and convert to JSON object
            elif mode=='CSV' or mode=='MAP':
                trip_desc+=str(trip_id)+sep+str(vessel_id)+sep+episode_desc+'\n'
            else:   # plain text (TXT)
                trip_desc+=episode_desc

        # Assign meaningful identifier for this trip by concatenating: vessel id, start timestamp, end timestamp
        new_trip_id = str(vessel_id) + '_' + str(t_min) + '_' + str(t_max)
        # Apply this new identifier into the already extracted descriptions
        if mode=='CSV' or mode=='MAP':
            trip_desc = trip_desc.replace(str(trip_id), new_trip_id)
            
        # Construct polyline from the sequence of point locations for this trip
        polyline = LineString(get_coordinates(list(itertools.chain(*trip_points))))
        
        # Calculate STATISTICS over the entire trip
        # Trip duration in h:m:s
        trip_duration = str(datetime.timedelta(seconds=(t_max - t_min)))
        
        # Traveled distance of the trip (in NAUTICAL MILES)
        trip_length = spatiotemporal.length_haversine(polyline)
        
        # Identify similarity to FERRY ROUTES   
        sim_route = ''
        origin_port = Point(polyline.coords[0])
        destination_port = Point(polyline.coords[-1])
        # Spatial join with FERRY ROUTES between the trip endpoints: identify proximity to this trip
        sel_ferry_routes = spatial_context.find_ferry_routes(context['ferry_routes'], origin_port, destination_port)
        for index, row in sel_ferry_routes.iterrows():
            distance, path = fastdtw(get_coordinates(list(itertools.chain(*trip_points))), get_coordinates(row['geometry']).tolist(), dist=euclidean)
            sim_route = '"Route":"' + row['name_int'] + '", "DTW":' + str(round(distance,2)) #' Trip course is similar to ' + row['name_int'] + ' with DTW distance ' + str(round(distance,2)) + '.'

        # Store the extracted trip description
        if mode=='CSV' or mode =='MAP':
            trip_descriptions += trip_desc   # Append to existing descriptions of previous trips
        else: # JSON or TXT
            if mode!='JSON':   # Extra statistics only reported in TXT format
                trip_desc += 'SUMMARY: ```json {"traveled_distance":' + str(round(trip_length,2)) + ', "total_duration_seconds":' + str(t_max - t_min) + ("," + sim_route if len(sim_route)>0 else "") + '}```' #' The total duration of the trip was '+ trip_duration + ' covering about ' + str(round(trip_length,2)) + ' nautical miles.' + sim_route
            trip_descriptions[new_trip_id] = trip_desc   # For descriptions in JSON or TXT 

    return trip_descriptions


def export_semantic_trajectories(gdf_annotated_trajectories, context, params):
    """Extract semantic trajectories of vessels enhanced with extra context (ports, placemarks, capes, meterorological conditions). 

    Args:
        vessel_types (string): The type of vessel according to AIS classification.
        gdf_annotated_trajectories (GeoDataFrame): A GeoDataFrame containing the locations of vessels annotated with important mobility events (stops, turns, gaps, etc.).
        context (dictionary): A dictionary with the datasets used to provide spatio-temporal context for enriching the semantic descriptions.
        params (dictionary): A dictionary containing parameter values.

    Returns:
        A description of the entire trajectory separated in trips (i.e., movements between stops or long gaps) in CSV, JSON or TXT format. The description includes annotations regarding anchorage in ports, communication gaps, proximity to known landmarks (like capes or islands), and turning manoeuvres.
    """

    #Parameters
    col_id = params['col_id'] if 'col_id' in params else 'id'
    col_ts = params['col_ts'] if 'col_ts' in params else 'ts'
    mode = params['format'] if 'format' in params else 'CSV'
    sep = params['sep'] if 'sep' in params else ';'

    # Get the unique MMSI of all vessels
    vessels = gdf_annotated_trajectories[col_id].unique()

    # Determine the format of the output descriptions
    if mode=='CSV':
        # Header in case of CSV format
        trip_descriptions = 'trip_id' +sep+ col_id +sep+ 'timestamp_start' +sep+ 'timestamp_end' +sep+ 'location_start' +sep+ 'location_end' +sep+ 'event' +sep+ 'direction' +sep+ 'heading' +sep+ 'duration_seconds' +sep+ 'distance_miles' +sep+ 'speed_knots' +sep+ 'wind_beaufort' +sep+ 'wind_direction' +sep+ 'sea_depth' +sep+ 'placemarks' + '\n'
    elif mode =='MAP':
        # Header in case of CSV format for map visualization (episodes to be drawn on map as linear segments)
        trip_descriptions = 'trip_id' +sep+ col_id +sep+ 'timestamp_start' +sep+ 'timestamp_end' +sep+ 'geometry' +sep+ 'event' +sep+ 'direction' +sep+ 'heading' +sep+ 'duration_seconds' +sep+ 'distance_miles' +sep+ 'speed_knots' +sep+ 'wind_beaufort' +sep+ 'wind_direction' +sep+ 'sea_depth' +sep+ 'placemarks' + '\n'
    else:
        trip_descriptions = {}
        
    # Iterate over the trajectory of each vessel
    for i in tqdm(range(len(vessels))):
        v = vessels[i]
        # Create a GeoDataFrame to hold the trajectory of a SINGLE vessel given its identifier (MMSI)
        gdf_trajectory = gdf_annotated_trajectories[gdf_annotated_trajectories[col_id].isin([v])].sort_values(by=[col_ts], ascending=True).reindex() # sorted by timestamp 
        if v in context['vessel_info']:
            vessel_type = context['vessel_info'][v]
        else:
            vessel_type = 'Unknown'
        # Generate the description for each trip of the given trajectory
        desc = describe_trajectory(v, vessel_type, gdf_trajectory, context, params)
        # Append it to the already generated descriptions
        if mode=='CSV' or mode=='MAP':
            trip_descriptions += desc
        else:
            trip_descriptions[int(v)] = desc

    # Srore the extracted descriptions into file
    with open(os.path.join(params['output_path'],params['output_file']), 'w') as out_file:
        if mode=='CSV' or mode=='MAP':
            out_file.write(trip_descriptions)
        else: # JSON or TXT
            json.dump(trip_descriptions, out_file)
    
    return trip_descriptions

