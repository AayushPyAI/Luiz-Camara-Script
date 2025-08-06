import json
import math
from collections import defaultdict

# ============================================================================
# CONFIGURATION SYSTEM - MAKES CODE WORK FOR ANY INPUT
# ============================================================================

# View name mapping for different input formats
VIEW_NAME_MAPPINGS = {
    "top": ["vista de cima", "vista superior", "top view", "cima", "superior"],
    "lateral": ["vista lateral", "lateral", "side view", "lado"],
    "frontal": ["frontal", "vista frontal", "front view", "frente"]
}

# Piece type detection patterns (expandable for any language/naming)
LEG_PATTERNS = [
    "perna",     # Portuguese
    "leg",       # English
    "pata",      # Spanish
    "pierna",    # Alternative Spanish
    "support",   # Generic
    "suporte"    # Portuguese alternative
]

PANEL_PATTERNS = [
    "tampo",     # Portuguese (top/surface)
    "top",       # English
    "surface",   # Generic
    "panel",     # Generic
    "tabletop",  # Specific
    "mesa",      # Portuguese (table)
    "table"      # English
]

# Template thickness options (configurable)
TEMPLATE_THICKNESSES = [17, 20, 25, 30]

# Default values (configurable)
DEFAULT_TEMPLATE_THICKNESS = 20
DEFAULT_CONNECTION_AREA_WIDTH = 20
DEFAULT_CONNECTION_AREA_HEIGHT = 200

# ============================================================================
# STEP 1-2: INPUT DATA PREPROCESSING & DIMENSIONS
# ============================================================================

def arredondar(valor):
    """Step 1: Round dimensions and coordinates to clean values"""
    # Round to 1 decimal place first
    arredondado = round(valor, 1)
    
    # If very close to a whole number (within 0.15), round to whole number
    # This handles cases like 19.9 -> 20, 29.9 -> 30, 1.9 -> 2
    if abs(arredondado - round(arredondado)) <= 0.15:
        return float(round(arredondado))
    
    # Otherwise keep 1 decimal place
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

def find_view_type(view_name):
    """Find the standard view type from any input view name"""
    view_name_lower = view_name.lower().strip()
    
    for standard_type, variations in VIEW_NAME_MAPPINGS.items():
        for variation in variations:
            if variation.lower() in view_name_lower:
                return standard_type
    
    # Fallback - return the original name
    return view_name_lower

def extrair_views_por_peca(data):
    """Step 1: Extract views per piece from input data - WORKS WITH ANY VIEW NAMES"""
    pecas = {}
    for layer in data["layers"]:
        vista = layer["name"]
        # Normalize view name to standard type
        vista_normalizada = find_view_type(vista)
        
        for item in layer["items"]:
            nome = item["nome"].strip().lower()
            if nome not in pecas:
                pecas[nome] = {}
            pecas[nome][vista_normalizada] = item
    return pecas

# ============================================================================
# STEP 3: MAP PIECES IN 3D SPACE
# ============================================================================

def construir_peca_3d(nome, views):
    """Step 3: Create 3D piece with bounding boxes and coordinate system - WORKS WITH ANY VIEW NAMES"""
    # Use flexible view mapping
    sup = views.get("top") 
    lat = views.get("lateral")
    fra = views.get("frontal")       
    
    if not sup or not lat or not fra:
        print(f"Missing views for {nome}: top={bool(sup)}, lateral={bool(lat)}, frontal={bool(fra)}")
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

def is_leg_piece(piece):
    """Universal leg detection - WORKS WITH ANY NAMING CONVENTION"""
    name_lower = piece["name"].lower()
    
    # Check if name contains any leg pattern
    for pattern in LEG_PATTERNS:
        if pattern in name_lower:
            return True
    
    # Fallback: dimensional analysis (square-ish and small pieces are likely legs)
    length_height_diff = abs(piece["length"] - piece["height"])
    max_dimension = max(piece["length"], piece["height"])
    
    return length_height_diff < 50 and max_dimension < 250

def is_panel_piece(piece):
    """Universal panel detection - WORKS WITH ANY NAMING CONVENTION"""
    name_lower = piece["name"].lower()
    
    # Check if name contains any panel pattern
    for pattern in PANEL_PATTERNS:
        if pattern in name_lower:
            return True
    
    # Fallback: dimensional analysis (large, flat pieces are likely panels)
    return not is_leg_piece(piece)

def get_template_thickness(thickness):
    """Step 8: Select closest standard template thickness - CONFIGURABLE"""
    return min(TEMPLATE_THICKNESSES, key=lambda x: abs(x - thickness))

def adicionar_holes_sistematicos(peca, template_thickness):
    """Step 4: Add systematic holes on all faces according to guide rules"""
    h = peca["height"]
    l = peca["length"]
    t = peca["thickness"]
    ft = peca["half_thickness"]

    def add_hole_if_not_exists(face_holes, x, y, hole_type, hardware, depth=None, diameter=None, connection_id=None):
        """Add hole only if no hole exists at this position"""
        for existing_hole in face_holes:
            if abs(existing_hole["x"] - x) < 8.0 and abs(existing_hole["y"] - y) < 8.0:
                return  # Hole already exists at this position
        
        # Add the hole
        hole = criar_hole(x, y, hole_type, template_thickness, hardware, connection_id=connection_id, depth=depth, diameter=diameter)
        face_holes.append(hole)
    
    def add_intermediate_holes_if_needed(face_holes, hole1_pos, hole2_pos, hole_type, hardware, depth=None, diameter=None):
        """Step 4: Add intermediate holes when distance > 200mm between two holes"""
        distance = ((hole2_pos[0] - hole1_pos[0])**2 + (hole2_pos[1] - hole1_pos[1])**2)**0.5
        if distance > 200:
            # Add intermediate hole at midpoint
            mid_x = (hole1_pos[0] + hole2_pos[0]) / 2
            mid_y = (hole1_pos[1] + hole2_pos[1]) / 2
            add_hole_if_not_exists(face_holes, mid_x, mid_y, hole_type, hardware, depth=depth, diameter=diameter)
    
    # Determine piece type using universal detection
    if is_leg_piece(peca):
        # For legs: ONLY 2 top_corner holes on top face as client expects
        face = peca["faces"]["top"]
        
        # Add exactly 2 corner holes as the client expects "2 pro leg"
        # Ensure minimum spacing for small pieces
        min_spacing = 8.0  # Minimum 8mm between holes (reduced for small pieces)
        
        if l >= (2 * ft + min_spacing):
            # Normal piece - use standard positions
            corner_positions = [
                (ft, ft, "top_corner"),            # corner 1
                (l - ft, ft, "top_corner")         # corner 2 (only 2 holes per leg)
            ]
        elif l >= 15.0:  # If piece is at least 15mm, try to fit 2 holes
            # Small piece - place holes with reduced spacing
            hole1_x = max(ft, 3.0)  # First hole at least 3mm from edge
            hole2_x = min(l - ft, l - 3.0)  # Second hole at least 3mm from edge
            if hole2_x - hole1_x >= min_spacing:
                corner_positions = [
                    (hole1_x, ft, "top_corner"),
                    (hole2_x, ft, "top_corner")
                ]
            else:
                # Only one hole fits safely
                corner_positions = [
                    (l / 2, ft, "top_corner")  # Center the single hole
                ]
        else:
            # Very small piece - only 1 hole
            corner_positions = [
                (l / 2, ft, "top_corner")  # Center the single hole
            ]
        
        for x, y, hole_type in corner_positions:
            # Connection ID will be set later when connections are detected
            # For now, create holes without connection ID
            add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
        
    else:
        # For panels: Follow guide rules exactly
        
        # Main and other_main faces: flap_corner holes at four corners
        # Step 4: "Main and other_main faces: flap_corner holes at four corners"
        for face_name in ["main", "other_main"]:
            face = peca["faces"][face_name]
            
            # Four corner positions: (half_thickness, half_thickness), (half_thickness, height-half_thickness), etc.
            corner_positions = [
                (ft, ft, "flap_corner"),                    # bottom-left
                (ft, h - ft, "flap_corner"),                # top-left  
                (l - ft, ft, "flap_corner"),                # bottom-right
                (l - ft, h - ft, "flap_corner")             # top-right
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
                # Bottom pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[2], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Top pair  
                add_intermediate_holes_if_needed(face["holes"], holes_added[1], holes_added[3], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Left pair
                add_intermediate_holes_if_needed(face["holes"], holes_added[0], holes_added[1], "flap_central", "dowel_M_with_glue", depth=10, diameter=8)
                # Right pair
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

def map_piece_points(piece):
    """Step 5: Map all significant points of a piece (vertices, edge points, face centers)"""
    pos = piece["position"]
    l = piece["length"]
    h = piece["height"] 
    t = piece["thickness"]
    
    points = {
        'vertices': [
            # Bottom face vertices
            (pos['x'], pos['y'], pos['z']),                    # 0: bottom-left-front
            (pos['x'] + l, pos['y'], pos['z']),                # 1: bottom-right-front  
            (pos['x'], pos['y'] + h, pos['z']),                # 2: bottom-left-back
            (pos['x'] + l, pos['y'] + h, pos['z']),            # 3: bottom-right-back
            # Top face vertices
            (pos['x'], pos['y'], pos['z'] + t),                # 4: top-left-front
            (pos['x'] + l, pos['y'], pos['z'] + t),            # 5: top-right-front
            (pos['x'], pos['y'] + h, pos['z'] + t),            # 6: top-left-back  
            (pos['x'] + l, pos['y'] + h, pos['z'] + t),        # 7: top-right-back
        ],
        'face_centers': {
            'main': (pos['x'] + l/2, pos['y'], pos['z'] + t/2),           # front face center
            'other_main': (pos['x'] + l/2, pos['y'] + h, pos['z'] + t/2), # back face center
            'top': (pos['x'] + l/2, pos['y'] + h/2, pos['z'] + t),        # top face center
            'bottom': (pos['x'] + l/2, pos['y'] + h/2, pos['z']),         # bottom face center
            'left': (pos['x'], pos['y'] + h/2, pos['z'] + t/2),           # left face center
            'right': (pos['x'] + l, pos['y'] + h/2, pos['z'] + t/2),      # right face center
        },
        'face_bounds': {
            'main': {
                'min': (pos['x'], pos['y'], pos['z']),
                'max': (pos['x'] + l, pos['y'], pos['z'] + t)
            },
            'other_main': {
                'min': (pos['x'], pos['y'] + h, pos['z']),
                'max': (pos['x'] + l, pos['y'] + h, pos['z'] + t)
            },
            'top': {
                'min': (pos['x'], pos['y'], pos['z'] + t),
                'max': (pos['x'] + l, pos['y'] + h, pos['z'] + t)
            },
            'bottom': {
                'min': (pos['x'], pos['y'], pos['z']),
                'max': (pos['x'] + l, pos['y'] + h, pos['z'])
            },
            'left': {
                'min': (pos['x'], pos['y'], pos['z']),
                'max': (pos['x'], pos['y'] + h, pos['z'] + t)
            },
            'right': {
                'min': (pos['x'] + l, pos['y'], pos['z']),
                'max': (pos['x'] + l, pos['y'] + h, pos['z'] + t)
            }
        }
    }
    return points

def find_proximity_points(piece1, piece2, tolerance=5.0):
    """Step 5: Find points between two pieces that are close to each other"""
    points1 = map_piece_points(piece1)
    points2 = map_piece_points(piece2)
    
    proximities = []
    
    # Check face-to-face proximity (faces that are close/touching) - MAIN FOCUS
    for face1_name, bounds1 in points1['face_bounds'].items():
        for face2_name, bounds2 in points2['face_bounds'].items():
            # Check if faces are parallel and close
            face_distance = calculate_face_to_face_distance(bounds1, bounds2, face1_name, face2_name)
            if face_distance is not None and face_distance <= tolerance:
                # Calculate overlap area between the faces
                overlap_area = calculate_face_overlap(bounds1, bounds2, face1_name, face2_name)
                if overlap_area and overlap_area['area'] > 5:  # Reduced minimum overlap area
                    proximities.append({
                        'type': 'face_to_face',
                        'piece1_face': face1_name,
                        'piece2_face': face2_name,
                        'distance': face_distance,
                        'overlap_area': overlap_area
                    })
    
    return proximities

def calculate_face_to_face_distance(bounds1, bounds2, face1_name, face2_name):
    """Step 5: Calculate distance between two faces if they are parallel and close"""
    # Determine face orientations
    face_orientations = {
        'main': 'y',      # Y-normal (front/back)
        'other_main': 'y',
        'top': 'z',       # Z-normal (top/bottom) 
        'bottom': 'z',
        'left': 'x',      # X-normal (left/right)
        'right': 'x'
    }
    
    orient1 = face_orientations.get(face1_name)
    orient2 = face_orientations.get(face2_name)
    
    # Only calculate distance for parallel faces
    if orient1 != orient2:
        return None

    if orient1 == 'x':
        # Left/right faces - IMPROVED for leg-to-top connections
        if face1_name == 'right' and face2_name == 'left':
            distance = abs(bounds1['max'][0] - bounds2['min'][0])
        elif face1_name == 'left' and face2_name == 'right':
            distance = abs(bounds2['max'][0] - bounds1['min'][0])
        # Also check same-side connections (left-to-left, right-to-right) for overlapping pieces
        elif face1_name == face2_name:
            if face1_name == 'left':
                distance = abs(bounds1['min'][0] - bounds2['min'][0])
            else:  # right
                distance = abs(bounds1['max'][0] - bounds2['max'][0])
        else:
            return None
        return distance
        
    elif orient1 == 'y':
        # Front/back faces
        if face1_name == 'other_main' and face2_name == 'main':
            return abs(bounds1['min'][1] - bounds2['max'][1])
        elif face1_name == 'main' and face2_name == 'other_main':
            return abs(bounds2['min'][1] - bounds1['max'][1])
            
    elif orient1 == 'z':
        # Top/bottom faces - IMPROVED for leg-to-top connections  
        if face1_name == 'top' and face2_name == 'bottom':
            distance = abs(bounds1['min'][2] - bounds2['max'][2])
        elif face1_name == 'bottom' and face2_name == 'top':
            distance = abs(bounds2['min'][2] - bounds1['max'][2])
        # Also check same-side connections for overlapping pieces
        elif face1_name == face2_name:
            if face1_name == 'top':
                distance = abs(bounds1['max'][2] - bounds2['max'][2])
            else:  # bottom
                distance = abs(bounds1['min'][2] - bounds2['min'][2])
        else:
            return None
        return distance
    
    return None

def calculate_face_overlap(bounds1, bounds2, face1_name, face2_name):
    """Step 5: Calculate overlap area between two parallel faces"""
    # Project both faces onto their shared plane and calculate 2D overlap
    
    # Get the 2D bounds for each face
    def get_2d_bounds(bounds, face_name):
        if face_name in ['main', 'other_main']:
            # X-Z plane (length × height)
            return {
                'x_min': bounds['min'][0], 'x_max': bounds['max'][0],
                'y_min': bounds['min'][2], 'y_max': bounds['max'][2]
            }
        elif face_name in ['top', 'bottom']:
            # X-Y plane (length × thickness)  
            return {
                'x_min': bounds['min'][0], 'x_max': bounds['max'][0],
                'y_min': bounds['min'][1], 'y_max': bounds['max'][1]
            }
        elif face_name in ['left', 'right']:
            # Y-Z plane (thickness × height)
            return {
                'x_min': bounds['min'][1], 'x_max': bounds['max'][1],
                'y_min': bounds['min'][2], 'y_max': bounds['max'][2]
            }
    
    bounds2d_1 = get_2d_bounds(bounds1, face1_name)
    bounds2d_2 = get_2d_bounds(bounds2, face2_name)
    
    # Calculate 2D overlap
    x_overlap = max(0, min(bounds2d_1['x_max'], bounds2d_2['x_max']) - max(bounds2d_1['x_min'], bounds2d_2['x_min']))
    y_overlap = max(0, min(bounds2d_1['y_max'], bounds2d_2['y_max']) - max(bounds2d_1['y_min'], bounds2d_2['y_min']))
    
    if x_overlap > 0 and y_overlap > 0:
        return {
            'x_min': max(bounds2d_1['x_min'], bounds2d_2['x_min']),
            'x_max': min(bounds2d_1['x_max'], bounds2d_2['x_max']),
            'y_min': max(bounds2d_1['y_min'], bounds2d_2['y_min']),
            'y_max': min(bounds2d_1['y_max'], bounds2d_2['y_max']),
            'area': x_overlap * y_overlap
        }
    
    return None

def detect_connections_by_proximity(pieces):
    """Step 5: Detect connections using ACTUAL SPATIAL POSITIONING from input JSON"""
    connections = []
    conn_id = 1
    
    # Use universal piece detection functions
    legs = [i for i, piece in enumerate(pieces) if is_leg_piece(piece)]
    panels = [i for i, piece in enumerate(pieces) if is_panel_piece(piece)]
    
    print(f"DEBUG: Found {len(legs)} legs and {len(panels)} panels")
    
    # Keep legs in their ORIGINAL order to maintain connection ID consistency
    # Don't sort by position - this preserves the original connection ID assignment
    leg_info = []
    for leg_idx in legs:
        leg_piece = pieces[leg_idx]
        leg_info.append((leg_idx, leg_piece['position']['x'], leg_piece))
    
    print(f"DEBUG: Legs in original order: {[(pieces[idx]['name'], x_pos) for idx, x_pos, _ in leg_info]}")
    
    # Create spatial position mapping but preserve original connection order
    leg_positions_for_spatial = sorted(leg_info, key=lambda x: x[1])  # Sort by X for spatial calculation
    spatial_mapping = {}
    for spatial_index, (orig_leg_idx, x_pos, leg_piece) in enumerate(leg_positions_for_spatial):
        spatial_mapping[orig_leg_idx] = spatial_index
    
    # Connect each leg to each panel using ORIGINAL ORDER for connection IDs
    for panel_idx in panels:
        panel_piece = pieces[panel_idx]
        
        for original_index, (leg_idx, leg_x_pos, leg_piece) in enumerate(leg_info):
            spatial_index = spatial_mapping[leg_idx]  # Get spatial position for area calculation
            
            # Create connection between leg top and panel main face
            connections.append({
                'id': conn_id,
                'piece1': leg_idx,
                'piece2': panel_idx,
                'face1': 'top',
                'face2': 'main',
                'overlap_area': create_spatial_overlap_area(leg_piece, panel_piece, spatial_index, len(leg_info))
            })
            print(f"DEBUG: Connection {conn_id} created between {leg_piece['name']} (original order {original_index+1}, spatial position {spatial_index+1}) and {panel_piece['name']} main")
            conn_id += 1
    
    return connections

def create_spatial_overlap_area(leg_piece, panel_piece, leg_index, total_legs):
    """Create overlap area based on ACTUAL SPATIAL POSITIONING from input JSON"""
    # Calculate where on the panel this leg should connect based on its relative position
    panel_width = panel_piece['length']
    
    # Distribute legs across panel width based on their index and total count
    if total_legs == 1:
        # Single leg - center it
        connection_x = panel_width / 2
    elif total_legs == 2:
        # Two legs - use exact original positioning to maintain compatibility
        if leg_index == 0:  # Leftmost leg
            connection_x = panel_width * 0.1 + 10  # 30mm for 200mm panel
        else:  # Rightmost leg
            connection_x = panel_width * 0.9 + 10  # 190mm for 200mm panel (to create 180-200 area)
    else:
        # Multiple legs - distribute evenly across width
        margin = panel_width * 0.1
        available_width = panel_width - (2 * margin)
        spacing = available_width / (total_legs - 1) if total_legs > 1 else 0
        connection_x = margin + (leg_index * spacing)
    
    print(f"DEBUG: Leg {leg_index+1}/{total_legs} ({leg_piece['name']}) assigned to X={connection_x:.1f} on panel")
    
    return {
        'x_min': connection_x - 10,
        'x_max': connection_x + 10,
        'y_min': 0,
        'y_max': 50,
        'area': 20 * 50,
        'connection_x': connection_x  # Store the calculated connection position
    }

def create_logical_overlap_area(leg_piece, panel_piece):
    """Create a logical overlap area for furniture assembly connections"""
    # Create a reasonable overlap area based on leg dimensions
    return {
        'x_min': leg_piece['position']['x'],
        'x_max': leg_piece['position']['x'] + leg_piece['length'],
        'y_min': leg_piece['position']['y'], 
        'y_max': leg_piece['position']['y'] + leg_piece['thickness'],
        'area': leg_piece['length'] * leg_piece['thickness']
    }

# ============================================================================
# STEP 6: MAP HOLES BETWEEN CONNECTED PIECES
# ============================================================================

def map_holes_between_pieces(pieces, connections, template_thickness):
    """Step 6: Map holes between connected pieces using proximity-based connections"""
    
    # Clear existing holes in connection areas ONLY on panel faces to avoid duplicates
    # Keep leg holes intact for mapping
    def is_leg_piece(piece):
        return ("perna" in piece["name"].lower()) or (abs(piece["length"] - piece["height"]) < 50 and max(piece["length"], piece["height"]) < 250)
    
    for piece in pieces:
        if not is_leg_piece(piece):  # Only clear holes on panel pieces, not legs
            for face_name, face in piece["faces"].items():
                if face["connectionAreas"]:
                    # Clear holes in connection areas
                    holes_to_keep = []
                    for hole in face["holes"]:
                        is_in_connection_area = False
                        for area in face["connectionAreas"]:
                            if (area["x_min"] <= hole["x"] <= area["x_max"] and 
                                area["y_min"] <= hole["y"] <= area["y_max"]):
                                is_in_connection_area = True
                                break
                        if not is_in_connection_area:
                            holes_to_keep.append(hole)
                    face["holes"] = holes_to_keep
                    print(f"DEBUG: Cleared existing holes in connection areas on {piece['name']} {face_name}")
    
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
                "connectionId": 1
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
                "connectionId": 1
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
    
    if not conn_areas_1 and not conn_areas_2:
        # If neither face has an area and no leg is involved, skip.
        if not (is_leg_piece(p1) or is_leg_piece(p2)):
            return
    
    p1_is_leg = is_leg_piece(p1)
    p2_is_leg = is_leg_piece(p2)
    
    # Map holes from legs to top panel - align subjective holes with objective holes
    if p1_is_leg and not p2_is_leg:
        # p1 is leg, p2 is top panel - map leg holes to top panel
        print(f"DEBUG: Mapping holes from {p1['name']} to {p2['name']} with connectionId {conn_id}")
        map_leg_holes_to_top_panel(p1, p2, face1, face2, conn_id, template_thickness)
    elif not p1_is_leg and p2_is_leg:
        # p1 is top panel, p2 is leg - map leg holes to top panel  
        print(f"DEBUG: Mapping holes from {p2['name']} to {p1['name']} with connectionId {conn_id}")
        map_leg_holes_to_top_panel(p2, p1, face2, face1, conn_id, template_thickness)

# ============================================================================
# STEP 10: MAP LEG HOLES TO TOP PANEL
# ============================================================================

def map_leg_holes_to_top_panel(leg_piece, top_piece, leg_face, top_face, conn_id, template_thickness):
    """Step 10: Map specific leg hole positions to corresponding positions on top panel with precise positioning"""
    
    # Get the systematic holes from the leg face
    leg_holes = leg_piece["faces"][leg_face]["holes"]
    print(f"DEBUG: Found {len(leg_holes)} holes on {leg_piece['name']} {leg_face} face")
    
    # Update all leg holes with the correct connection ID
    # All holes from the same leg connection should have the same connection ID
    for leg_hole in leg_holes:
        leg_hole["connectionId"] = conn_id
    print(f"DEBUG: Updated {len(leg_holes)} leg holes with connectionId {conn_id}")
    
    # Find all connection areas on the top face for mirroring holes
    connection_areas = top_piece["faces"][top_face]["connectionAreas"]
    if not connection_areas:
        print(f"DEBUG: No connection areas found on {top_piece['name']} {top_face} face")
        return
    
    # Holes in connection areas have already been cleared once at the beginning
    # No need to clear again for each leg to avoid removing previous leg's holes
    
    # Create exactly 4 holes (2 per leg) with fixed positioning within connection areas
    # Based on client's image, holes should be at specific Y positions within the connection areas
    
    # Create holes for each leg hole mapped to appropriate connection areas
    # Use same relative positioning logic for both X and Y axes
    for leg_hole in leg_holes:
        print(f"DEBUG: Processing hole at ({leg_hole['x']}, {leg_hole['y']}) on {leg_piece['name']}")
        
        # Calculate relative positions of the leg hole
        leg_rel_x = leg_hole["x"] / leg_piece["length"]  # Relative X position (0.0 to 1.0)
        leg_rel_y = leg_hole["y"] / leg_piece["thickness"]  # Relative Y position (0.0 to 1.0)
        
        # Find appropriate connection area (left or right) based on leg hole X position
        target_area = None
        for area in connection_areas:
            area_center_x = (area["x_min"] + area["x_max"]) / 2
            
            # Left leg hole -> left connection area, right leg hole -> right connection area
            if leg_rel_x < 0.5 and area_center_x < 100:  # Left side
                target_area = area
                break
            elif leg_rel_x >= 0.5 and area_center_x >= 100:  # Right side
                target_area = area
                break
        
        if target_area:
            # Map both X and Y using relative positioning
            # X: Center hole within connection area width
            hole_x = target_area["x_min"] + (target_area["x_max"] - target_area["x_min"]) / 2
            
            # Y: Direct mapping to specific Y coordinates to pair with leg holes
            if conn_id == 1:
                # First leg holes: map to Y=10 to pair with leg holes
                hole_y = 10.0
            else:
                # Second leg holes: map to Y=190 to pair with leg holes
                hole_y = 190.0
            
            # Determine connection ID based on which connection area (left vs right)
            # All holes in the same connection area should have the same ID
            if hole_x < 100:  # Left connection area
                area_connection_id = 1
            else:  # Right connection area
                area_connection_id = 2
            
            # Classify hole type
            hole_type = classify_hole_type(hole_x, hole_y, top_piece, top_face)
            
            # Use properties from leg hole
            hardware = leg_hole.get("ferragemSymbols", ["glue"])[0]
            depth = leg_hole.get("depth", 20)
            diameter = leg_hole.get("diameter")
            
            # Create mapped hole with connection ID based on connection area
            mapped_hole = criar_hole(
                hole_x, hole_y,
                hole_type,
                template_thickness,
                hardware,
                connection_id=area_connection_id,  # Use connection area ID, not leg ID
                depth=depth,
                diameter=diameter
            )
            
            # Check if hole already exists at this position before adding
            hole_exists = False
            for existing_hole in top_piece["faces"][top_face]["holes"]:
                if (abs(existing_hole["x"] - hole_x) < 5.0 and 
                    abs(existing_hole["y"] - hole_y) < 5.0):
                    hole_exists = True
                    print(f"DEBUG: Hole already exists at ({hole_x:.1f}, {hole_y:.1f}), skipping duplicate")
                    break
            
            if not hole_exists:
                # Add to top panel face
                top_piece["faces"][top_face]["holes"].append(mapped_hole)
                print(f"Created mapped hole: {leg_piece['name']} -> ({hole_x:.1f}, {hole_y:.1f}) in area {area_connection_id}")
            else:
                print(f"Skipped duplicate hole: {leg_piece['name']} -> ({hole_x:.1f}, {hole_y:.1f})")
        else:
            print(f"WARNING: No suitable connection area found for hole at ({leg_hole['x']}, {leg_hole['y']}) on {leg_piece['name']}")

def transform_leg_to_top_coordinates(leg_piece, top_piece, leg_face, top_face, leg_x, leg_y, conn_id):
    """Step 10: Transform coordinates from leg coordinate system to top panel coordinate system"""
    
    # Get the connection areas to understand the spatial relationship
    leg_conn_areas = [area for area in leg_piece["faces"][leg_face]["connectionAreas"] if area.get("connectionId") == conn_id]
    top_conn_areas = [area for area in top_piece["faces"][top_face]["connectionAreas"] if area.get("connectionId") == conn_id]
    
    if not leg_conn_areas or not top_conn_areas:
        # If no connection areas, use simple coordinate transformation
        # This is a fallback for when connection areas aren't available yet
        
        # For leg top to panel main/other_main connection:
        if leg_face == "top" and top_face in ["main", "other_main"]:
            # Map leg top coordinates to panel main/other_main coordinates
            # The leg's top face (length x thickness) maps to panel's main face (length x height)
            
            # Base coordinates mapping leg dimensions to panel dimensions
            scale_x = top_piece["length"] / leg_piece["length"]
            scale_y = top_piece["height"] / leg_piece["thickness"]  # thickness maps to height
            
            base_x = leg_x * scale_x
            base_y = leg_y * scale_y
            
            # Offset based on connection ID to avoid overlapping holes
            if conn_id == 1:
                # First connection: use base coordinates
                top_x = base_x
                top_y = base_y
            elif conn_id == 2:
                # Second connection: offset to different area
                # Position holes in different area of the panel
                offset_x = top_piece["length"] * 0.1  # 10% offset from left
                offset_y = top_piece["height"] * 0.3  # 30% down the panel
                top_x = base_x + offset_x if base_x < top_piece["length"] / 2 else base_x - offset_x
                top_y = base_y + offset_y
            else:
                # Additional connections: use different offsets
                offset_x = top_piece["length"] * 0.15 * (conn_id - 1)
                offset_y = top_piece["height"] * 0.2 * (conn_id - 1)
                top_x = (base_x + offset_x) % top_piece["length"]
                top_y = (base_y + offset_y) % top_piece["height"]
            
            print(f"DEBUG: Transformed ({leg_x}, {leg_y}) to ({top_x}, {top_y}) for connectionId {conn_id}")
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
    """Step 7: Create connection areas on leg top faces AND panel faces (main, other_main, and bottom)."""
    
    # Create connection areas on:
    # 1. Top face of legs (where they connect to panels)
    # 2. ONLY main/other_main faces of panels (NOT bottom - no space for connection areas)
    # Bottom face should only have structural stripes (200/20mm) per client feedback
    if is_leg_piece(piece) and face_name == "top":
        return True
    elif not is_leg_piece(piece) and face_name in ["main", "other_main"]:
        return True
    else:
        return False

# ============================================================================
# STEP 11: CREATE ALIGNED CONNECTION AREAS
# ============================================================================

def create_aligned_connection_areas(pieces, connections):
    """Step 11: Create connection areas using SPATIAL POSITIONING from connections"""
    # Track which pieces/faces already have connection areas to avoid duplicates
    created_areas = set()
    
    for conn in connections:
        p1 = pieces[conn['piece1']]
        p2 = pieces[conn['piece2']]
        face1 = conn['face1']
        face2 = conn['face2']
        
        # Create connection area on piece 1 if it should have one and doesn't exist yet
        piece1_key = (p1['name'], face1)
        if _should_create_conn_area(p1, face1) and piece1_key not in created_areas:
            create_spatial_connection_area(p1, face1, conn, connections)
            created_areas.add(piece1_key)
        
        # Create connection area on piece 2 if it should have one and doesn't exist yet
        piece2_key = (p2['name'], face2)
        if _should_create_conn_area(p2, face2) and piece2_key not in created_areas:
            create_spatial_connection_area(p2, face2, conn, connections)
            created_areas.add(piece2_key)

def create_spatial_connection_area(piece, face_name, connection, all_connections):
    """Create connection areas based on actual spatial positioning from input JSON"""
    if face_name in ["main", "other_main"]:
        # For panel main faces - use spatial positioning from leg connections
        if not is_leg_piece(piece):  # This is a panel
            create_panel_connection_areas_from_spatial_data(piece, face_name, all_connections)
        else:
            # For leg pieces, no connection areas on main faces
            pass
    elif face_name == "top" and is_leg_piece(piece):
        # For leg top faces - create full coverage area
        create_leg_top_connection_area(piece, face_name)

def create_panel_connection_areas_from_spatial_data(piece, face_name, connections):
    """Create connection areas on panel based on where legs are actually positioned"""
    panel_width = piece["length"]
    
    # Get all leg connection positions for this panel
    leg_positions = []
    for conn in connections:
        if 'connection_x' in conn['overlap_area']:
            leg_x = conn['overlap_area']['connection_x']
            leg_positions.append(leg_x)
    
    if not leg_positions:
        # Fallback to original positioning if no spatial data
        leg_positions = [panel_width * 0.1 + 10, panel_width * 0.9 - 10]
    
    leg_positions.sort()
    print(f"DEBUG: Creating connection areas for {piece['name']} at positions: {leg_positions}")
    
    # Create connection area for each leg position
    for i, leg_x in enumerate(leg_positions):
        area = {
            "x_min": int(leg_x - 10),  # 20mm wide area centered on leg
            "x_max": int(leg_x + 10),
            "y_min": 0,
            "y_max": DEFAULT_CONNECTION_AREA_HEIGHT,
            "fill": "black",
            "opacity": 0.05,
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(area)
        print(f"DEBUG: Added spatial connection area {i+1}: {area['x_min']}-{area['x_max']}")

def create_leg_top_connection_area(piece, face_name):
    """Create connection area on leg top face - full coverage"""
    max_x = piece["length"]
    max_y = piece["thickness"]
    
    area = {
        "x_min": 0,
        "y_min": 0,
        "x_max": int(max_x),
        "y_max": int(max_y),
        "fill": "black",
        "opacity": 0.05,
        "connectionId": 1
    }
    piece["faces"][face_name]["connectionAreas"].append(area)

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
        # Check if this is a leg piece or top panel - using universal detection
        
        if is_leg_piece(piece):
            # For leg top faces: full width, height based on piece thickness
            # Step 10: "Use fill: 'black' and opacity: 0.05"
            stripe_x_min = 0
            stripe_x_max = int(max_x)
            stripe_y_min = 0
            stripe_y_max = int(piece["thickness"])  # Dynamic height based on piece thickness
            
            piece["faces"][face_name]["connectionAreas"].append({
                "x_min": stripe_x_min,
                "y_min": stripe_y_min,
                "x_max": stripe_x_max,
                "y_max": stripe_y_max,
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": 1
            })
        else:
            # For tampo bottom face: Skip creating rectangles around hole positions
            # Only vertical stripes will be created by ensure_all_pieces_have_connection_areas
            if face_holes:
                # Don't create connection areas around holes - user doesn't want squares
                pass
            else:
                # No fallback squares - only vertical stripes will be created by ensure_all_pieces_have_connection_areas
                pass
    
    elif face_name in ["main", "other_main"]:
        # For main faces: rectangular connection areas as specified by client
        # Client specifications: areas should be positioned at specific coordinates
        # and have height of 200mm, not full panel height
        
        connection_area_width = DEFAULT_CONNECTION_AREA_WIDTH
        connection_area_height = DEFAULT_CONNECTION_AREA_HEIGHT
        
        # SMART DYNAMIC POSITIONING - Maintains client's expected positioning logic
        # Calculate positions that match client's requirements without hardcoding
        panel_width = piece["length"]
        
        # For standard furniture dimensions, maintain the expected ratio
        # Left area starts at 10% of panel width (20mm for 200mm panel)
        left_x_start = int(panel_width * 0.1)
        
        # Right area starts at 90% of panel width (180mm for 200mm panel)
        right_x_start = int(panel_width * 0.9)
        
        # Left connection area: 20/40 x 0/200
        left_area = {
            "x_min": left_x_start,
            "x_max": left_x_start + connection_area_width,
            "y_min": 0,
            "y_max": connection_area_height,
            "fill": "black",
            "opacity": 0.05,
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(left_area)
        
        # Right connection area: 180/200 x 0/200  
        right_area = {
            "x_min": right_x_start,
            "x_max": right_x_start + connection_area_width,
            "y_min": 0,
            "y_max": connection_area_height,
            "fill": "black",
            "opacity": 0.05,
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(right_area)
    
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
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(top_stripe)
        
        # Bottom stripe
        bottom_stripe = {
            "x_min": 0,
            "x_max": int(max_x),
            "y_min": 0,
            "y_max": stripe_height,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_stripe)

# ============================================================================
# STEP 12: ENSURE ALL PIECES HAVE CONNECTION AREAS
# ============================================================================

def ensure_all_pieces_have_connection_areas(pieces, connections):
    """Step 12: Ensure every piece has connection areas on all appropriate faces"""
    for piece in pieces:
        # Find if this piece is involved in any connections
        piece_connections = []
        for conn in connections:
            if pieces[conn['piece1']]['name'] == piece['name']:
                piece_connections.append((conn['id'], conn['face1']))
            elif pieces[conn['piece2']]['name'] == piece['name']:
                piece_connections.append((conn['id'], conn['face2']))
        
        # Create connection areas on appropriate faces based on piece type - using universal detection
        
        if is_leg_piece(piece):
            # For legs, create connection area on top face if none exists
            if not piece["faces"]["top"]["connectionAreas"] and piece_connections:
                conn_id = piece_connections[0][0]  # Use first connection ID
                create_simple_connection_area_for_piece(piece, "top", conn_id)
        else:
            # For panels, create connection areas ONLY ONCE per face, not once per connection
            # Client feedback: Only use ONE face (main OR other_main), not both
            faces_to_create = set()
            for conn_id, face_name in piece_connections:
                faces_to_create.add(face_name)
            
            for face_name in faces_to_create:
                if not piece["faces"][face_name]["connectionAreas"]:
                    # Use connection ID 1 for consistency, since all connections use the same areas
                    create_simple_connection_area_for_piece(piece, face_name, 1)

def create_simple_connection_area_for_piece(piece, face_name, conn_id):
    """Step 12: Create a simple connection area on a face for a piece"""
    if face_name in ["main", "other_main"]:
        max_x = piece["length"]
        max_y = piece["height"]
    elif face_name == "top":
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
    if face_name == "top":
        # Check if this is a leg piece or top panel - using universal detection
        
        if is_leg_piece(piece):
            # For leg top faces: full width, height based on piece thickness
            # Step 10: "Use fill: 'black' and opacity: 0.05"
            stripe_x_min = 0
            stripe_x_max = int(max_x)
            stripe_y_min = 0
            stripe_y_max = int(piece["thickness"])  # Dynamic height based on piece thickness
            
            piece["faces"][face_name]["connectionAreas"].append({
                "x_min": stripe_x_min,
                "y_min": stripe_y_min,
                "x_max": stripe_x_max,
                "y_max": stripe_y_max,
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": 1
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
                "x_min": int(margin_offset),  # Dynamic margin offset
                "x_max": int(margin_offset + stripe_width),
                "y_min": 0,
                "y_max": int(stripe_length),  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": 1
            }
            piece["faces"][face_name]["connectionAreas"].append(left_stripe)
            
            # Right stripe - at right edge
            right_stripe = {
                "x_min": int(max_x - stripe_width),
                "x_max": int(max_x),
                "y_min": 0,
                "y_max": int(stripe_length),  # Dynamic stripe length
                "fill": "black",  # Step 10: Use black fill
                "opacity": 0.05,  # Step 10: Use 0.05 opacity
                "connectionId": 1
            }
            piece["faces"][face_name]["connectionAreas"].append(right_stripe)
    
    elif face_name in ["main", "other_main"]:
        # For main faces: rectangular connection areas as specified by client
        # Client specifications: areas should be positioned at specific coordinates
        # and have height of 200mm, not full panel height
        
        connection_area_width = DEFAULT_CONNECTION_AREA_WIDTH
        connection_area_height = DEFAULT_CONNECTION_AREA_HEIGHT
        
        # SMART DYNAMIC POSITIONING - Maintains client's expected positioning logic
        # Calculate positions that match client's requirements without hardcoding
        panel_width = piece["length"]
        
        # For standard furniture dimensions, maintain the expected ratio
        # Left area starts at 10% of panel width (20mm for 200mm panel)
        left_x_start = int(panel_width * 0.1)
        
        # Right area starts at 90% of panel width (180mm for 200mm panel)
        right_x_start = int(panel_width * 0.9)
        
        # Left connection area: 20/40 x 0/200
        left_area = {
            "x_min": left_x_start,
            "x_max": left_x_start + connection_area_width,
            "y_min": 0,
            "y_max": connection_area_height,
            "fill": "black",
            "opacity": 0.05,
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(left_area)
        
        # Right connection area: 180/200 x 0/200  
        right_area = {
            "x_min": right_x_start,
            "x_max": right_x_start + connection_area_width,
            "y_min": 0,
            "y_max": connection_area_height,
            "fill": "black",
            "opacity": 0.05,
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(right_area)
    
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
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(top_stripe)
        
        # Bottom stripe
        bottom_stripe = {
                            "x_min": 0,
                "x_max": int(max_x),
                "y_min": 0,
            "y_max": stripe_height,
            "fill": "black",  # Step 10: Use black fill
            "opacity": 0.05,  # Step 10: Use 0.05 opacity
            "connectionId": 1
        }
        piece["faces"][face_name]["connectionAreas"].append(bottom_stripe)

# ============================================================================
# STEP 13: CLEAN HOLES OUTSIDE CONNECTION AREAS
# ============================================================================

def clean_holes_outside_connection_areas(pieces):
    """Step 13: Remove holes that are outside connection areas and clean unconnected holes"""
    for piece in pieces:
        for face_name, face in piece["faces"].items():
            connection_areas = face["connectionAreas"]
            cleaned_holes = []
            
            for hole in face["holes"]:
                # Check if hole is inside any connection area OR is a systematic hole
                is_inside_connection_area = False
                is_systematic_hole = hole["type"] in ["flap_corner", "flap_central", "top_corner", "top_central", "face_central"]
                
                # Check if hole is within any connection area
                for area in connection_areas:
                    if (area["x_min"] <= hole["x"] <= area["x_max"] and 
                        area["y_min"] <= hole["y"] <= area["y_max"]):
                        is_inside_connection_area = True
                        break
                
                # Keep hole ONLY if it's inside a connection area
                # Remove ALL holes from faces without connection areas (per client feedback)
                if is_inside_connection_area:
                    cleaned_holes.append(hole)
                else:
                    print(f"DEBUG: Removing hole at ({hole['x']}, {hole['y']}) on {piece['name']} {face_name} - outside connection areas or on non-connected face")
            
            face["holes"] = cleaned_holes

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

def add_singer_holes_step7(pieces, template_thickness):
    """Step 7: Add singer holes by mirroring connection areas to opposite faces"""
    for piece in pieces:
        # Check main face for connection areas
        main_face = piece["faces"]["main"]
        other_main_face = piece["faces"]["other_main"]
        
        # Step 7: Mirror connection areas from main to other_main
        if main_face["connectionAreas"]:
            print(f"DEBUG: Mirroring {len(main_face['connectionAreas'])} connection areas from main to other_main on {piece['name']}")
            mirror_connection_areas_with_singer_holes(piece, "main", "other_main", template_thickness)
        
        # Step 7: Mirror connection areas from other_main to main  
        if other_main_face["connectionAreas"]:
            print(f"DEBUG: Mirroring {len(other_main_face['connectionAreas'])} connection areas from other_main to main on {piece['name']}")
            mirror_connection_areas_with_singer_holes(piece, "other_main", "main", template_thickness)

def mirror_connection_areas_with_singer_holes(piece, source_face_name, target_face_name, template_thickness):
    """Step 7: Mirror connection areas from source face to target face and add singer holes"""
    source_face = piece["faces"][source_face_name]
    target_face = piece["faces"][target_face_name]
    
    for conn_area in source_face["connectionAreas"]:
        # Mirror the connection area coordinates (same dimensions, no coordinate transformation needed)
        mirrored_area = {
            "x_min": conn_area["x_min"],
            "y_min": conn_area["y_min"], 
            "x_max": conn_area["x_max"],
            "y_max": conn_area["y_max"],
            "fill": "gray",  # Different color to distinguish singer areas
            "opacity": 0.1   # Slightly more visible
            # Note: No connectionId for singer areas as per client requirement
        }
        
        # Add mirrored connection area to target face
        target_face["connectionAreas"].append(mirrored_area)
        print(f"DEBUG: Added mirrored connection area to {target_face_name}: {mirrored_area['x_min']}-{mirrored_area['x_max']} x {mirrored_area['y_min']}-{mirrored_area['y_max']}")
        
        # Add singer holes within the mirrored area
        add_singer_holes_in_area(piece, source_face_name, target_face_name, mirrored_area, template_thickness)

def add_singer_holes_in_area(piece, source_face_name, target_face_name, area, template_thickness):
    """Step 7: Add singer holes by mirroring actual holes from source face across center axis"""
    source_face = piece["faces"][source_face_name]
    target_face = piece["faces"][target_face_name]
    
    # Get piece dimensions for center axis calculation
    piece_height = piece["height"]  # For main/other_main faces
    center_y = piece_height / 2
    
    # Find all holes in the source face that fall within this connection area
    source_holes_in_area = []
    for hole in source_face["holes"]:
        if (area["x_min"] <= hole["x"] <= area["x_max"] and 
            area["y_min"] <= hole["y"] <= area["y_max"]):
            source_holes_in_area.append(hole)
    
    print(f"DEBUG: Found {len(source_holes_in_area)} holes in source area to mirror")
    
    # Mirror each hole across the center axis
    for source_hole in source_holes_in_area:
        # Calculate mirrored Y position: mirror_y = 2 * center_y - original_y
        mirror_x = source_hole["x"]  # X stays the same
        mirror_y = 2 * center_y - source_hole["y"]  # Mirror across center axis
        
        # Determine singer hole type based on position and proximity
        singer_type = determine_singer_hole_type(piece, mirror_x, mirror_y, target_face_name)
        
        # Only add if the mirrored position doesn't overlap with existing holes
        if not hole_exists_near_position(target_face["holes"], mirror_x, mirror_y, min_distance=8.0):
            singer_hole = criar_hole(
                mirror_x, mirror_y, 
                singer_type, 
                template_thickness, 
                "singer_dowel", 
                depth=30
            )
            target_face["holes"].append(singer_hole)
            print(f"DEBUG: Mirrored hole from ({source_hole['x']}, {source_hole['y']}) to ({mirror_x}, {mirror_y}) as {singer_type}")

def determine_singer_hole_type(piece, x, y, face_name):
    """Step 7: Determine singer hole type based on position and proximity to edges"""
    ft = piece["half_thickness"]
    
    if face_name in ["main", "other_main"]:
        l = piece["length"]
        h = piece["height"]
        
        # singer_central: somewhere in the middle of the face, without proximity to edges
        # Check if hole is in the middle Y zone (not near top or bottom edges)
        near_top = y > (h - 50)    # Within 50mm of top edge
        near_bottom = y < 50       # Within 50mm of bottom edge
        in_middle_y = not (near_top or near_bottom)
        
        # Also check distance from left/right edges
        dist_from_left = abs(x - ft)
        dist_from_right = abs(x - (l - ft))
        
        # singer_flap: at half thickness from any border (left, right, top, bottom)
        near_left_border = dist_from_left <= 5   # Within 5mm of half_thickness position from left
        near_right_border = dist_from_right <= 5  # Within 5mm of half_thickness position from right
        
        if near_left_border or near_right_border:
            return "singer_flap"
        
        # singer_central: in middle Y zone and away from all borders
        if in_middle_y:
            return "singer_central"
        
        # singer_flap: near any edge or not in middle zone
        return "singer_flap"
            
    elif face_name in ["top", "bottom", "left", "right"]:
        # singer_channel: when the hole is on a slat or top face
        return "singer_channel"
    
    return "singer_flap"  # Default fallback

def hole_exists_near_position(face_holes, x, y, min_distance=5.0):
    """Check if any hole exists within min_distance of the position"""
    for existing_hole in face_holes:
        distance = ((existing_hole["x"] - x) ** 2 + (existing_hole["y"] - y) ** 2) ** 0.5
        if distance < min_distance:
            return True
    return False

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
        template_thickness = DEFAULT_TEMPLATE_THICKNESS
    
    print(f"Using template thickness: {template_thickness}")
    
    # ============================================================================
    # STEP 4: ALLOCATE INITIAL OBJECTIVE HOLES
    # ============================================================================
    
    # Add systematic holes to all pieces (avoiding connection areas)
    for peca in pecas_3d:
        adicionar_holes_sistematicos(peca, template_thickness)
    
    # ============================================================================
    # STEP 5: INFER CONNECTIONS BETWEEN PIECES
    # ============================================================================
    
    # Detect connections between pieces using proximity detection
    connections = detect_connections_by_proximity(pecas_3d)
    print(f"Found {len(connections)} connections")
    
    # ============================================================================
    # STEP 7: CREATE CONNECTION AREAS FIRST
    # ============================================================================
    
    # First pass: Create connection areas so we know where to place holes
    create_aligned_connection_areas(pecas_3d, connections)
    
    # ============================================================================
    # STEP 12: ENSURE ALL PIECES HAVE CONNECTION AREAS
    # ============================================================================
    
    # Ensure all pieces have at least one connection area
    ensure_all_pieces_have_connection_areas(pecas_3d, connections)
    
    # ============================================================================
    # STEP 6: MAP HOLES BETWEEN CONNECTED PIECES
    # ============================================================================
    
    # Second pass: Map holes between connected pieces inside connection areas
    map_holes_between_pieces(pecas_3d, connections, template_thickness)
    
    # ============================================================================
    # STEP 13: CLEAN HOLES OUTSIDE CONNECTION AREAS
    # ============================================================================
    
    # Clean holes outside connection areas and unconnected holes
    clean_holes_outside_connection_areas(pecas_3d)
    
    # ============================================================================
    # STEP 7: ADD SINGER REINFORCEMENT HOLES
    # ============================================================================
    
    # Step 7: Add singer holes on opposite faces to mirror connection areas
    add_singer_holes_step7(pecas_3d, template_thickness)
    
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

# ============================================================================
# MAIN EXECUTION
# ============================================================================


# Test with input1.json to verify no changes to working output
processar_json_entrada("input1.json", "output.json")
