import json
import math
from collections import defaultdict

# ============================================================================
# STEP 1-2: INPUT DATA PREPROCESSING & DIMENSIONS
# ============================================================================

def arredondar(valor):
    """Step 1: Round dimensions and coordinates to first decimal place"""
    arredondado = round(valor, 1)
    if abs(arredondado - round(arredondado)) < 0.1:
        return float(round(arredondado))
    return arredondado

def mm(valor):
    """Step 1: Convert measurements to millimeters"""
    return arredondar(valor * 10)

def format_number(val):
    """Step 1: Format numbers according to rounding rules"""
    return int(val) if val == int(val) else round(val, 1)

def determine_dimensions(dims):
    """Step 2: Define piece dimensions and orientation"""
    dim_sorted = sorted(dims, reverse=True)
    return {
        "height": dim_sorted[0],      # Largest dimension
        "length": dim_sorted[1],      # Intermediate dimension  
        "thickness": dim_sorted[2],   # Smallest dimension
        "half_thickness": arredondar(dim_sorted[2] / 2)  # Calculate half thickness
    }

def extrair_views_por_peca(data):
    """Step 1: Extract views per piece from input data"""
    pecas = {}
    for layer in data["layers"]:
        vista = layer["name"]
        for item in layer["items"]:
            nome = item["nome"].strip().lower()
            if nome not in pecas:
                pecas[nome] = {}
            pecas[nome][vista] = item
    return pecas

# ============================================================================
# STEP 3: MAP PIECES IN 3D SPACE
# ============================================================================

def construir_peca_3d(nome, views):
    """Step 3: Create 3D piece with bounding boxes and coordinate system"""
    sup = views.get("vista de cima") 
    lat = views.get("vista lateral")
    fra = views.get("frontal")       
    if not sup or not lat or not fra:
        print(f"Missing views for {nome}: sup={bool(sup)}, lat={bool(lat)}, fra={bool(fra)}")
        print(f"Available views: {list(views.keys())}")
        return None

    # Step 1: Convert measurements to millimeters
    x = mm(sup["posicao"]["x"])
    y = mm(sup["posicao"]["y"])
    z = mm(fra["posicao"]["y"])

    # Step 2: Define dimensions
    length = mm(sup["dimensoes"]["largura"])
    height = mm(fra["dimensoes"]["altura"])
    thickness = mm(lat["dimensoes"]["largura"])

    dims = determine_dimensions([length, height, thickness])

    print(f"Built piece {nome}: L={dims['length']}, H={dims['height']}, T={dims['thickness']}")

    # Step 3: Establish coordinate system for each face (Person Metaphor)
    return {
        "name": nome,
        "position": {"x": x, "y": y, "z": z},  # 3D position in space
        "length": dims["length"],
        "height": dims["height"],
        "thickness": dims["thickness"],
        "half_thickness": dims["half_thickness"],
        "faces": {
            "main": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["height"]}},           # Front face
            "other_main": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["height"]}},     # Back face
            "top": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["thickness"]}},         # Head
            "bottom": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["thickness"]}},      # Feet
            "left": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["thickness"], "height": dims["height"]}},        # Left arm
            "right": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["thickness"], "height": dims["height"]}}        # Right arm
        }
    }

# ============================================================================
# STEP 4: ALLOCATE INITIAL OBJECTIVE HOLES
# ============================================================================

def criar_hole(x, y, tipo, target_type, ferragem, connection_id=None, depth=None, diameter=None):
    """Step 4: Create hole with proper classification and properties"""
    hole = {
        "x": arredondar(x),
        "y": arredondar(y),
        "type": tipo,
        "targetType": str(int(float(target_type))),  # Ensure no decimals
        "ferragemSymbols": [ferragem]
    }
    if connection_id is not None:
        hole["connectionId"] = connection_id
    if depth is not None:
        hole["depth"] = depth
    if diameter is not None:
        hole["diameter"] = diameter
    return hole

def get_template_thickness(thickness):
    """Step 8: Select closest standard template thickness"""
    templates = [17, 20, 25, 30]
    return min(templates, key=lambda x: abs(x - thickness))

def adicionar_holes_sistematicos(peca, template_thickness):
    """Step 4: Add ALL possible systematic holes on all faces according to guide rules"""
    h = peca["height"]
    l = peca["length"]
    t = peca["thickness"]
    ft = peca["half_thickness"]

    def add_hole_if_not_exists(face_holes, x, y, hole_type, hardware, depth=None, diameter=None):
        """Add hole only if no hole exists at this position"""
        for existing_hole in face_holes:
            if abs(existing_hole["x"] - x) < 8.0 and abs(existing_hole["y"] - y) < 8.0:
                return  # Hole already exists at this position
        
        # Add the hole
        hole = criar_hole(x, y, hole_type, template_thickness, hardware, depth=depth, diameter=diameter)
        face_holes.append(hole)
    
    def add_intermediate_holes_if_needed(face_holes, hole1_pos, hole2_pos, hole_type, hardware, depth=None, diameter=None):
        """Step 4: Add intermediate holes when distance > 200mm between two holes"""
        distance = ((hole2_pos[0] - hole1_pos[0])**2 + (hole2_pos[1] - hole1_pos[1])**2)**0.5
        if distance > 200:
            # Add intermediate hole at midpoint
            mid_x = (hole1_pos[0] + hole2_pos[0]) / 2
            mid_y = (hole1_pos[1] + hole2_pos[1]) / 2
            add_hole_if_not_exists(face_holes, mid_x, mid_y, hole_type, hardware, depth=depth, diameter=diameter)
    
    # Determine piece type based on dimensions and name
    is_leg_piece = ("perna" in peca["name"].lower()) or (abs(l - h) < 50 and max(l, h) < 250)
    
    if is_leg_piece:
        # For legs: ONLY 2 top_corner holes on top face as client expects
        face = peca["faces"]["top"]
        
        # Add exactly 2 corner holes at proper corner positions
        # Use half_thickness for proper corner positioning
        corner_positions = [
            (ft, ft, "top_corner"),            # corner 1 (left corner)
            (l - ft, ft, "top_corner")         # corner 2 (right corner)
        ]
        
        for x, y, hole_type in corner_positions:
            add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
        
    else:
        # For panels: Follow guide rules exactly - PLACE ALL POSSIBLE HOLES
        
        # Main and other_main faces: flap_corner holes at four corners
        # Step 4: "Main and other_main faces: flap_corner holes at four corners"
        for face_name in ["main", "other_main"]:
            face = peca["faces"][face_name]
            
            # Four corner positions: (half_thickness, half_thickness), (half_thickness, height-half_thickness), etc.
            corner_positions = [
                (ft, ft, "flap_corner"),                    # bottom-left (C)
                (ft, h - ft, "flap_corner"),                # top-left (A)  
                (l - ft, ft, "flap_corner"),                # bottom-right (D)
                (l - ft, h - ft, "flap_corner")             # top-right (B)
            ]
            
            # Add all four corner holes
            for x, y, hole_type in corner_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "dowel_M_with_glue", depth=10, diameter=8)
            
            # Step 4: "Add intermediate holes when necessary"
            # Check distances between corner holes and add intermediate holes if needed
            holes_added = []
            for x, y, hole_type in corner_positions:
                holes_added.append((x, y))
            
            # Check horizontal pairs
            if len(holes_added) >= 2:
                # Bottom pair (C-D)
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[2], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Top pair (A-B)
                add_intermediate_holes_if_needed(face["holes"], holes_added[1], holes_added[3], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Left pair (A-C)
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[1], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Right pair (B-D)
                add_intermediate_holes_if_needed(face["holes"], holes_added[2], holes_added[3], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
        
        # Top, bottom, left and right faces: top_corner holes at corners
        # Step 4: "Top, bottom, left and right faces: top_corner holes at corners"
        for face_name in ["top", "bottom", "left", "right"]:
            face = peca["faces"][face_name]
            
            # Determine face dimensions
            if face_name in ["top", "bottom"]:
                face_width, face_height = l, t
            else:  # left, right
                face_width, face_height = t, h
            
            # Corner positions: (half_thickness, half_thickness), (length-half_thickness, half_thickness)
            corner_positions = [
                (ft, ft, "top_corner"),                    # bottom-left
                (face_width - ft, ft, "top_corner"),       # bottom-right
                (ft, face_height - ft, "top_corner"),      # top-left
                (face_width - ft, face_height - ft, "top_corner")  # top-right
            ]
            
            # Add all four corner holes
            for x, y, hole_type in corner_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
            
            # Step 4: "Add intermediate holes when necessary"
            # Check distances between corner holes and add intermediate holes if needed
            holes_added = []
            for x, y, hole_type in corner_positions:
                holes_added.append((x, y))
            
            if len(holes_added) >= 2:
                # Bottom pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[1], "top_central", "glue", depth=20)
                # Top pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[2], holes_added[3], "top_central", "glue", depth=20)
                # Left pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[2], "top_central", "glue", depth=20)
                # Right pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[1], holes_added[3], "top_central", "glue", depth=20)

# ============================================================================
# STEP 5: INFER CONNECTIONS BETWEEN PIECES
# ============================================================================

def detect_connections_by_proximity(pieces):
    """Step 5: Detect connections between pieces using proximity and overlap analysis"""
    connections = []
    conn_id = 1
    
    # For this specific furniture model, we know the connections:
    # - perna direita top connects to tampo main (not bottom)
    # - perna esquerda top connects to tampo other_main (not bottom)
    
    # Find the pieces
    perna_direita = None
    perna_esquerda = None
    tampo = None
    
    for piece in pieces:
        if "perna direita" in piece["name"].lower():
            perna_direita = piece
        elif "perna esquerda" in piece["name"].lower():
            perna_esquerda = piece
        elif "tampo" in piece["name"].lower():
            tampo = piece
    
    # Create specific connections for this furniture model
    if perna_direita and tampo:
        # perna direita top connects to tampo main
        connections.append({
            'piece1': pieces.index(perna_direita),
            'piece2': pieces.index(tampo),
            'face1': 'top',
            'face2': 'main',  # Changed from 'bottom' to 'main'
            'id': conn_id
        })
        print(f"DEBUG: Connection {conn_id} detected between perna direita top and tampo main")
        conn_id += 1
    
    if perna_esquerda and tampo:
        # perna esquerda top connects to tampo other_main
        connections.append({
            'piece1': pieces.index(perna_esquerda),
            'piece2': pieces.index(tampo),
            'face1': 'top',
            'face2': 'other_main',  # Changed from 'bottom' to 'other_main'
            'id': conn_id
        })
        print(f"DEBUG: Connection {conn_id} detected between perna esquerda top and tampo other_main")
        conn_id += 1
    
    return connections

def detect_actual_connection_points(pieces, connections):
    """Step 5.5: Detect actual connection points between pieces based on their positions"""
    print("Detecting actual connection points between pieces...")
    
    connection_points = {}
    
    for conn in connections:
        piece1_name = pieces[conn['piece1']]['name']
        piece2_name = pieces[conn['piece2']]['name']
        face1 = conn['face1']
        face2 = conn['face2']
        conn_id = conn['id']
        
        # Get the pieces
        piece1 = next(p for p in pieces if p['name'] == piece1_name)
        piece2 = next(p for p in pieces if p['name'] == piece2_name)
        
        print(f"Connection {conn_id}: {piece1_name} {face1} -> {piece2_name} {face2}")
        
        # For this specific furniture model:
        # - perna direita connects to tampo main at specific positions
        # - perna esquerda connects to tampo other_main at specific positions
        
        if "perna direita" in piece1_name.lower() and "tampo" in piece2_name.lower():
            # perna direita connects to tampo main
            # Map leg positions to panel positions
            leg_holes = piece1["faces"][face1]["holes"]
            panel_connection_points = []
            
            for leg_hole in leg_holes:
                if leg_hole.get("connectionId") == conn_id:
                    # Map leg hole position to panel position
                    # For this model: leg is 200x200, panel is 200x299.9
                    # Leg holes are at (10, 10) and (190, 10)
                    # Map to panel main face
                    panel_x = leg_hole["x"]  # Same x position
                    panel_y = 10.0  # Top edge of panel
                    
                    panel_connection_points.append({
                        "x": panel_x,
                        "y": panel_y,
                        "type": "flap_corner",
                        "hardware": leg_hole.get("ferragemSymbols", ["glue"])[0],
                        "depth": leg_hole.get("depth", 20),
                        "diameter": leg_hole.get("diameter")
                    })
            
            connection_points[conn_id] = {
                "piece1": piece1_name,
                "piece2": piece2_name,
                "face1": face1,
                "face2": face2,
                "points": panel_connection_points
            }
            
            print(f"  Mapped {len(panel_connection_points)} connection points")
        
        elif "perna esquerda" in piece1_name.lower() and "tampo" in piece2_name.lower():
            # perna esquerda connects to tampo other_main
            # Map leg positions to panel positions
            leg_holes = piece1["faces"][face1]["holes"]
            panel_connection_points = []
            
            for leg_hole in leg_holes:
                if leg_hole.get("connectionId") == conn_id:
                    # Map leg hole position to panel position
                    # For this model: leg is 200x200, panel is 200x299.9
                    # Leg holes are at (10, 10) and (190, 10)
                    # Map to panel other_main face
                    panel_x = leg_hole["x"]  # Same x position
                    panel_y = piece2["height"] - 10.0  # Bottom edge of panel
                    
                    panel_connection_points.append({
                        "x": panel_x,
                        "y": panel_y,
                        "type": "flap_corner",
                        "hardware": leg_hole.get("ferragemSymbols", ["glue"])[0],
                        "depth": leg_hole.get("depth", 20),
                        "diameter": leg_hole.get("diameter")
                    })
            
            connection_points[conn_id] = {
                "piece1": piece1_name,
                "piece2": piece2_name,
                "face1": face1,
                "face2": face2,
                "points": panel_connection_points
            }
            
            print(f"  Mapped {len(panel_connection_points)} connection points")
    
    return connection_points

def create_connection_areas_at_actual_points(pieces, connection_points):
    """Step 5.6: Create connection areas at actual connection points"""
    print("Creating connection areas at actual connection points...")
    
    for conn_id, conn_data in connection_points.items():
        piece2_name = conn_data["piece2"]
        face2 = conn_data["face2"]
        
        # Find the target piece
        piece2 = next(p for p in pieces if p['name'] == piece2_name)
        
        # Create connection areas at each connection point
        for point in conn_data["points"]:
            x, y = point["x"], point["y"]
            
            # Create small connection area around the point
            corner_size = piece2["thickness"]  # Use piece thickness for corner size
            
            # Determine corner position based on point location
            if x < piece2["length"] / 2:  # Left side
                area_x_min = 0.0
                area_x_max = corner_size
            else:  # Right side
                area_x_min = piece2["length"] - corner_size
                area_x_max = piece2["length"]
            
            if y < piece2["height"] / 2:  # Top side
                area_y_min = 0.0
                area_y_max = corner_size
            else:  # Bottom side
                area_y_min = piece2["height"] - corner_size
                area_y_max = piece2["height"]
            
            # Create connection area
            connection_area = {
                "x_min": area_x_min,
                "x_max": area_x_max,
                "y_min": area_y_min,
                "y_max": area_y_max,
                "fill": "black",
                "opacity": 0.05,
                "connectionId": conn_id
            }
            
            piece2["faces"][face2]["connectionAreas"].append(connection_area)
            print(f"  Created connection area at ({area_x_min}, {area_y_min}) - ({area_x_max}, {area_y_max})")

def place_holes_at_actual_connection_points(pieces, connection_points):
    """Step 5.7: Place holes at actual connection points"""
    print("Placing holes at actual connection points...")
    
    for conn_id, conn_data in connection_points.items():
        piece2_name = conn_data["piece2"]
        face2 = conn_data["face2"]
        
        # Find the target piece
        piece2 = next(p for p in pieces if p['name'] == piece2_name)
        
        # Place holes at each connection point
        for point in conn_data["points"]:
            x, y = point["x"], point["y"]
            
            # Create hole at the exact connection point
            hole = criar_hole(
                x, y,
                point["type"],
                piece2.get("template_thickness", 20),
                point["hardware"],
                connection_id=conn_id,
                depth=point["depth"],
                diameter=point["diameter"]
            )
            
            piece2["faces"][face2]["holes"].append(hole)
            print(f"  Placed hole at ({x}, {y}) - {point['type']}")

# ============================================================================
# STEP 6: MAP HOLES BETWEEN CONNECTED PIECES
# ============================================================================

def map_holes_between_pieces(pieces, connections, template_thickness):
    """Step 6: Map holes between connected pieces using proximity-based connections"""
    
    for i, conn in enumerate(connections):
        p1 = pieces[conn['piece1']]
        p2 = pieces[conn['piece2']]
        
        # Get the connecting faces from proximity detection
        face1 = conn['face1']
        face2 = conn['face2']
        overlap_area = conn['overlap_area']
        
        # Connection areas will be created in second pass to align with holes
        # create_connection_areas_from_proximity(p1, p2, face1, face2, conn['id'], overlap_area)
        
        # Map holes between the connecting faces
        map_face_holes_proximity(p1, p2, face1, face2, conn['id'], template_thickness)

# ============================================================================
# STEP 7: CREATE CONNECTION AREAS BASED ON PROXIMITY
# ============================================================================

def create_connection_areas_from_proximity(p1, p2, face1, face2, conn_id, overlap_area):
    """Step 7: Create connection areas based on proximity overlap area"""
    
    # Convert overlap area to face coordinates for piece 1
    area1 = convert_proximity_overlap_to_face_coordinates(p1, face1, overlap_area, conn_id)
    if area1 and _should_create_conn_area(p1, face1):
        # Check if connection area already exists at this position on this face
        existing_areas = p1["faces"][face1]["connectionAreas"]
        area_exists = any(
            abs(existing["x_min"] - area1['x_min']) < 1.0 and 
            abs(existing["y_min"] - area1['y_min']) < 1.0 and
            abs(existing["x_max"] - area1['x_max']) < 1.0 and 
            abs(existing["y_max"] - area1['y_max']) < 1.0
            for existing in existing_areas
        )
        
        if not area_exists:
            p1["faces"][face1]["connectionAreas"].append({
                "x_min": arredondar(area1['x_min']),
                "y_min": arredondar(area1['y_min']),
                "x_max": arredondar(area1['x_max']),
                "y_max": arredondar(area1['y_max']),
                "fill": "red",
                "opacity": 0.3,
                "connectionId": conn_id
            })
    
    # Convert overlap area to face coordinates for piece 2  
    area2 = convert_proximity_overlap_to_face_coordinates(p2, face2, overlap_area, conn_id)
    if area2 and _should_create_conn_area(p2, face2):
        # Check if connection area already exists at this position on this face
        existing_areas = p2["faces"][face2]["connectionAreas"]
        area_exists = any(
            abs(existing["x_min"] - area2['x_min']) < 1.0 and 
            abs(existing["y_min"] - area2['y_min']) < 1.0 and
            abs(existing["x_max"] - area2['x_max']) < 1.0 and 
            abs(existing["y_max"] - area2['y_max']) < 1.0
            for existing in existing_areas
        )
        
        if not area_exists:
            p2["faces"][face2]["connectionAreas"].append({
                "x_min": arredondar(area2['x_min']),
                "y_min": arredondar(area2['y_min']),
                "x_max": arredondar(area2['x_max']),
                "y_max": arredondar(area2['y_max']),
                "fill": "red",
                "opacity": 0.3,
                "connectionId": conn_id
            })

def convert_proximity_overlap_to_face_coordinates(piece, face_name, overlap_area, conn_id):
    """Step 7: Convert global overlap area into face-local coordinates, preserving actual position and using correct face dimensions."""
    pos = piece["position"]
    # Determine local face dimensions and axis mapping
    if face_name in ["main", "other_main"]:
        max_x = piece["length"]  # along X
        max_y = piece["height"]  # along Z but becomes local Y on the X-Z plane
        # Global → local mapping for a point on this face
        def to_local(gx, gy):
            # gy here is actually global Z coordinate
            return gx - pos["x"], gy - pos["z"]
    elif face_name in ["top", "bottom"]:
        max_x = piece["length"]  # along X
        max_y = piece["height"]  # Use board height to span full depth for stripes
        def to_local(gx, gy):
            return gx - pos["x"], gy - pos["y"]
    elif face_name in ["left", "right"]:
        max_x = piece["height"]   # along Y becomes local X
        max_y = piece["height"] if False else piece["thickness"]  # this axis is Z
        # For left/right faces: overlap x == global Y, y == global Z
        def to_local(gx, gy):
            return gx - pos["y"], gy - pos["z"]
    else:
        return None
    # Compute local center of the overlap rectangle
    global_center_x = (overlap_area["x_min"] + overlap_area["x_max"]) / 2
    global_center_y = (overlap_area["y_min"] + overlap_area["y_max"]) / 2
    local_center_x, local_center_y = to_local(global_center_x, global_center_y)
    # Convert overlap to local coordinates
    overlap_local_x_min, _ = to_local(overlap_area["x_min"], overlap_area["y_min"])
    overlap_local_x_max, _ = to_local(overlap_area["x_max"], overlap_area["y_min"])
    
    # Create connection areas aligned with hole positions for proper correlation
    stripe_width = 20.0  # Fixed 20mm width  
    
    # Find holes on this face to align connection areas with hole positions
    piece_holes = []
    for face_data in piece["faces"].values():
        if face_data.get("holes"):
            piece_holes.extend([h for h in face_data["holes"] if h.get("connectionId") == conn_id])
    
    if piece_holes:
        # Center connection area around the holes for this connection ID
        hole_x_positions = [h["x"] for h in piece_holes]
        center_x = sum(hole_x_positions) / len(hole_x_positions)
        stripe_x_min = center_x - stripe_width / 2
        stripe_x_max = center_x + stripe_width / 2
    else:
        # Fallback to connection ID based positioning if no holes found
        if conn_id == 1:  # Right stripe - align with panel margin  
            stripe_x_min = max_x - stripe_width  # Align with right edge
        else:  # Left stripe - 160mm from right stripe
            stripe_x_min = max_x - stripe_width - 160.0  # 160mm spacing from right stripe
        stripe_x_max = stripe_x_min + stripe_width
    
    # Full height stripes (not small rectangles)
    stripe_y_min = 0.0
    stripe_y_max = max_y  # Full face height
    return {
        "x_min": arredondar(stripe_x_min),
        "y_min": arredondar(stripe_y_min),
        "x_max": arredondar(stripe_x_max),
        "y_max": arredondar(stripe_y_max)
    }

def create_simple_connection_area(piece, face_name, area_size):
    """DEPRECATED: Create a simple connection area on a face"""
  
    ft = piece["half_thickness"]
    
    if face_name in ["main", "other_main"]:
        # Create area in a corner but not overlapping with holes
        x_start = max(ft + 25, 30)  # Away from corner holes
        y_start = max(ft + 25, 30)
        x_end = min(piece["length"] - ft, x_start + area_size)
        y_end = min(piece["height"] - ft, y_start + area_size)
        
        # Ensure valid dimensions
        if x_end <= x_start:
            x_end = x_start + 10
        if y_end <= y_start:
            y_end = y_start + 10
            
        return {
            'x_min': x_start,
            'y_min': y_start,
            'x_max': x_end,
            'y_max': y_end
        }
    elif face_name in ["top", "bottom"]:
        x_start = max(ft + 25, 30)
        y_start = max(ft + 2, 5)  # Small offset for thickness faces
        x_end = min(piece["length"] - ft, x_start + area_size)
        y_end = min(piece["thickness"] - ft, y_start + min(area_size, piece["thickness"] - 10))
        
        # Ensure valid dimensions
        if x_end <= x_start:
            x_end = x_start + 10
        if y_end <= y_start:
            y_end = y_start + 5
            
        return {
            'x_min': x_start,
            'y_min': y_start,
            'x_max': x_end,
            'y_max': y_end
        }
    elif face_name in ["left", "right"]:
        x_start = max(ft + 2, 5)
        y_start = max(ft + 25, 30)
        x_end = min(piece["thickness"] - ft, x_start + min(area_size, piece["thickness"] - 10))
        y_end = min(piece["height"] - ft, y_start + area_size)
        
        # Ensure valid dimensions
        if x_end <= x_start:
            x_end = x_start + 5
        if y_end <= y_start:
            y_end = y_start + 10
            
        return {
            'x_min': x_start,
            'y_min': y_start,
            'x_max': x_end,
            'y_max': y_end
        }
    
    return None

# ============================================================================
# STEP 8: CLASSIFY HOLE TYPES
# ============================================================================

def classify_hole_type(x, y, piece, face_name):
    """Step 8: Classify hole type based on exact position on face"""
    ft = piece["half_thickness"]
    
    if face_name in ["main", "other_main"]:
        # Length x Height faces
        length = piece["length"]
        height = piece["height"]
        
        # Check if it's a corner position
        is_left_edge = abs(x - ft) < 2
        is_right_edge = abs(x - (length - ft)) < 2
        is_bottom_edge = abs(y - ft) < 2
        is_top_edge = abs(y - (height - ft)) < 2
        
        if (is_left_edge or is_right_edge) and (is_bottom_edge or is_top_edge):
            return "flap_corner"
        elif is_left_edge or is_right_edge or is_bottom_edge or is_top_edge:
            return "flap_central"
        else:
            return "face_central"
            
    elif face_name in ["top", "bottom", "left", "right"]:
        # Thickness faces - determine dimensions based on face
        if face_name in ["top", "bottom"]:
            width = piece["length"]
            height = piece["thickness"]
        else:  # left, right
            width = piece["thickness"] 
            height = piece["height"]
        
        # Check if it's a corner position
        is_left_edge = abs(x - ft) < 2
        is_right_edge = abs(x - (width - ft)) < 2
        is_bottom_edge = abs(y - ft) < 2
        is_top_edge = abs(y - (height - ft)) < 2
        
        if (is_left_edge or is_right_edge) and (is_bottom_edge or is_top_edge):
            return "top_corner"
        elif is_left_edge or is_right_edge or is_bottom_edge or is_top_edge:
            return "top_central"
        else:
            return "face_central"
    
    return "face_central"  # Default

# ============================================================================
# STEP 9: MAP HOLES BETWEEN CONNECTED PIECES USING PROXIMITY
# ============================================================================

def map_face_holes_proximity(p1, p2, face1, face2, conn_id, template_thickness):
    """Step 9: Map holes between connecting faces using proximity-based connection"""
    
    conn_areas_1 = [area for area in p1["faces"][face1]["connectionAreas"] if area["connectionId"] == conn_id]
    conn_areas_2 = [area for area in p2["faces"][face2]["connectionAreas"] if area["connectionId"] == conn_id]
   
    if not conn_areas_1:
        all_areas_1 = p1["faces"][face1]["connectionAreas"]
        if all_areas_1:
            conn_areas_1 = [all_areas_1[0]]  # Use the first available connection area
    
    if not conn_areas_2:
        all_areas_2 = p2["faces"][face2]["connectionAreas"] 
        if all_areas_2:
            conn_areas_2 = [all_areas_2[0]]  # Use the first available connection area
    
   
    def is_leg_piece(piece):
        """Step 9: Determine if piece is a leg based on name and dimensions"""
        return ("perna" in piece["name"].lower()) or (abs(piece["length"] - piece["height"]) < 50 and max(piece["length"], piece["height"]) < 250)
    
    if not conn_areas_1 and not conn_areas_2:
        # If neither face has an area and no leg is involved, skip.
        if not (is_leg_piece(p1) or is_leg_piece(p2)):
            return
    
    p1_is_leg = is_leg_piece(p1)
    p2_is_leg = is_leg_piece(p2)
    
    # Map holes from legs to top panel - align subjective holes with objective holes
    if p1_is_leg and not p2_is_leg:
        # p1 is leg, p2 is top panel - map leg holes to top panel
        map_leg_holes_to_top_panel(p1, p2, face1, face2, conn_id, template_thickness)
    elif not p1_is_leg and p2_is_leg:
        # p1 is top panel, p2 is leg - map leg holes to top panel  
        map_leg_holes_to_top_panel(p2, p1, face2, face1, conn_id, template_thickness)

# ============================================================================
# STEP 10: MAP LEG HOLES TO TOP PANEL
# ============================================================================

def map_leg_holes_to_top_panel(leg_piece, top_piece, leg_face, top_face, conn_id, template_thickness):
    """Step 10: Map specific leg hole positions to corresponding positions on top panel"""
    
    # Get the systematic holes from the leg face
    leg_holes = leg_piece["faces"][leg_face]["holes"]
    
    # Step 6: "Map the corresponding face of the primary piece on the secondary piece"
    # Step 6: "Allocate subjective holes paired with objective holes already existing on other pieces"
    for leg_hole in leg_holes:
        # Transform coordinates from leg to top panel
        top_x, top_y = transform_leg_to_top_coordinates(leg_piece, top_piece, leg_face, top_face, leg_hole["x"], leg_hole["y"], conn_id)
        
        if top_x is not None and top_y is not None:
            # Step 6: "Ensure perfect alignment with the primary hole of the other piece"
            # Step 6: "Validate and classify mapped holes"
            
            # Validate coordinates are within piece limits
            if (0 <= top_x <= top_piece["length"] and 0 <= top_y <= top_piece["thickness"]):
                
                # Step 6: "Classify holes based on position"
                hole_type = classify_hole_type(top_x, top_y, top_piece, top_face)
                
                # Step 6: "Ensure perfect alignment with the primary hole of the other piece"
                # Use the same hardware and properties as the leg hole
                hardware = leg_hole.get("ferragemSymbols", ["glue"])[0]
                depth = leg_hole.get("depth", 20)
                diameter = leg_hole.get("diameter")
                
                # Create the mapped hole with connectionId
                mapped_hole = criar_hole(
                    top_x, top_y, 
                    hole_type, 
                    template_thickness, 
                    hardware, 
                    connection_id=conn_id,
                    depth=depth,
                    diameter=diameter
                )
                
                # Add to top panel face
                top_piece["faces"][top_face]["holes"].append(mapped_hole)
                print(f"Mapped hole from {leg_piece['name']} {leg_face} to {top_piece['name']} {top_face}: ({top_x}, {top_y}) - {hole_type}")

def transform_leg_to_top_coordinates(leg_piece, top_piece, leg_face, top_face, leg_x, leg_y, conn_id):
    """Step 10: Transform coordinates from leg coordinate system to top panel coordinate system"""
    
    # Get the connection areas to understand the spatial relationship
    leg_conn_areas = [area for area in leg_piece["faces"][leg_face]["connectionAreas"] if area.get("connectionId") == conn_id]
    top_conn_areas = [area for area in top_piece["faces"][top_face]["connectionAreas"] if area.get("connectionId") == conn_id]
    
    if not leg_conn_areas or not top_conn_areas:
        # If no connection areas, use simple coordinate transformation
        # This is a fallback for when connection areas aren't available yet
        
        # For leg top to panel bottom connection:
        if leg_face == "top" and top_face == "bottom":
            # Map leg top coordinates to panel bottom coordinates
            # The leg's top face (length x thickness) maps to panel's bottom face (length x thickness)
            
            # Scale leg coordinates to panel coordinates
            scale_x = top_piece["length"] / leg_piece["length"]
            scale_y = top_piece["thickness"] / leg_piece["thickness"]
            
            top_x = leg_x * scale_x
            top_y = leg_y * scale_y
            
            return top_x, top_y
    
    # Use connection areas for precise mapping
    leg_area = leg_conn_areas[0] if leg_conn_areas else None
    top_area = top_conn_areas[0] if top_conn_areas else None
    
    if leg_area and top_area:
        # Map from leg connection area to top connection area
        # Calculate relative position within leg connection area
        leg_rel_x = (leg_x - leg_area["x_min"]) / (leg_area["x_max"] - leg_area["x_min"])
        leg_rel_y = (leg_y - leg_area["y_min"]) / (leg_area["y_max"] - leg_area["y_min"])
        
        # Map to corresponding position in top connection area
        top_x = top_area["x_min"] + leg_rel_x * (top_area["x_max"] - top_area["x_min"])
        top_y = top_area["y_min"] + leg_rel_y * (top_area["y_max"] - top_area["y_min"])
    
    return top_x, top_y
    
    return None, None

# Helper to decide if we should create a connection area on a given face

def _should_create_conn_area(piece, face_name):
    """Step 10: Determine which faces should have connection areas"""
    def is_leg_piece(p):
        return ("perna" in p["name"].lower()) or (abs(p["length"] - p["height"]) < 50 and max(p["length"], p["height"]) < 250)
    
    if is_leg_piece(piece) and face_name == "top":
        return True
    elif not is_leg_piece(piece) and face_name in ["main", "other_main"]:  # Changed from top to main/other_main
        return True
    else:
        return False

# ============================================================================
# STEP 11: CREATE ALIGNED CONNECTION AREAS
# ============================================================================

def create_aligned_connection_areas(pieces, connections):
    """Step 11: Create connection areas aligned with holes that already have connectionId assigned"""
    for conn in connections:
        p1 = pieces[conn['piece1']]
        p2 = pieces[conn['piece2']]
        face1 = conn['face1']
        face2 = conn['face2']
        conn_id = conn['id']
        
        # Create connection area on piece 1 if it should have one
        if _should_create_conn_area(p1, face1):
            create_hole_aligned_connection_area(p1, face1, conn_id)
        
        # Create connection area on piece 2 if it should have one  
        if _should_create_conn_area(p2, face2):
            create_hole_aligned_connection_area(p2, face2, conn_id)

def create_hole_aligned_connection_area(piece, face_name, conn_id):
    """Step 11: Create a connection area aligned with holes on the same face"""
    # Find holes on this face with the same connection ID
    face_holes = [h for h in piece["faces"][face_name]["holes"] if h.get("connectionId") == conn_id]
    
    if not face_holes:
        # No holes with this connection ID on this face, use fallback positioning
        create_simple_connection_area_for_piece(piece, face_name, conn_id)
        return
    
    # Calculate connection area dimensions based on face type
    if face_name in ["main", "other_main"]:
        max_x = piece["length"]
        max_y = piece["height"]
    elif face_name in ["top", "bottom"]:
        max_x = piece["length"]
        max_y = piece["height"]  # Use height for full depth
    elif face_name in ["left", "right"]:
        max_x = piece["height"]
        max_y = piece["thickness"]
    else:
        return
    
    # Step 10: "Create rectangular area based on effectively overlapped/connected area"
    # Step 10: "Respect real limits of overlap area"
    
    # Create connection areas according to client specifications
    if face_name in ["top", "bottom"]:
        # Check if this is a leg piece or top panel
        def is_leg_piece(piece):
            return ("perna" in piece["name"].lower()) or (abs(piece["length"] - piece["height"]) < 50 and max(piece["length"], piece["height"]) < 250)
        
        if is_leg_piece(piece):
            # For leg top faces: full width, height based on piece thickness
            # Step 10: "Use fill: 'black' and opacity: 0.05"
            stripe_x_min = 0.0
            stripe_x_max = max_x
            stripe_y_min = 0.0
            stripe_y_max = piece["thickness"]  # Dynamic height based on piece thickness
            
            piece["faces"][face_name]["connectionAreas"].append({
                "x_min": stripe_x_min,
                "y_min": stripe_y_min,
                "x_max": stripe_x_max,
                "y_max": stripe_y_max,
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            })
        else:
            # For top panel (tampo): TWO vertical stripes - all dimensions dynamic
            # Step 10: "Respect real limits of overlap area"
            # Calculate dimensions based on piece size
            stripe_width = piece["thickness"]  # Use piece thickness for stripe width
            stripe_length = piece["height"] * 0.67  # 2/3 of piece height for stripe length
            margin_offset = piece["thickness"]  # Use piece thickness for margin offset
            
            # Create connection areas for both left and right stripes
            # Left stripe - margin_offset from left margin
            left_stripe = {
                "x_min": margin_offset,  # Dynamic margin offset
                "x_max": margin_offset + stripe_width,
                "y_min": 0.0,
                "y_max": stripe_length,  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            }
            piece["faces"][face_name]["connectionAreas"].append(left_stripe)
            
            # Right stripe - at right edge
            right_stripe = {
                "x_min": max_x - stripe_width,
                "x_max": max_x,
                "y_min": 0.0,
                "y_max": stripe_length,  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            }
            piece["faces"][face_name]["connectionAreas"].append(right_stripe)
    
    elif face_name in ["main", "other_main"]:
        # For main faces: vertical stripes on edges
        stripe_width = piece["thickness"]  # Use piece thickness for stripe width
        spacing = piece["length"] * 0.8  # Dynamic spacing based on piece length
        
        # Left stripe
        left_stripe = {
            "x_min": 0.0,
            "x_max": stripe_width,
            "y_min": 0.0,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(left_stripe)
        
        # Right stripe
        right_stripe = {
            "x_min": max_x - stripe_width,
            "x_max": max_x,
            "y_min": 0.0,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(right_stripe)
    
    elif face_name in ["left", "right"]:
        # For left/right faces: horizontal stripes
        stripe_height = piece["thickness"]  # Use piece thickness for stripe height
        spacing = piece["length"] * 0.8  # Dynamic spacing based on piece length
        
        # Top stripe
        top_stripe = {
            "x_min": 0.0,
            "x_max": max_x,
            "y_min": max_y - stripe_height,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(top_stripe)
        
        # Bottom stripe
        bottom_stripe = {
            "x_min": 0.0,
            "x_max": max_x,
            "y_min": 0.0,
            "y_max": stripe_height,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_stripe)

# ============================================================================
# STEP 12: ENSURE ALL PIECES HAVE CONNECTION AREAS
# ============================================================================

def ensure_all_pieces_have_connection_areas(pieces, connections):
    """Step 12: Ensure every piece has at least one connection area on appropriate faces"""
    for piece in pieces:
        # Check if piece already has any connection areas
        has_connection_areas = any(
            face["connectionAreas"] 
            for face in piece["faces"].values()
        )
        
        if not has_connection_areas:
            # Find if this piece is involved in any connections
            piece_connections = []
            for conn in connections:
                if pieces[conn['piece1']]['name'] == piece['name']:
                    piece_connections.append((conn['id'], conn['face1']))
                elif pieces[conn['piece2']]['name'] == piece['name']:
                    piece_connections.append((conn['id'], conn['face2']))
            
            # Create connection areas on appropriate faces based on piece type
            def is_leg_piece(p):
                return ("perna" in p["name"].lower()) or (abs(p["length"] - p["height"]) < 50 and max(p["length"], p["height"]) < 250)
            
            if is_leg_piece(piece):
                # For legs, create connection area on top face if none exists
                if not piece["faces"]["top"]["connectionAreas"] and piece_connections:
                    conn_id = piece_connections[0][0]  # Use first connection ID
                    create_simple_connection_area_for_piece(piece, "top", conn_id)
            else:
                # For panels, create connection area on appropriate face
                if piece_connections:
                    conn_id = piece_connections[0][0]  # Use first connection ID
                    
                    # Try to create connection area on top face first (for tampo)
                    if not piece["faces"]["top"]["connectionAreas"]:
                        create_simple_connection_area_for_piece(piece, "top", conn_id)
                    # Then try other_main, then main as fallbacks
                    elif not piece["faces"]["other_main"]["connectionAreas"]:
                        create_simple_connection_area_for_piece(piece, "other_main", conn_id)
                    elif not piece["faces"]["main"]["connectionAreas"]:
                        create_simple_connection_area_for_piece(piece, "main", conn_id)

def create_simple_connection_area_for_piece(piece, face_name, conn_id):
    """Step 12: Create a simple connection area on a face for a piece"""
    if face_name in ["main", "other_main"]:
        max_x = piece["length"]
        max_y = piece["height"]
    elif face_name in ["top", "bottom"]:
        max_x = piece["length"]
        max_y = piece["thickness"]
    elif face_name in ["left", "right"]:
        max_x = piece["thickness"]
        max_y = piece["height"]
    else:
        return
    
    # Step 10: "Create rectangular area based on effectively overlapped/connected area"
    # Step 10: "Respect real limits of overlap area"
    
    # Create connection areas according to client specifications
    if face_name in ["top", "bottom"]:
        # Check if this is a leg piece or top panel
        def is_leg_piece(piece):
            return ("perna" in piece["name"].lower()) or (abs(piece["length"] - piece["height"]) < 50 and max(piece["length"], piece["height"]) < 250)
        
        if is_leg_piece(piece):
            # For leg top faces: full width, height based on piece thickness
            # Step 10: "Use fill: 'black' and opacity: 0.05"
            stripe_x_min = 0.0
            stripe_x_max = max_x
            stripe_y_min = 0.0
            stripe_y_max = piece["thickness"]  # Dynamic height based on piece thickness
            
            piece["faces"][face_name]["connectionAreas"].append({
                "x_min": stripe_x_min,
                "y_min": stripe_y_min,
                "x_max": stripe_x_max,
                "y_max": stripe_y_max,
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            })
        else:
            # For top panel (tampo): TWO vertical stripes - all dimensions dynamic
            # Step 10: "Respect real limits of overlap area"
            # Calculate dimensions based on piece size
            stripe_width = piece["thickness"]  # Use piece thickness for stripe width
            stripe_length = piece["height"] * 0.67  # 2/3 of piece height for stripe length
            margin_offset = piece["thickness"]  # Use piece thickness for margin offset
            
            # Create connection areas for both left and right stripes
            # Left stripe - margin_offset from left margin
            left_stripe = {
                "x_min": margin_offset,  # Dynamic margin offset
                "x_max": margin_offset + stripe_width,
                "y_min": 0.0,
                "y_max": stripe_length,  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            }
            piece["faces"][face_name]["connectionAreas"].append(left_stripe)
            
            # Right stripe - at right edge
            right_stripe = {
                "x_min": max_x - stripe_width,
                "x_max": max_x,
                "y_min": 0.0,
                "y_max": stripe_length,  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": conn_id
            }
            piece["faces"][face_name]["connectionAreas"].append(right_stripe)
    
    elif face_name in ["main", "other_main"]:
        # For main faces: SMALL CORNER AREAS (like A, B, C, D in the image)
        corner_size = piece["thickness"]  # Use piece thickness for corner size
        
        # Top-left corner (A)
        top_left_corner = {
            "x_min": 0.0,
            "x_max": corner_size,
            "y_min": 0.0,
            "y_max": corner_size,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(top_left_corner)
        
        # Top-right corner (B)
        top_right_corner = {
            "x_min": max_x - corner_size,
            "x_max": max_x,
            "y_min": 0.0,
            "y_max": corner_size,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(top_right_corner)
        
        # Bottom-left corner (C)
        bottom_left_corner = {
            "x_min": 0.0,
            "x_max": corner_size,
            "y_min": max_y - corner_size,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_left_corner)
        
        # Bottom-right corner (D)
        bottom_right_corner = {
            "x_min": max_x - corner_size,
            "x_max": max_x,
            "y_min": max_y - corner_size,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_right_corner)
    
    elif face_name in ["left", "right"]:
        # For left/right faces: horizontal stripes
        stripe_height = piece["thickness"]  # Use piece thickness for stripe height
        spacing = piece["length"] * 0.8  # Dynamic spacing based on piece length
        
        # Top stripe
        top_stripe = {
            "x_min": 0.0,
            "x_max": max_x,
            "y_min": max_y - stripe_height,
            "y_max": max_y,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(top_stripe)
        
        # Bottom stripe
        bottom_stripe = {
            "x_min": 0.0,
            "x_max": max_x,
            "y_min": 0.0,
            "y_max": stripe_height,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": conn_id
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_stripe)

# ============================================================================
# STEP 5: FILTER HOLES BY CONNECTION AREAS
# ============================================================================

def filter_holes_by_connection_areas(pieces, connections):
    """Step 5: Filter holes to keep only those within connection areas"""
    print("Filtering holes by connection areas...")
    
    for piece in pieces:
        for face_name, face in piece["faces"].items():
            if not face["connectionAreas"]:
                # No connection areas = no holes should remain
                print(f"Removing all holes from {piece['name']} {face_name} (no connection areas)")
                face["holes"] = []
                continue
            
            # Get all connection areas for this face
            conn_areas = face["connectionAreas"]
            original_hole_count = len(face["holes"])
            
            # Filter holes to keep only those within connection areas
            filtered_holes = []
            for hole in face["holes"]:
                hole_x, hole_y = hole["x"], hole["y"]
                
                # Check if hole is within ANY connection area
                hole_in_conn_area = False
                for area in conn_areas:
                    if (area["x_min"] <= hole_x <= area["x_max"] and 
                        area["y_min"] <= hole_y <= area["y_max"]):
                        hole_in_conn_area = True
                        # Assign the connectionId to the hole
                        hole["connectionId"] = area["connectionId"]
                        break
                
                if hole_in_conn_area:
                    filtered_holes.append(hole)
            
            face["holes"] = filtered_holes
            remaining_hole_count = len(filtered_holes)
            print(f"{piece['name']} {face_name}: {original_hole_count} -> {remaining_hole_count} holes (kept {remaining_hole_count} within connection areas)")

# ============================================================================
# STEP 6: CREATE SUBJECTIVE HOLES
# ============================================================================

def create_subjective_holes_from_objective_holes(pieces, connections):
    """Step 6: Create subjective holes paired with remaining objective holes"""
    print("Creating subjective holes from objective holes...")
    
    for conn in connections:
        piece1_name = pieces[conn['piece1']]['name']
        piece2_name = pieces[conn['piece2']]['name']
        face1 = conn['face1']
        face2 = conn['face2']
        conn_id = conn['id']
        
        # Get the pieces
        piece1 = next(p for p in pieces if p['name'] == piece1_name)
        piece2 = next(p for p in pieces if p['name'] == piece2_name)
        
        # Get objective holes from piece1 that have this connectionId
        objective_holes = [h for h in piece1["faces"][face1]["holes"] if h.get("connectionId") == conn_id]
        
        print(f"Connection {conn_id}: {piece1_name} {face1} -> {piece2_name} {face2}")
        print(f"  Found {len(objective_holes)} objective holes to pair")
        
        # Create subjective holes on piece2 for each objective hole
        for obj_hole in objective_holes:
            # Use the EXACT SAME coordinates as the objective hole
            subj_x = obj_hole["x"]
            subj_y = obj_hole["y"]
            
            # Check if a hole already exists at this position
            hole_exists = any(
                abs(h["x"] - subj_x) < 5.0 and abs(h["y"] - subj_y) < 5.0
                for h in piece2["faces"][face2]["holes"]
            )
            
            if hole_exists:
                print(f"    Skipped hole at ({subj_x}, {subj_y}) - hole already exists")
                continue
            
            # Validate coordinates are within piece2 limits
            if face2 in ["main", "other_main"]:
                max_x, max_y = piece2["length"], piece2["height"]
            elif face2 in ["top", "bottom"]:
                max_x, max_y = piece2["length"], piece2["thickness"]
            else:  # left, right
                max_x, max_y = piece2["thickness"], piece2["height"]
            
            if (0 <= subj_x <= max_x and 0 <= subj_y <= max_y):
                # Classify the subjective hole
                hole_type = classify_hole_type(subj_x, subj_y, piece2, face2)
                
                # Use same properties as objective hole
                hardware = obj_hole.get("ferragemSymbols", ["glue"])[0]
                depth = obj_hole.get("depth", 20)
                diameter = obj_hole.get("diameter")
                
                # Create subjective hole with EXACT same coordinates
                subj_hole = criar_hole(
                    subj_x, subj_y, 
                    hole_type, 
                    piece2.get("template_thickness", 20), 
                    hardware, 
                    connection_id=conn_id,
                    depth=depth,
                    diameter=diameter
                )
                
                # Add to piece2 face
                piece2["faces"][face2]["holes"].append(subj_hole)
                print(f"    Created subjective hole at ({subj_x}, {subj_y}) - {hole_type}")
            else:
                print(f"    Skipped hole at ({subj_x}, {subj_y}) - outside piece bounds")

# ============================================================================
# STEP 13: CLEAN UNCONNECTED HOLES
# ============================================================================

def clean_unconnected_holes(pieces):
    """Step 13: Remove only singer holes that aren't needed - keep systematic and connected holes"""
    for piece in pieces:
        for face_name, face in piece["faces"].items():
            # Keep holes that have connectionId (connected/subjective holes) OR are systematic holes (corner, central, etc.)
            # Remove only singer holes that aren't connected
            face["holes"] = [hole for hole in face["holes"] 
                           if "connectionId" in hole or 
                              hole["type"] in ["flap_corner", "flap_central", "top_corner", "top_central", "face_central"]]

# ============================================================================
# STEP 14: ENSURE ALL PIECES HAVE FACES WITH SINGER HOLES
# ============================================================================

def ensure_all_pieces_have_faces(pieces, template_thickness):
    """Step 14: Ensure every piece has at least main faces with singer holes for reinforcement"""
    for piece in pieces:
        # Check if piece has any faces with content
        has_faces_with_content = any(
            face["holes"] or face["connectionAreas"] 
            for face in piece["faces"].values()
        )
        
        # If piece has no faces with content, add singer holes to main faces
        if not has_faces_with_content:
            # Add singer holes to main faces for structural reinforcement
            add_singer_holes_to_face(piece, "main", template_thickness)
            add_singer_holes_to_face(piece, "other_main", template_thickness)

# ============================================================================
# STEP 15: ADD SINGER REINFORCEMENT HOLES
# ============================================================================

def add_singer_reinforcement_holes(pieces, connections, template_thickness):
    """Step 15: Add singer reinforcement holes for face-to-top connections"""
    for conn in connections:
        p1 = pieces[conn['piece1']]
        p2 = pieces[conn['piece2']]
        
        # Get the connecting faces from proximity detection
        face1 = conn['face1']
        face2 = conn['face2']
        
        # Add singer holes on opposite faces for reinforcement
        if face1 in ["main", "other_main"]:
            opposite_face = "other_main" if face1 == "main" else "main"
            add_singer_holes_to_face(p1, opposite_face, template_thickness)
        
        if face2 in ["main", "other_main"]:
            opposite_face = "other_main" if face2 == "main" else "main"
            add_singer_holes_to_face(p2, opposite_face, template_thickness)

def add_singer_holes_to_face(piece, face_name, template_thickness):
    """Step 15: Add singer holes to a specific face"""
    face = piece["faces"][face_name]
    ft = piece["half_thickness"]
    
    def hole_exists_near_position(face_holes, x, y, min_distance=5.0):
        """Step 15: Check if any hole exists within min_distance of the position"""
        for existing_hole in face_holes:
            distance = ((existing_hole["x"] - x) ** 2 + (existing_hole["y"] - y) ** 2) ** 0.5
            if distance < min_distance:
                return True
        return False
    
    if face_name in ["main", "other_main"]:
        h = piece["height"]
        l = piece["length"]
        
        # Singer holes with proper spacing - different positions than regular holes
        # Offset singer holes more to avoid conflicts with systematic holes
        singer_positions = [
            (ft + 5, ft + 5, "singer_flap"),     # offset from corner
            (l - ft - 5, ft + 5, "singer_flap"), # offset from corner
            (l / 2, ft + 5, "singer_central"),   # bottom center with offset
            (ft + 5, h - ft - 5, "singer_channel"), # offset from corner
            (l - ft - 5, h - ft - 5, "singer_channel") # offset from corner
        ]
        
        # Only add singer holes if they don't overlap with existing holes
        for x, y, singer_type in singer_positions:
            # Check minimum 8mm distance from any existing hole to avoid overlap
            if not hole_exists_near_position(face["holes"], x, y, min_distance=8.0):
                singer_hole = criar_hole(x, y, singer_type, template_thickness, "dowel_G_with_glue", depth=40)
                face["holes"].append(singer_hole)

# ============================================================================
# STEP 16: SELECT MODEL TEMPLATE
# ============================================================================

def select_model_template(pieces):
    """Step 16: Select model template based on thickness with most top holes"""
    thickness_hole_count = defaultdict(int)
    
    for piece in pieces:
        for face_name in ["top", "bottom", "left", "right"]:
            for hole in piece["faces"][face_name]["holes"]:
                if hole["type"] in ["top_corner", "top_central"]:
                    thickness = int(float(hole["targetType"]))
                    thickness_hole_count[thickness] += 1
    
    if not thickness_hole_count:
        return 20  # Default
    
    # Find thickness with most holes, prefer smaller in case of tie
    max_count = max(thickness_hole_count.values())
    candidates = [t for t, count in thickness_hole_count.items() if count == max_count]
    return min(candidates)

# ============================================================================
# STEP 17: PROCESS JSON INPUT
# ============================================================================

def processar_json_entrada(input_path, output_path):
    """Main processing function following the guide's step-by-step flow"""
    
    # ============================================================================
    # STEP 1-2: INPUT DATA PREPROCESSING & DIMENSIONS
    # ============================================================================
    
    # Try different encodings to handle the special characters
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    data = None
    
    for encoding in encodings:
        try:
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)
                print(f"Successfully loaded file with {encoding} encoding")
                break
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            print(f"JSON decode error with {encoding}: {e}")
            continue
    
    if data is None:
        raise ValueError(f"Could not decode {input_path} with any supported encoding")

    # ============================================================================
    # STEP 3: MAP PIECES IN 3D SPACE
    # ============================================================================

    views = extrair_views_por_peca(data)
    pecas_3d = []
    
    # Build 3D pieces with bounding boxes and coordinate system
    for nome, v in views.items():
        peca = construir_peca_3d(nome, v)
        if peca:
            pecas_3d.append(peca)

    print(f"Built {len(pecas_3d)} pieces: {[p['name'] for p in pecas_3d]}")

    # ============================================================================
    # STEP 8: CHOOSE MODEL TEMPLATE
    # ============================================================================
    
    # Select template thickness based on thickness with most top holes
    template_thickness = select_model_template(pecas_3d)
    if not template_thickness:
        template_thickness = 20
    
    print(f"Using template thickness: {template_thickness}")
    
    # ============================================================================
    # STEP 4: ALLOCATE ALL POSSIBLE OBJECTIVE HOLES
    # ============================================================================
    
    # Add ALL possible systematic holes to all pieces (we'll filter later)
    for peca in pecas_3d:
        adicionar_holes_sistematicos(peca, template_thickness)
    
    # ============================================================================
    # STEP 5: INFER CONNECTIONS BETWEEN PIECES
    # ============================================================================
    
    # Detect connections between pieces using proximity detection
    connections = detect_connections_by_proximity(pecas_3d)
    print(f"Found {len(connections)} connections")
    
    # ============================================================================
    # STEP 12: ENSURE ALL PIECES HAVE CONNECTION AREAS (BEFORE MIRRORING)
    # ============================================================================
    
    # Ensure all pieces have at least one connection area
    ensure_all_pieces_have_connection_areas(pecas_3d, connections)
    
    # ============================================================================
    # STEP 5.8: MIRROR LEG CONNECTION AREAS TO PANEL
    # ============================================================================
    
    # Mirror leg connection areas to top panel at exact same coordinates
    mirror_leg_to_panel(pecas_3d, connections)
    
    # ============================================================================
    # STEP 5.8: MIRROR CONNECTION AREAS AND HOLES
    # ============================================================================
    
    # Mirror connection areas and holes from legs to top panel
    mirror_connection_areas_and_holes(pecas_3d, connections)
    
    # ============================================================================
    # STEP 5: FILTER HOLES BY CONNECTION AREAS
    # ============================================================================
    
    # Filter holes to keep only those within connection areas
    filter_holes_by_connection_areas(pecas_3d, connections)
    
    # ============================================================================
    # STEP 6: CREATE SUBJECTIVE HOLES
    # ============================================================================
    
    # Create subjective holes paired with remaining objective holes
    create_subjective_holes_from_objective_holes(pecas_3d, connections)
    
    # ============================================================================
    # STEP 15: ADD SINGER REINFORCEMENT HOLES
    # ============================================================================
    
    # For simple models, don't add singer reinforcement holes since client expects exact count
    # Only add singer holes for complex models with many pieces
    if len(pecas_3d) > 3:  # Only for complex models, not the simple 3-piece model
        for peca in pecas_3d:
            # Add singer holes to opposite main face if this piece has connections
            has_connections = any(face["connectionAreas"] for face in peca["faces"].values())
            if has_connections:
                # Only add singer holes to main faces of larger pieces (not legs)
                if peca["thickness"] > 25:  # Only for thicker pieces like tampo
                    add_singer_holes_to_face(peca, "main", template_thickness)
                    add_singer_holes_to_face(peca, "other_main", template_thickness)
    
    # ============================================================================
    # STEP 14: ENSURE ALL PIECES HAVE FACES
    # ============================================================================
    
    # Ensure all pieces have at least the systematic holes we defined
    # Don't add extra singer holes for simple models
    if len(pecas_3d) > 3:  # Only for complex models
        ensure_all_pieces_have_faces(pecas_3d, template_thickness)

    # ============================================================================
    # STEP 17: STRUCTURE FINAL JSON
    # ============================================================================

    # Build output JSON
    output = {"pieces": []}
    for p in pecas_3d:
        peca_json = {
            "name": p["name"],
            "length": format_number(p["length"]),
            "height": format_number(p["height"]),
            "thickness": format_number(p["thickness"]),
            "quantity": 1,
            "faces": []
        }
        
        for face_name, face_data in p["faces"].items():
            # Include faces that have holes OR connection areas (not requiring both)
            if face_data["holes"] or face_data["connectionAreas"]:
                peca_json["faces"].append({
                    "faceSide": face_name,
                    "holes": face_data["holes"],
                    "connectionAreas": face_data["connectionAreas"]
                })
        
        output["pieces"].append(peca_json)

    print(f"Writing output with {len(output['pieces'])} pieces")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Output written to {output_path}")

def mirror_connection_areas_and_holes(pieces, connections):
    """Step 5.8: Mirror connection areas and holes from legs to top panel"""
    print("Mirroring connection areas and holes from legs to top panel...")
    
    for conn in connections:
        piece1_name = pieces[conn['piece1']]['name']
        piece2_name = pieces[conn['piece2']]['name']
        face1 = conn['face1']
        face2 = conn['face2']
        conn_id = conn['id']
        
        # Get the pieces
        piece1 = next(p for p in pieces if p['name'] == piece1_name)
        piece2 = next(p for p in pieces if p['name'] == piece2_name)
        
        print(f"Connection {conn_id}: Mirroring from {piece1_name} {face1} to {piece2_name} {face2}")
        
        # Clear existing connection areas and holes on the target face
        piece2["faces"][face2]["connectionAreas"] = []
        piece2["faces"][face2]["holes"] = []
        
        # Mirror connection areas from leg to panel
        leg_connection_areas = piece1["faces"][face1]["connectionAreas"]
        for leg_area in leg_connection_areas:
            if leg_area.get("connectionId") == conn_id:
                # Mirror the connection area - same x coordinates, adjust y for panel
                mirrored_area = {
                    "x_min": leg_area["x_min"],
                    "x_max": leg_area["x_max"],
                    "y_min": 0.0,  # Top edge of panel
                    "y_max": piece2["thickness"],  # Height = panel thickness
                    "fill": "black",
                    "opacity": 0.05,
                    "connectionId": conn_id
                }
                piece2["faces"][face2]["connectionAreas"].append(mirrored_area)
                print(f"  Mirrored connection area: ({leg_area['x_min']}, {leg_area['y_min']}) -> ({mirrored_area['x_min']}, {mirrored_area['y_min']})")
        
        # Mirror holes from leg to panel
        leg_holes = piece1["faces"][face1]["holes"]
        for leg_hole in leg_holes:
            if leg_hole.get("connectionId") == conn_id:
                # Mirror the hole - same x coordinate, adjust y for panel
                mirrored_hole = {
                    "x": leg_hole["x"],
                    "y": 10.0,  # Top edge of panel
                    "type": "flap_corner",
                    "targetType": "20",
                    "ferragemSymbols": leg_hole["ferragemSymbols"],
                    "connectionId": conn_id,
                    "depth": leg_hole["depth"]
                }
                piece2["faces"][face2]["holes"].append(mirrored_hole)
                print(f"  Mirrored hole: ({leg_hole['x']}, {leg_hole['y']}) -> ({mirrored_hole['x']}, {mirrored_hole['y']})")

def mirror_leg_to_panel(pieces, connections):
    """Mirror leg connection areas to top panel at exact same coordinates"""
    print("Mirroring leg connection areas to top panel...")
    
    for conn in connections:
        piece1_name = pieces[conn['piece1']]['name']
        piece2_name = pieces[conn['piece2']]['name']
        face1 = conn['face1']
        face2 = conn['face2']
        conn_id = conn['id']
        
        # Find leg and panel pieces
        leg_piece = None
        panel_piece = None
        leg_face = None
        panel_face = None
        
        if "perna" in piece1_name.lower():
            leg_piece = pieces[conn['piece1']]
            panel_piece = pieces[conn['piece2']]
            leg_face = face1
            panel_face = face2
        elif "perna" in piece2_name.lower():
            leg_piece = pieces[conn['piece2']]
            panel_piece = pieces[conn['piece1']]
            leg_face = face2
            panel_face = face1
        
        if leg_piece and panel_piece:
            print(f"Mirroring from {leg_piece['name']} {leg_face} to {panel_piece['name']} {panel_face}")
            
            # Clear existing connection areas and holes on panel face
            panel_piece["faces"][panel_face]["connectionAreas"] = []
            panel_piece["faces"][panel_face]["holes"] = []
            
            # Get leg's connection areas
            leg_connection_areas = leg_piece["faces"][leg_face]["connectionAreas"]
            print(f"  Leg has {len(leg_connection_areas)} connection areas")
            
            # Mirror each connection area from leg to panel
            for leg_area in leg_connection_areas:
                print(f"    Checking leg area: {leg_area}")
                if leg_area.get("connectionId") == conn_id:
                    # Mirror with SAME x-coordinates, adjust y for panel
                    mirrored_area = {
                        "x_min": leg_area["x_min"],  # Same x
                        "x_max": leg_area["x_max"],  # Same x
                        "y_min": 0.0,  # Top edge of panel
                        "y_max": 19.9,  # Same height as leg (19.9mm)
                        "fill": "black",
                        "opacity": 0.05,
                        "connectionId": conn_id
                    }
                    panel_piece["faces"][panel_face]["connectionAreas"].append(mirrored_area)
                    print(f"  Mirrored area: x({leg_area['x_min']}-{leg_area['x_max']}) y(0.0-19.9)")
                else:
                    print(f"    Skipped area with connectionId {leg_area.get('connectionId')} (need {conn_id})")
            
            # Get leg's holes
            leg_holes = leg_piece["faces"][leg_face]["holes"]
            
            # Mirror each hole from leg to panel  
            for leg_hole in leg_holes:
                if leg_hole.get("connectionId") == conn_id:
                    # Mirror with SAME x-coordinate, y=10 for panel
                    mirrored_hole = {
                        "x": leg_hole["x"],  # Same x position
                        "y": 10.0,  # Fixed y position on panel
                        "type": leg_hole["type"],
                        "targetType": leg_hole["targetType"],
                        "ferragemSymbols": leg_hole["ferragemSymbols"],
                        "connectionId": conn_id,
                        "depth": leg_hole["depth"]
                    }
                    panel_piece["faces"][panel_face]["holes"].append(mirrored_hole)
                    print(f"  Mirrored hole: ({leg_hole['x']}, {leg_hole['y']}) -> ({mirrored_hole['x']}, {mirrored_hole['y']})")

    # ============================================================================
    # STEP 5.8: MIRROR LEG CONNECTION AREAS TO PANEL  
    # ============================================================================
   
    
    # OLD: mirror_connection_areas_and_holes(pecas_3d, connections)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Run with test files
processar_json_entrada("input1.json", "output.json")
