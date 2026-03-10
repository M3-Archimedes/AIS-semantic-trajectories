import sys
sys.path.append('../src')

import reader
import spatiotemporal
import netcdf_context
import spatial_context
import description
import warnings
warnings.filterwarnings('ignore')


# Execution parameters
exec_params = {
    'col_id':'id',           #The column containing the unique vessel identifiers (typically, their MMSI)
    'col_ts':'t',            #The column containing timestamp values (as UNIX epochs in seconds)
    'col_trip_id':'trip_id', #The column containing trip identifiers; if NOT available, parameter 'assign_trip_id' must be set to True.
    'assign_trip_id':True,   #If True, a unique (randomly chosen) UUID will be assigned in each trip; otherwise, the original trip identifier will be used in the description. 
    'MIN_GAP_SIZE':3600,     #The maximum allowed interval (in seconds) with no positional report; if no signal is relayed for a period longer than this threshold, a new trip will be assigned.
    'MIN_TURN_DURATION':60,  #The minimum duration of smooth turns (in seconds); allow non-annotated intermediate locations after a turning point, in order to capture long-lasting turns
    'MIN_TURN_ANGLE':5,      #The minimum angle (in degrees) for a TURN event; turns of lesser magnitude are characterized as MANEUVERS
    'output_path':'output',    #Path to the output file where the extracted trip descriptions will be stored
    'output_file':'trip_descriptions.json',                  #Output file name
    'format':'JSON',         #Description format: If 'CSV' or 'MAP' is specified, then description will be returned in CSV format with the designated separator; if 'JSON' is specified, then a JSON array will be returned, with each item representing a separate trip; otherwise, a description in plain text (TXT) will be given.
    'sep':';',               #A character dpecifying the separator between columns if the description will be given in CSV or MAP format; ';' is the default separator.       
}


# Context settings
context_settings = {
    'vessel_info':'settings/vessel_info.csv',  # CSV: The type(passenger, cargo, tanker, etc.) of each vessel
    'ports':'context/geospatial/ports.csv', # CSV: List of ports in the area and their names
    'placemarks':'context/geospatial/osm_places.shp', # SHP: The shapefile containing cislands and other (polygon) placemarks as extracted from OSM
    'protected_areas':'context/geospatial/osm_protected_areas.shp', # SHP: The shapefile containing protected areas as extracted from OSM
    'capes':'context/geospatial/osm_capes.shp', # SHP: The shapefile containing capes, peninsuale, straits, etc as extracted from OSM
    'ferry_routes':'context/geospatial/osm_ferry_routes.shp', # SHP: The shapefile containing ferry routes as extracted from OSM
    'separation_zones':'context/geospatial/osm_separation.shp', # SHP: The shapefile containing separation zones as extracted from OSM
    'meteo_netcdf':'context/meteorological',   # Path to the NetCDF files containing meterorological (wind) data
    'bytho_netcdf':'context/bathymetry',   # Path to the NetCDF files containing meterorological (wind) data
}

print('Reading available data sources for context...')
# Create all context to be used for enriching the semantic descriptions
context = description.construct_context(context_settings, local_crs='epsg:25832', col_name='name', iso_lang=None)
print('DONE!')

# Provide the CSV file that contains AIS locations with their ANNOTATIONS 
# Such a file can be computed from AIS raw locations by the module available in https://github.com/M3-Archimedes/AIS-trajectory-annotation
ais_annotated_file = 'input/ais_annotated_locations.csv'

print('Reading annotated AIS data...')
# Specify the necessary attributes: vessel identifier, longitude, latitude, timestamp (in epoch seconds), heading, annotation  
gdf_ais_annotated = reader.read_annotated_ais_locations(ais_annotated_file, col_id='id', col_lon='lon', col_lat='lat', col_ts='t', col_heading='heading', col_anno='annotation', sep=',', crs='epsg:4326')
print('DONE!')

print('Preparing semantic trajectory descriptions...')
# Extract semantic descriptions of each trip in the given AIS annotated trajectories and enrich them with any available spatio-temporal context
trip_descriptions = description.export_semantic_trajectories(gdf_ais_annotated, context, exec_params)
print('DONE!')
