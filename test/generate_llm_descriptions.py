import os
import requests
import json
import time
import pandas as pd
from groq import Groq
from io import StringIO

# Speccify here your API key issued by Groq at https://console.groq.com/keys
GROQ_API_KEY = "<YOUR API KEY TO GROQ AI PROVIDER>" 


# Create a client ot the API
client = Groq(
    api_key= GROQ_API_KEY #os.environ.get(GROQ_API_KEY),
)


def submit_query(model, system_prompt, user_prompt):
    """Sumbit a request to an LLM hosted in groq and returns the given answer. 

    Args:
        model (string): The model identifier as given by groq.
        system_prompt (string): The system prompt, designating the role, the objectives, and instructions for the request.
        user_prompt (string): The user prompt, specifying the question asked along with any detailed specifications or data.

        
    Returns:
        The response to the submitted query as given by the LLM according to the instructions in the prompts.
    """


    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            model=model,
        )
        return chat_completion.choices[0].message.content, chat_completion.usage.total_time, chat_completion.usage.prompt_tokens, chat_completion.usage.total_tokens
    except:
        print("An exception occurred when calling ", model) 
        return "FAILED", 0, 0, 0


# SYSTEM PROMPT
system_prompt = '# ROLE AND OBJECTIVE:\nYou are a data scientist who studies trips of vessels, i.e., the route of ships sailing between ports or locations at open sea. You are given a list of waypoints in JSON format representing the trip of a vessel, including information about anchorage in ports, duration of each stop, sailing for varying time intervals, and occasionally turning maneuvers when a vessel changes its direction of movement. Based on this information about the trip, you must provide its description in plain text. \n# APPROACH AND LIMITATIONS:\nAll vessel locations are specified in (longitude, latitude) coordinates in WGS84 (EPSG:4326) Coordinate Reference System. Distances are always expressed in nautical miles and are calculated using the Haversine formula on an ellipsoid. Speed values are in knots, i.e., nautical miles per hour. Durations are in seconds. All timestamp values are in UNIX epochs (seconds elapsed since 1970-01-01) in GMT time zone. Wind intensity is in Beaufort scale. Placemarks indicate proximity to islands, ports, straits, capes, etc. Note that the motion patterns and speed of vessels absolutely depend on their type (e.g., Passenger, Cargo, Tanker, Pleasure craft, etc.), and some vessels may be anchored for long intervals. Due to COMMUNICATION GAPS, a vessel may suddenly appear far away from its previously known position.\n# METHODOLOGY:\nYou must provide:\n(i) A textual description in PLAIN TEXT that outlines the trip. In a separate paragraph describe each major stage of the trip, such as port operations (e.g., anchorage), important navigational features (e.g., cruising at open sea, maneuvering, turning) as well as any proximity to placemarks (e.g., islands, straits, capes). Do NOT include any explanations or reasoning regarding any stage of the trip.\n(ii) A short summary in JSON format with statistics that include the traveled distance (in nautical miles), the total duration (in seconds), the names of the origin and destination ports (if available) and any adverse weather conditions identified across the entire trip as follows:\n```json{"traveled_distance_nm": distance_value, "total_duration_sec": duration_value, "origin_port": port_name, "destination_port" : port_name, "adverse_weather_conditions": [ "wind_intensity":"beaufort_value", "wind_direction": direction_value ] }```.\n For your responses, you must NOT include information from any external source; use information strictly from the input JSON.'


# USER PROMPT TEMPLATE
user_prompt_template = 'Based on this JSON array representing the simplified trip of a vessel, please provide a textual description. \n```json{}```'


# SETUP

# Specify here the LLM models you wish to test for generating textual descriptions of vessel trips
llm_models = ['llama-3.1-8b-instant','qwen/qwen3-32b','openai/gpt-oss-20b','openai/gpt-oss-120b','llama-3.3-70b-versatile'] 


# EXECUTION

json_input_file = 'output/trip_descriptions.json'
with open(json_input_file) as f:
    dict_vessel_trips = json.load(f)

json_output_file = 'output/llm_generated_trip_descriptions.json'

# INITIAL RUN
output_descriptions = dict()
for llm in llm_models:
    output_descriptions[llm] = []

k = 0
for vessel, vessel_trips in dict_vessel_trips.items():
    for trip_id in vessel_trips:
        k += 1
        user_prompt = user_prompt_template
        user_prompt = user_prompt.replace('{}', str(vessel_trips[trip_id]))
        for llm in llm_models:
            #Ingest the JSON trip into the prompt and submit request to API
            response, total_time, prompt_tokens, total_tokens = submit_query(llm, system_prompt, user_prompt)
            llm_result = {'response':response, 'total_time':total_time, 'prompt_tokens':prompt_tokens, 'total_tokens':total_tokens}
            output_descriptions[llm].append({trip_id: llm_result})
        print(trip_id)
        # Write received responses every 10 trips to output file
        if (k%10 ==0):
            with open(json_output_file, 'w') as f:
                json.dump(output_descriptions, f)

