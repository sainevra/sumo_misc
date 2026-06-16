# -*- coding: utf-8 -*-
#
# Author: Juan Alberto Gallardo Gómez <jgallardo7@us.es>
# Date: 2026
# Description: Script to run SUMO simulations with Charging Stations.
# License: Eclipse Public License - v 2.0 (EPL-2.0)
#
# Usage: edit the CONFIG block below and run with `python3 run_sumo_with_cs.py`.

import os
import subprocess
import math
from datetime import datetime
import re
import xml.etree.ElementTree as ET

# ============================================================
# CONFIG
# ============================================================

# Use "sumo" or "sumo-gui".
# No SUMO_HOME is needed: the command must be available in your PATH.
SUMO_BINARY = "sumo-gui"
NETCONVERT_BINARY = "netconvert"

# Folder containing the original SUMO plain files and configuration.
# This folder is copied into a new run folder before each simulation.
INPUT_FOLDER = "cs_example/"

# File names inside INPUT_FOLDER.
CONFIG_FILE_NAME = "simulation.sumocfg"
NODES_FILE_NAME = "network.nod.xml"
EDGES_FILE_NAME = "network.edg.xml"
CON_FILE_NAME = "network.con.xml"
TLL_FILE_NAME = "network.tll.xml"
ADDITIONAL_FILE_NAME = "infrastructure.add.xml"
NETWORK_FILE_NAME = "network.net.xml"
ROUTES_FILE_NAME = "routes.rou.xml"
POLY_FILE_NAME = ""

# Charging station parameters.
# Use edge IDs here.
CS_LIST = [
    "e6"
    # "edge_id_1",
    # "edge_id_2",
]

CS_SIZE = 50
CS_POWER = [150000, 1.0]

# TraCI port.
RUN_PORT = 8816

# If True, removes temporary copied network/input files after the run.
# Output metrics are kept.
CLEAN_TEMP_FILES = True

# ============================================================
# CONFIG HELPERS
# ============================================================

def ensure_trailing_sep(path):
    """Return path as string ending with a path separator."""
    path = str(path)
    if path.endswith("/") or path.endswith("\\"):
        return path
    return path + os.sep


def build_config():
    """Build the old config dictionary from the simple variables above."""
    return {
        "SUMO_BINARY": SUMO_BINARY,
        "NETCONVERT_BINARY": NETCONVERT_BINARY,
        "FOLDER": ensure_trailing_sep(INPUT_FOLDER),
        "CONFIG_FILE": CONFIG_FILE_NAME,
        "NODES_FILE": NODES_FILE_NAME,
        "EDGES_FILE": EDGES_FILE_NAME,
        "CON_FILE": CON_FILE_NAME,
        "TLL_FILE": TLL_FILE_NAME,
        "ADDITIONAL_FILE": ADDITIONAL_FILE_NAME,
        "NETWORK_FILE": NETWORK_FILE_NAME,
        "ROUTES_FILE": ROUTES_FILE_NAME,
        "POLY_FILE": POLY_FILE_NAME,
        "CS_LIST": CS_LIST,
        "CS_SIZE": CS_SIZE,
        "CS_POWER": CS_POWER,
    }


def print_config(config):
    print("\n--- Configuration ---")
    for k, v in config.items():
        print(f"{k}: {v}")
    print("---------------------\n")

def folder_setup(param_dict, file_names, port=''):
    """
    Creates a timestamped folder, copies the given files into it, and writes params.txt.

    Parameters:
        FOLDER (str): Path to the folder containing the original files (must end with '/')
        param_dict (dict): Dictionary of parameters to be written to params.txt
        file_names (list): List of filenames to copy from FOLDER to the new folder

    Returns:
        str: Path to the created folder
    """
    # Generate date prefix: YYMMDD
    date_prefix = datetime.now().strftime("%y%m%d")

    # Look for existing runs with same date prefix
    runs_dir = "runs/"
    os.makedirs(runs_dir, exist_ok=True)
    existing = [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d)) and d.startswith(date_prefix)]

    # Count how many runs already exist for today
    n = len(existing) + 1
    folder_name = f"{date_prefix}-{n}"
    folder_path = os.path.join(runs_dir, folder_name) + port + "/"
    os.makedirs(folder_path, exist_ok=True)

    # Copy files
    for name in file_names:
        src_path = FOLDER + name
        dst_path = folder_path + name
        
        with open(src_path, 'r', encoding='utf-8') as f_in:
            content = f_in.read()

        with open(dst_path, 'w', encoding='utf-8') as f_out:
            f_out.write(content)

    # Write params.txt
    with open(folder_path + "params.txt", 'w', encoding='utf-8') as f:
        for key, value in param_dict.items():
            f.write(f"{key}={value}\n")

    print(f"Created folder: {folder_path}")
    return folder_path

def add_charging_stations():    
    edge_ids = obtain_edge_ids_no_roundabouts()   
    for cs in CS_LIST:
        #edge_id = edge_ids[cs]
        edge_id = cs
        if edge_id not in edge_ids:
            print(f"Edge ID {edge_id} not found in the edges file. Skipping charging station addition.")
            continue
        #print('Index: '+str(cs)+', Edge ID: '+str(edge_id))
        print('Adding CS to Edge ID: '+str(edge_id))
        # Now we have the edge_id where we want to add the charging station
        # First, we need to get the point in the edge where we want to place the charging station starting node
        edge_xml = get_edge_block(edge_id)
        shape_points = extract_shape_coords(edge_xml)        
        if shape_points:
            # If the edge has a shape, we have to use the middle point of the shape
            mid_point = compute_middle_point(shape_points)
            if mid_point:
                xm, ym = mid_point
            else:
                print(f"Error computing middle point for edge {edge_id}.")
                continue
        else:
            # If the edge does not have a shape, we have to calculate the middle point using the from and to nodes
            from_node, to_node = get_edge_nodes(edge_id)
            node_coords = load_nodes()
            if from_node in node_coords and to_node in node_coords:
                x1, y1 = node_coords[from_node]
                x2, y2 = node_coords[to_node]
                xm = (x1 + x2) / 2
                ym = (y1 + y2) / 2
            else:
                print(f"Error: Nodes {from_node} or {to_node} not found.")
                continue
        # Once we have xm and ym, we can add the node to the nodes file
        node_id = f"cs_{edge_id}"
        add_node_to_xml(NODES_FILE, node_id, xm, ym)
        # Now we can split the edge by changing the attributes of the current edge in the XML file and duplicating it
        first_half_edge = replace_attribute(edge_xml, "id", f"first_{edge_id}")
        first_half_edge = replace_attribute(first_half_edge, "to", node_id)
        second_half_edge = replace_attribute(edge_xml, "id", f"second_{edge_id}")
        second_half_edge = replace_attribute(second_half_edge, "from", node_id)
        # If the edge has a shape, we need to split it into two halves and change the shape attributes accordingly
        if shape_points:
            mid_point = (xm, ym)
            # Split shape into two halves
            n = len(shape_points)
            mid_index = n // 2
            first_half = shape_points[:mid_index+1]
            second_half = shape_points[mid_index:]
            # Ensure mid_point is included in both halves
            if first_half[-1] != mid_point:
                first_half.append(mid_point)
            if second_half[0] != mid_point:
                second_half.insert(0, mid_point)
            # Build new shape strings
            new_shape1 = "".join(f"{x},{y} " for x, y in first_half)
            new_shape2 = "".join(f"{x},{y} " for x, y in second_half)
            first_half_edge = replace_attribute(first_half_edge, "shape", new_shape1[:-1])
            second_half_edge = replace_attribute(second_half_edge, "shape", new_shape2[:-1])
        # Now we replace the old edge block in the edges file with the two new edges
        replace_xml_block_in_file(EDGES_FILE, edge_xml, first_half_edge + second_half_edge)
        # And finally, we add the charging station structure
        if shape_points:
            x1, y1 = first_half[0]
            x2, y2 = second_half[-1]
        length = 200  # Length of the charging station lane
        offset = length/2 
        x1, y1, x2, y2 = generate_parallel_segment_offset_from_point(x1, y1, x2, y2, xm, ym, length, offset)
        add_charging_station(edge_id, cs, x1, y1, x2, y2, length)
    print('Charging stations added successfully')

def replace_routes():
    """Replace edge IDs in CS_LIST inside ROUTES_FILE.
    Handles routes inside <vehicle> and routes defined directly under <routes> root.
    Maintains the original order of edges.
    """
    
    # Parse the XML file
    tree = ET.parse(ROUTES_FILE)
    root = tree.getroot()

    # --- 1. Replace edges inside vehicles ---
    for vehicle in root.findall('vehicle'):
        route = vehicle.find('route')
        if route is not None:
            edges = route.attrib.get('edges', "")
            edge_ids = edges.split()
            modified_edges = [
                f"first_{eid} second_{eid}" if eid in CS_LIST else eid
                for eid in edge_ids
            ]
            route.attrib['edges'] = " ".join(modified_edges)

    # --- 2. Replace edges in routes defined directly under root ---
    for route in root.findall('route'):
        edges = route.attrib.get('edges', "")
        edge_ids = edges.split()
        modified_edges = [
            f"first_{eid} second_{eid}" if eid in CS_LIST else eid
            for eid in edge_ids
        ]
        route.attrib['edges'] = " ".join(modified_edges)

    # Write back the modified XML
    tree.write(ROUTES_FILE, encoding="utf-8", xml_declaration=True)

def fix_connections(file):
    """Fix connections file by renaming edges in CS_LIST"""
    tree = ET.parse(file)
    root = tree.getroot()

    for conn in root.findall("connection"):
        # Check 'from'
        from_edge = conn.get("from")
        if from_edge in CS_LIST:
            conn.set("from", f"second_{from_edge}")

        # Check 'to'
        to_edge = conn.get("to")
        if to_edge in CS_LIST:
            conn.set("to", f"first_{to_edge}")

    # Save back to the same file
    tree.write(file, encoding="utf-8", xml_declaration=True)

def obtain_edge_ids():
    '''
    Obtains all edge IDs from the edges file and returns them as a list.
    '''
    edge_ids = []
    with open(EDGES_FILE, "r") as f:
        content = f.read()
        lines = content.splitlines()
        for line in lines:
            if '<edge id="' in line:
                start = line.find('id="') + 4
                end = line.find('"', start)
                edge_id = line[start:end]
                edge_ids.append(edge_id)
    return edge_ids

def obtain_edge_ids_no_roundabouts():
    '''
    Obtains all edge IDs from the edges file and returns them as a list,
    excluding those that belong to roundabouts.
    '''
    edge_ids = []
    roundabout_edges = set()

    with open(EDGES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines()

        # First pass: find all roundabout edges
        for line in lines:
            if '<roundabout ' in line:
                start = line.find('edges="') + 7
                end = line.find('"', start)
                edges_str = line[start:end]
                for edge in edges_str.split():
                    roundabout_edges.add(edge)

        # Second pass: collect edges excluding roundabouts
        for line in lines:
            if '<edge id="' in line:
                start = line.find('id="') + 4
                end = line.find('"', start)
                edge_id = line[start:end]
                if edge_id not in roundabout_edges:
                    edge_ids.append(edge_id)

    return edge_ids

def get_edge_nodes(edge_id):
    '''
    Returns the from and to nodes of an edge given its ID.
    '''
    pattern = re.compile(
        r'<edge[^>]*id="' + re.escape(edge_id) + r'"[^>]*from="([^"]+)"[^>]*to="([^"]+)"'
    )
    
    with open(EDGES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                from_node = match.group(1)
                to_node = match.group(2)
                return from_node, to_node

    return None, None

def load_nodes():
    '''
    Loads all nodes from the nodes file and returns a dictionary with node IDs as keys
    and their coordinates as values.
    '''
    node_coords = {}
    node_re = re.compile(
        r'<node[^>]*id="([^"]+)"[^>]*x="([^"]+)"[^>]*y="([^"]+)"'
    )

    with open(NODES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            m = node_re.search(line)
            if m:
                node_id = m.group(1)
                x = float(m.group(2))
                y = float(m.group(3))
                node_coords[node_id] = (x, y)

    return node_coords

def get_edge_block(edge_id):
    '''
    Returns the XML block of an edge given its ID.
    If the edge is not found, returns None.
    '''
    edge_start_re = re.compile(
        r'<edge\b[^>]*\bid="' + re.escape(edge_id) + r'"'
    )
    
    in_edge = False
    block_lines = []
    
    with open(EDGES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not in_edge:
                if edge_start_re.search(line):
                    in_edge = True
                    block_lines.append(line)
                    # Check if ends in same line
                    if '/>' in line:
                        in_edge = False
                        break
            else:
                block_lines.append(line)
                if '</edge>' in line:
                    in_edge = False
                    break

    if block_lines:
        return ''.join(block_lines)
    else:
        return None

def shifted_segment(x1, y1, x2, y2, d):
    """
    Returns a parallel (offset) segment shifted by distance d.
    
    Parameters:
        x1, y1 : float
            Coordinates of the start point.
        x2, y2 : float
            Coordinates of the end point.
        d : float
            Lateral offset distance (meters).
            d > 0 shifts to the left (normal +90°),
            d < 0 shifts to the right.
    
    Returns:
        (x1_shifted, y1_shifted, x2_shifted, y2_shifted)
    """

    # Direction vector of the original segment
    vx = x2 - x1
    vy = y2 - y1

    # Length of the segment
    L = math.hypot(vx, vy)
    if L == 0:
        return x1, y1, x2, y2  # No shift for zero-length segment

    # Unit normal vector (perpendicular to the segment)
    # Rotate 90°: (vx, vy) -> (-vy, vx)
    nx = -vy / L
    ny =  vx / L

    # Apply lateral offset to both endpoints
    x1_shifted = x1 + d * nx
    y1_shifted = y1 + d * ny
    x2_shifted = x2 + d * nx
    y2_shifted = y2 + d * ny

    return (round(x1_shifted, 2), round(y1_shifted, 2), round(x2_shifted, 2), round(y2_shifted, 2))

def add_charging_station(edge_id, cs_group, x1, y1, x2, y2, lane_length):
    '''
    Adds a charging station to the network by creating the necessary nodes and edges.
    The charging station consists of a start node, an end node, and a lane with multiple
    charging points. The function also adds the charging station to the additional.xml file.
    '''
    cs_start = f"cs_start_{edge_id}_0"
    cs_end = f"cs_end_{edge_id}_0"
    add_node_to_xml(NODES_FILE, cs_start, x1, y1)
    add_node_to_xml(NODES_FILE, cs_end, x2, y2)
    xm1, ym1, xm2, ym2 = shifted_segment(x1, y1, x2, y2, lane_length/3)
    xm = (xm1 + xm2) / 2
    ym = (ym1 + ym2) / 2
    cs_split = f"cs_{edge_id}_split"
    add_node_to_xml(NODES_FILE, cs_split, xm, ym)

    edges = f"""
    <edge id="to_cs_{edge_id}_split" from="cs_{edge_id}" to="{cs_split}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge>
    <edge id="from_cs_{edge_id}_split" from="{cs_split}" to="cs_{edge_id}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge> 
    <edge id="to_to_cs_{edge_id}_0" from="{cs_split}" to="{cs_start}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge>
    <edge id="from_from_cs_{edge_id}_0" from="{cs_end}" to="{cs_split}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge> 
    <edge id="to_from_cs_{edge_id}_0" from="{cs_split}" to="{cs_end}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge>
    <edge id="from_to_cs_{edge_id}_0" from="{cs_start}" to="{cs_split}" priority="-1">
        <lane index="0" speed="13.89"/>
    </edge>       
    """
    n_lanes = 3
    lanes = "".join(f'<lane index="{i}" speed="13.89"/>' for i in range(n_lanes))  
    cs_edges = f"""
        <edge id="cs_lanes_{edge_id}_0" from="{cs_start}" to="{cs_end}" priority="1" numLanes="{n_lanes}">
            {lanes}
        </edge>
        <edge id="cs_back_lane_{edge_id}_0" from="{cs_end}" to="{cs_start}" priority="1">
            <lane index="0" speed="13.89"/>
        </edge>
        """
    connections = "".join(f'<connection from="cs_lanes_{edge_id}_0" to="from_from_cs_{edge_id}_0" fromLane="{i}" toLane="0"/>' for i in range(n_lanes)) 
    connections += (f'\n<connection from="cs_back_lane_{edge_id}_0" to="from_to_cs_{edge_id}_0" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="to_to_cs_{edge_id}_0" to="cs_lanes_{edge_id}_0" fromLane="0" toLane="2"/>')
    connections += (f'\n<connection from="to_from_cs_{edge_id}_0" to="cs_back_lane_{edge_id}_0" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="from_to_cs_{edge_id}_0" to="to_from_cs_{edge_id}_0" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="from_to_cs_{edge_id}_0" to="from_cs_{edge_id}_split" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="from_from_cs_{edge_id}_0" to="from_cs_{edge_id}_split" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="from_from_cs_{edge_id}_0" to="to_to_cs_{edge_id}_0" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="from_cs_{edge_id}_split" to="second_{edge_id}" fromLane="0" toLane="0"/>')
    connections += (f'\n<connection from="to_cs_{edge_id}_split" to="to_to_cs_{edge_id}_0" fromLane="0" toLane="0"/>')

    cs_length = 5
    for i in range(1, int(CS_SIZE/cs_length)):
        x1, y1, x2, y2 = shifted_segment(x1, y1, x2, y2, -lane_length/4)
        cs_start = f"cs_start_{edge_id}_{i}"
        cs_end = f"cs_end_{edge_id}_{i}"
        add_node_to_xml(NODES_FILE, cs_start, x1, y1)
        add_node_to_xml(NODES_FILE, cs_end, x2, y2)
        cs_edges += f"""
        <edge id="cs_lanes_{edge_id}_{i}" from="{cs_start}" to="{cs_end}" priority="1" numLanes="{n_lanes}">
            {lanes}
        </edge>
        <edge id="cs_back_lane_{edge_id}_{i}" from="{cs_end}" to="{cs_start}" priority="1">
            <lane index="0" speed="13.89"/>
        </edge>
        """
        edges += f"""
        <edge id="to_to_cs_{edge_id}_{i}" from="cs_start_{edge_id}_{i-1}" to="{cs_start}" priority="-1">
        <lane index="0" speed="13.89"/>
        </edge>
        <edge id="from_from_cs_{edge_id}_{i}" from="{cs_end}" to="cs_end_{edge_id}_{i-1}" priority="-1">
            <lane index="0" speed="13.89"/>
        </edge>
        <edge id="from_to_cs_{edge_id}_{i}" from="{cs_start}" to="cs_start_{edge_id}_{i-1}" priority="-1">
        <lane index="0" speed="13.89"/>
        </edge>
        <edge id="to_from_cs_{edge_id}_{i}" from="cs_end_{edge_id}_{i-1}" to="{cs_end}" priority="-1">
            <lane index="0" speed="13.89"/>
        </edge>      
        """
        for j in range(n_lanes):
            connections += (f'\n<connection from="cs_lanes_{edge_id}_{i}" to="from_from_cs_{edge_id}_{i}" fromLane="{j}" toLane="0"/>')
            connections += (f'\n<connection from="cs_lanes_{edge_id}_{i-1}" to="to_from_cs_{edge_id}_{i}" fromLane="{j}" toLane="0"/>')
        connections += (f'\n<connection from="cs_back_lane_{edge_id}_{i}" to="from_to_cs_{edge_id}_{i}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="cs_back_lane_{edge_id}_{i-1}" to="to_to_cs_{edge_id}_{i}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="to_to_cs_{edge_id}_{i}" to="cs_lanes_{edge_id}_{i}" fromLane="0" toLane="2"/>')
        connections += (f'\n<connection from="to_to_cs_{edge_id}_{i-1}" to="to_to_cs_{edge_id}_{i}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="from_to_cs_{edge_id}_{i}" to="cs_lanes_{edge_id}_{i-1}" fromLane="0" toLane="2"/>')
        connections += (f'\n<connection from="from_to_cs_{edge_id}_{i}" to="from_to_cs_{edge_id}_{i-1}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="from_from_cs_{edge_id}_{i}" to="cs_back_lane_{edge_id}_{i-1}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="from_from_cs_{edge_id}_{i}" to="from_from_cs_{edge_id}_{i-1}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="to_from_cs_{edge_id}_{i-1}" to="to_from_cs_{edge_id}_{i}" fromLane="0" toLane="0"/>')
        connections += (f'\n<connection from="to_from_cs_{edge_id}_{i}" to="cs_back_lane_{edge_id}_{i}" fromLane="0" toLane="0"/>')

    edges += cs_edges
    
    #rerouter = f'\n<rerouter id="rerouter_{edge_id}" edges="to_cs_{edge_id}_split">\n<interval begin="0" end="61200">'

    charging_points = ""
    cs_offset = cs_length * 5 + (cs_length - 1) * 2
    for i in range(int(CS_SIZE/cs_length)):
        charging_points += f'\n<parkingArea id="parking_{edge_id}_{i}" lane="cs_lanes_{edge_id}_{i}_0" startPos="{lane_length-30-cs_offset}" endPos="{lane_length-30}" friendlyPos="true" roadsideCapacity="{cs_length}"  reservable="true"/>'
        charging_points += f'\n<chargingStation id="cs_{edge_id}_{i}" parkingArea="parking_{edge_id}_{i}" lane="cs_lanes_{edge_id}_{i}_0" startPos="{lane_length-30-cs_offset}" endPos="{lane_length-30}" friendlyPos="true" power="{CS_POWER[0]}"/>'
        #rerouter += f'<parkingAreaReroute id="parking_{edge_id}_{i}" visible="true"/>'

    #rerouter += '\n</interval>\n</rerouter>'
    #charging_points += rerouter
    add_edge_to_xml(EDGES_FILE, edges)
    add_cs_to_xml(ADDITIONAL_FILE, charging_points)
    add_connection_to_xml(CON_FILE, connections)

def add_node_to_xml(file_path, node_id, x, y):
    """
    Appends a <node> element to the XML file before the closing </nodes> tag.

    Parameters:
        file_path (str): Path to the nodes.xml file.
        node_id (str): ID of the new node.
        x (float): X coordinate of the new node.
        y (float): Y coordinate of the new node.
    """
    # Read the file content
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Create the new node line
    new_node_line = f'    <node id="{node_id}" x="{x}" y="{y}" />\n'

    # Insert the new node before </nodes>
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip() == "</nodes>":
                f.write(new_node_line)
            f.write(line)

    print(f'Node "{node_id}" added to {file_path}.')

def add_edge_to_xml(file_path, edge_block):
    """
    Appends an <edge> block to the XML file before the closing </edges> tag.

    Parameters:
        file_path (str): Path to the edges.xml file.
        edge_block (str): XML text of the edge block (can be multiline).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip() == "</edges>":
                f.write(edge_block.rstrip() + "\n")
            f.write(line)

    print(f'Edge block added to {file_path}.')

def add_connection_to_xml(file_path, connection_block):
    """
    Appends an <connection> block to the XML file before the closing </connections> tag.

    Parameters:
        file_path (str): Path to the connection.xml file.
        connection_block (str): XML text of the connection block (can be multiline).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip() == "</connections>":
                f.write(connection_block.rstrip() + "\n")
            f.write(line)

    print(f'Connection block added to {file_path}.')

def add_cs_to_xml(file_path, cs_block):
    """
    Appends an <chargingStation> block to the XML file before the closing </additional> tag.

    Parameters:
        file_path (str): Path to the additional.xml file.
        cs_block (str): XML text of the charging station block (can be multiline).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip() == "</additional>":
                f.write(cs_block.rstrip() + "\n")
            f.write(line)

    print(f'Charging station block added to {file_path}.')

def replace_xml_block_in_file(file_path, old_block, new_block):
    """
    Replaces a block of XML text in a file.

    Parameters:
        file_path (str): Path to the XML file.
        old_block (str): Exact XML block to be replaced.
        new_block (str): New XML block to insert in place.

    Returns:
        bool: True if replacement was successful, False otherwise.
    """
    # Read the entire file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if the old block exists in the file
    if old_block not in content:
        print("The block to replace was not found.")
        return False

    # Replace the block
    updated_content = content.replace(old_block, new_block)

    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print("Block replaced successfully.")
    return True

def extract_shape_coords(edge_xml_text):
    """
    If the edge XML block contains a shape attribute, this function extracts the coordinates
    and returns them as a list of tuples (x, y). If no shape is found, returns None.
    """
    shape_re = re.compile(r'shape="([^"]+)"')
    m = shape_re.search(edge_xml_text)
    if not m:
        return None
    
    shape_str = m.group(1)
    points = []
    for pair in shape_str.strip().split():
        x_str, y_str = pair.split(',')
        points.append((float(x_str), float(y_str)))
    return points

def compute_middle_point(shape_points):
    """
    Returns the middle point of a list of shape points.
    If the list is empty, returns None.
    """
    n = len(shape_points)
    if n == 0:
        return None
    mid_index = n // 2
    return shape_points[mid_index]

def replace_attribute(xml_text, attr_name, new_value):
    """
    Replaces the value of an attribute in an XML block.
    """
    regex = re.compile(r'(' + re.escape(attr_name) + r')="[^"]*"')
    new_text, count = regex.subn(r'\1="{}"'.format(new_value), xml_text, count=1)
    if count == 0:
        # Atributo no existe → lo añadimos
        new_text = new_text.rstrip('/>\n ') + f' {attr_name}="{new_value}" />\n'
    return new_text

def generate_parallel_segment_offset_from_point(x1, y1, x2, y2, xp, yp, length=65, offset=55):
    """
    Given a reference segment AB and a point P, generate a new segment (Q1–Q2) that:
    - Is parallel to AB
    - Is at a perpendicular distance `offset` from P
    - Has same length as AB (or a fixed one if 'length' is given)
    - Forms a triangle with vertex P

    Parameters:
        x1, y1: coordinates of point A (start of AB)
        x2, y2: coordinates of point B (end of AB)
        xp, yp: coordinates of point P
        length: optional fixed length for the parallel segment
        offset: distance from P to the new segment (perpendicular displacement)

    Returns:
        (qx1, qy1), (qx2, qy2): coordinates of the new parallel segment
    """
    # Vector AB
    dx = x2 - x1
    dy = y2 - y1
    mag = math.hypot(dx, dy)
    if mag == 0:
        raise ValueError("Points A and B cannot be the same.")

    # Normalize AB
    dx /= mag
    dy /= mag

    # Length of the new segment
    seg_len = length if length is not None else mag

    # Vector perpendicular to AB (rotated +90°)
    perp_dx = dy
    perp_dy = -dx

    # Compute midpoint of the new segment, offset from P
    mx = xp + perp_dx * offset
    my = yp + perp_dy * offset

    # Half-length vector in AB direction
    half_len = seg_len / 2
    dx_half = dx * half_len
    dy_half = dy * half_len

    # Get the two endpoints
    qx1 = mx - dx_half
    qy1 = my - dy_half
    qx2 = mx + dx_half
    qy2 = my + dy_half

    return qx1, qy1, qx2, qy2

############################################

def remove_files(WORKING_FOLDER, files_to_remove):
    """
    Delete a list of files inside a given folder.

    Parameters:
        WORKING_FOLDER (str): Path to the folder (must end with '/')
        files_to_remove (list): List of filenames to delete
    """
    for filename in files_to_remove:
        filepath = WORKING_FOLDER + filename
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"Deleted: {filepath}")
            else:
                print(f"File not found: {filepath}")
        except Exception as e:
            print(f"Error deleting {filepath}: {e}")

def run(config=None, port=RUN_PORT):
    # netconvert --sumo-net-file network.net.xml --plain-output-prefix network
    # Set up paths and files based on the configuration.
    global FOLDER, WORKING_FOLDER, NODES_FILE, EDGES_FILE, ADDITIONAL_FILE
    global CON_FILE, TLL_FILE, NETWORK_FILE, CS_LIST, CS_SIZE, CS_POWER, ROUTES_FILE
    global SUMO_BINARY, NETCONVERT_BINARY, CONFIG_FILE, POLY_FILE

    if config is None:
        config = build_config()

    SUMO_BINARY = config["SUMO_BINARY"]
    NETCONVERT_BINARY = config.get("NETCONVERT_BINARY", NETCONVERT_BINARY)

    FOLDER = ensure_trailing_sep(config["FOLDER"])

    if not os.path.isdir(FOLDER):
        raise FileNotFoundError(f"Input folder not found: {FOLDER}")

    file_list = [
        f for f in os.listdir(FOLDER)
        if os.path.isfile(os.path.join(FOLDER, f))
    ]

    WORKING_FOLDER = folder_setup(config, file_list, "_" + str(port))

    NODES_FILE = WORKING_FOLDER + config["NODES_FILE"]
    EDGES_FILE = WORKING_FOLDER + config["EDGES_FILE"]
    ADDITIONAL_FILE = WORKING_FOLDER + config["ADDITIONAL_FILE"]
    NETWORK_FILE = WORKING_FOLDER + config["NETWORK_FILE"]
    CON_FILE = WORKING_FOLDER + config["CON_FILE"]
    TLL_FILE = WORKING_FOLDER + config.get("TLL_FILE", "")
    POLY_FILE = WORKING_FOLDER + config.get("POLY_FILE", "") if config.get("POLY_FILE") else ""

    CS_LIST = config["CS_LIST"]
    CS_SIZE = config["CS_SIZE"]
    CS_POWER = config["CS_POWER"]

    # Add charging stations
    add_charging_stations()

    # Replace routes file
    ROUTES_FILE = WORKING_FOLDER + config["ROUTES_FILE"]
    replace_routes()

    # Fix connections file
    fix_connections(CON_FILE)

    if TLL_FILE and os.path.exists(TLL_FILE):
        fix_connections(TLL_FILE)

    # Convert plain network files into .net.xml
    cmd = [
        NETCONVERT_BINARY,
        "--node-files", NODES_FILE,
        "--edge-files", EDGES_FILE,
        "--connection-files", CON_FILE,
    ]

    if TLL_FILE and os.path.exists(TLL_FILE):
        cmd += ["--tllogic-files", TLL_FILE]

    cmd += ["--output-file", NETWORK_FILE]

    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Run SUMO simulation
    CONFIG_FILE = WORKING_FOLDER + config["CONFIG_FILE"]
    #run_simulation(port)
    cmd = [SUMO_BINARY, "-c", str(CONFIG_FILE)]

    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Clean up temporary files
    if CLEAN_TEMP_FILES:
        files_to_remove = [
            NETWORK_FILE,
            EDGES_FILE,
            NODES_FILE,
            ADDITIONAL_FILE,
            ROUTES_FILE,
            CON_FILE,
            TLL_FILE,
            POLY_FILE,
            CONFIG_FILE,
        ]
        files_to_remove = [f for f in files_to_remove if f]
        # remove_files('', files_to_remove)

    # Print summary or calculate combined metric for genetic algorithm optimization
    return WORKING_FOLDER


if __name__ == "__main__":
    config = build_config()
    print_config(config)
    run(config, port=RUN_PORT)
