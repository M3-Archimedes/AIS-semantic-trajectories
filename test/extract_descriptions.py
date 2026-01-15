import sys
sys.path.append('../src')

import reader
import spatiotemporal
import netcdf_context
import spatial_context
import description

# Execution parameters
exec_params = {
    'col_id':'id',           #The column containing the unique vessel identifiers (typically, their MMSI)
    'col_ts':'t',            #The column containing timestamp values (as UNIX epochs in seconds)
    'col_trip_id':'trip_id', #The column containing trip identifiers; if NOT available, parameter 'assign_trip_id' must be set to True.
    'assign_trip_id':True,   #If True, a unique (randomly chosen) UUID will be assigned in each trip; otherwise, the original trip identifier will be used in the description. 
    'MIN_GAP_SIZE':3600,     #The maximum allowed interval (in seconds) with no positional report; if no signal is relayed for a period longer than this threshold, a new trip will be assigned.
    'MIN_TURN_DURATION':60,  #The minimum duration of smooth turns (in seconds); allow non-annotated intermediate locations after a turning point, in order to capture long-lasting turns
    'MIN_TURN_ANGLE':5,      #The minimum angle (in degrees) for a TURN event; turns of lesser magnitude are characterized as MANEUVERS
    'output_path':'/mnt/data/trajectory/danish/tripped/',    #Path to the output file where the extracted trip descriptions will be stored
    'output_file':'trip_descriptions7.json',                  #Output file name
    'format':'JSON',         #Description format: If 'CSV' or 'MAP' is specified, then description will be returned in CSV format with the designated separator; if 'JSON' is specified, then a JSON array will be returned, with each item representing a separate trip; otherwise, a description in plain text (TXT) will be given.
    'sep':';',               #A character dpecifying the separator between columns if the description will be given in CSV or MAP format; ';' is the default separator.       
}


# Context settings
context_settings = {
    'vessel_info':'/mnt/data/trajectory/AIS-trajectory-annotation/test/settings/vessel_info_266331000.csv',  # CSV: The type(passenger, cargo, tanker, etc.) of each vessel
    'ports':'/mnt/data/trajectory/context/ports.csv', # CSV: List of ports in the area and their names
    'placemarks':'/mnt/data/trajectory/context/denmark/osm_places.shp', # SHP: The shapefile containing cislands and other (polygon) placemarks as extracted from OSM
    'protected_areas':'/mnt/data/trajectory/context/denmark/osm_protected_areas.shp', # SHP: The shapefile containing protected areas as extracted from OSM
    'capes':'/mnt/data/trajectory/context/denmark/osm_capes.shp', # SHP: The shapefile containing capes, peninsuale, straits, etc as extracted from OSM
    'ferry_routes':'/mnt/data/trajectory/context/denmark/osm_ferry_routes.shp', # SHP: The shapefile containing ferry routes as extracted from OSM
    'separation_zones':'/mnt/data/trajectory/context/denmark/osm_separation.shp', # SHP: The shapefile containing separation zones as extracted from OSM
    'meteo_netcdf':'/mnt/data/trajectory/context/denmark/meteo',   # Path to the NetCDF files containing meterorological (wind) data
    'bytho_netcdf':'/mnt/data/trajectory/context/denmark/bythometry',   # Path to the NetCDF files containing meterorological (wind) data
}


# Create all context to be used for enriching the semantic descriptions
context = description.construct_context(context_settings, local_crs='epsg:25832', col_name='name', iso_lang=None)

# Provide the CSV file that contains AIS locations with their ANNOTATIONS 
# Such a file can be computed from AIS raw locations by the module available in https://github.com/M3-Archimedes/AIS-trajectory-annotation
ais_annotated_file = '/mnt/data/trajectory/danish/tripped/211188000_tripped_indexed.csv'

# Specify the necessary attributes: vessel identifier, longitude, latitude, timestamp (in epoch seconds), heading, annotation  
gdf_ais_annotated = reader.read_annotated_ais_locations(ais_annotated_file, col_id='MMSI', col_lon='LON', col_lat='LAT', col_ts='TIMESTAMP', col_heading='HEADING', col_anno='ANNOTATION', sep=',', crs='epsg:4326')

# Extract semantic descriptions of each trip in the given AIS annotated trajectories and enrich them with any available spatio-temporal context
trip_descriptions = description.export_semantic_trajectories(gdf_ais_annotated, context, exec_params)



