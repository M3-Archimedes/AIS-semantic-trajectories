# Context-Enriched Natural Language Descriptions of Vessel Trajectories


This software transforms raw vessel trajectory data collected from AIS into structured and semantically enriched representations interpretable by humans and directly usable by machine reasoning systems. It applies a context-aware trajectory abstraction framework that segments noisy AIS sequences into distinct trips each consisting of clean, mobility-annotated episodes. Each episode is further enriched with multi-source contextual information, such as nearby geographic entities, offshore navigation features, and weather conditions. Crucially, such representations can support generation of controlled natural language descriptions using Large Language Models (LLM). By increasing semantic density and reducing spatiotemporal complexity, this abstraction can facilitate downstream analytics and enable integration with LLMs for higher-level maritime reasoning tasks.

## Installation 

Pre-requisites:
```
! pip install geopandas numpy==1.26.4 fastdtw==0.3.4 haversine==2.9.0 pandas pygeohash==3.2.2 scipy shapely==2.0.6 tqdm==4.66.5 transliterate==1.10.2 xarray==2023.1.0 netCDF4 setuptools
```
If you are running this through a notebook, you might need to restart kernel to load changes.

*Please find a working example in the test folder along with indicative datasets.* 

## Framework

This framework enables (i) construction of context-enriched semantic trajectories for vessels and (ii) generating textual descriptions of vessel trips in natual language.

### (i) Constructing context-enriched semantic trajectories

This open-source module accepts as input raw vessel locations collected through the [Automatic Identification System (AIS)](https://www.imo.org/en/ourwork/safety/pages/ais.aspx) and constructs context-enriched trajectory representations. More specifically:

* _Mobility annotation_: It first annotates important points along the course of each vessel according to detected mobility events (e.g., stops, turns, slow motion). 

* _Trip segmentation_: Noisy locations are filtered out and raw positional reports are organized by trip, each consisting of a sequence of semantic episodes based on the detected annotations.

* _Context enrichment_: It ingests extra context from various (geographical, maritime, meteorological) sources into each episode. Such context may include:

    - _Ports_: Identifies the name of the port where the vessel is anchored during a stop episode.

    - _Placemarks_ (Coastal features): Finds whether the vessel is moving in close distance (e.g., less than 5 nautical miles) to capes, peninsulae, straits, etc.

    - _Protection zones_ (Offshore areas): Finds any polygonal regions (e.g., marine protection zones, national sea parks, fishing areas) the vessel is crossing along its course.

    - _Traffic separation schemes_: Indicates whether the vessel is navigating across the designated lane for its direction in high-density areas according to traffic regulations.

    - _Meteorological_: If NetCDF data is available for this time period, the module identifies the wind conditions (wind force in the Beaufort scale, wind direction) along the polyline that represents the course of a vessel during this episode.

    - _Bathymetry_: The NetCDF data that provides the seabed depth (in meters) at the grid cell of the stop event (if the vessel is anchored) or the minimum depth along the polyline of a moving episode (i.e., when the vessel is sailing or turning).

* _Output representation_: The resulting semantic trajectory representation can be exported into several formats (CSV, JSON, plain TXT) for further processing, analytics, or visualization in maps and charts.

### (ii) LLM-generated description in natural language

To generate descriptions using LLMs, we employ a prompt consisting of a system message that establishes the task context and a user message that provides the semantic trajectory extracted in (i). This approach includes detailed instructions concerning interpretation of the various features (coordinates, timestamp, speed, distance, duration) per episode in the movement, as well as precise guidelines for measurement units (e.g., nautical miles for distance, Beaufort scale for wind force) and any available placemarks (islands, ports, capes, etc.) added from extra context to make sure that the model can interpret and use them properly. This prompt also includes a methodology that guides the LLM in synthesizing available information in order to provide its response in two parts:

* A _textual description_ in natural language that outlines the trip and its most significant stages. 

* A summary of _trip statistics_ in JSON format that include the traveled distance, the total duration, and the origin and destination ports (if available). 


<br>


## Related GitHub Repositories 

* [**HABIT: Aggregation-based Imputation Framework for Vessel Trajectories**](https://github.com/M3-Archimedes/HABIT)

* [**IMGIN: Image-based Imputation of Trajectories**](https://github.com/M3-Archimedes/IMaGe-based-ImputatioN-of-Trajectories)

* [**AIS Vessel Trajectory Annotation**](https://github.com/M3-Archimedes/AIS-trajectory-annotation)


## Project 
[**M3: Multimodal Foundation Models for the Maritime Domain Project**](https://github.com/M3-Archimedes)


## Publication 

Kostas Patroumpas, Alexandros Troupiotis-Kapeliaris, Giannis Spiliopoulos, Panagiotis Betchavas, Dimitrios Skoutas, Dimitris Zissis, Nikos Bikakis
[**Context-Enriched Natural Language Descriptions of Vessel Trajectories**](http://arxiv.org/abs/2603.12287), IEEE International Conference on Mobile Data Management (IEEE MDM 2026).



<br>

## License

The contents of these repository are licensed under [GNU General Public License v3.0](https://github.com/M3-Archimedes/AIS-semantic-trajectories/blob/main/LICENSE).
