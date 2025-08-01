import json
import math
from collections import defaultdict

def arredondar(valor):
    arredondado = round(valor, 1)
    if abs(arredondado - round(arredondado)) < 0.1:
        return float(round(arredondado))
    return arredondado

def mm(valor):
    return arredondar(valor * 10)

def format_number(val):
    return int(val) if val == int(val) else round(val, 1)

def determine_dimensions(dims):
    dim_sorted = sorted(dims, reverse=True)
    return {
        "height": dim_sorted[0],
        "length": dim_sorted[1],
        "thickness": dim_sorted[2],
        "half_thickness": arredondar(dim_sorted[2] / 2)
    }

def extrair_views_por_peca(data):
    pecas = {}
    for layer in data["layers"]:
        vista = layer["name"]
        for item in layer["items"]:
            nome = item["nome"].strip().lower()
            if nome not in pecas:
                pecas[nome] = {}
            pecas[nome][vista] = item
    return pecas

def construir_peca_3d(nome, views):
    sup = views.get("vista superior")
    lat = views.get("vista lateral")
    fra = views.get("vista frontal")
    if not sup or not lat or not fra:
        return None

    x = mm(sup["posicao"]["x"])
    y = mm(sup["posicao"]["y"])
    z = mm(fra["posicao"]["y"])

    length = mm(sup["dimensoes"]["largura"])
    height = mm(fra["dimensoes"]["altura"])
    thickness = mm(lat["dimensoes"]["largura"])

    dims = determine_dimensions([length, height, thickness])

    return {
        "name": nome,
        "position": {"x": x, "y": y, "z": z},
        "length": dims["length"],
        "height": dims["height"],
        "thickness": dims["thickness"],
        "half_thickness": dims["half_thickness"],
        "faces": {
            "main": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["height"]}},
            "other_main": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["height"]}},
            "top": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["thickness"]}},
            "bottom": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["length"], "height": dims["thickness"]}},
            "left": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["thickness"], "height": dims["height"]}},
            "right": {"holes": [], "connectionAreas": [], "dimensions": {"width": dims["thickness"], "height": dims["height"]}}
        }
    }

def criar_hole(x, y, tipo, target_type, ferragem, connection_id=None, depth=None, diameter=None):
    hole = {
        "x": arredondar(x),
        "y": arredondar(y),
        "type": tipo,
        "targetType": str(int(float(target_type))),  # Ensure no decimals - convert to int first
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
    """Select closest standard template thickness"""
    templates = [17, 20, 25, 30]
    return min(templates, key=lambda x: abs(x - thickness))

def adicionar_holes_sistematicos(peca, template_thickness):
    """Add systematic holes on all faces according to PDF requirements"""
    h = peca["height"]
    l = peca["length"]
    t = peca["thickness"]
    ft = peca["half_thickness"]

    def add_hole_if_not_exists(face_holes, x, y, hole_type, hardware, depth=None, diameter=None):
        """Add hole only if no hole exists at this position"""
        for existing_hole in face_holes:
            if abs(existing_hole["x"] - x) < 2.0 and abs(existing_hole["y"] - y) < 2.0:
                return  # Hole already exists at this position
        
        # Add the hole
        hole = criar_hole(x, y, hole_type, template_thickness, hardware, depth=depth, diameter=diameter)
        face_holes.append(hole)
    
    # Main and other_main faces: flap holes (length x height)
    for face_name in ["main", "other_main"]:
        face = peca["faces"][face_name]
        
        # Corner holes at proper positions with correct classification
        corner_positions = [
            (ft, ft, "flap_corner"),           # bottom-left
            (l - ft, ft, "flap_corner"),       # bottom-right  
            (ft, h - ft, "flap_corner"),       # top-left
            (l - ft, h - ft, "flap_corner")    # top-right
        ]
        
        for x, y, hole_type in corner_positions:
            add_hole_if_not_exists(face["holes"], x, y, hole_type, "dowel_M_with_glue", depth=10, diameter=8)
        
        # Edge holes if distance > 200mm
        if l > 200:
            mid_x = l / 2
            edge_positions = [
                (mid_x, ft, "flap_central"),      # bottom-center
                (mid_x, h - ft, "flap_central")   # top-center
            ]
            for x, y, hole_type in edge_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "dowel_M_with_glue", depth=10, diameter=8)
        
        if h > 200:
            mid_y = h / 2
            edge_positions = [
                (ft, mid_y, "flap_central"),          # left-center
                (l - ft, mid_y, "flap_central")       # right-center
            ]
            for x, y, hole_type in edge_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "dowel_M_with_glue", depth=10, diameter=8)
    
    # Top and bottom faces: top holes (length x thickness)
    for face_name in ["top", "bottom"]:
        face = peca["faces"][face_name]
        
        # Corner holes with correct classification
        corner_positions = [
            (ft, ft, "top_corner"),            # corner 1
            (l - ft, ft, "top_corner"),        # corner 2
            (ft, t - ft, "top_corner"),        # corner 3
            (l - ft, t - ft, "top_corner")     # corner 4
        ]
        
        for x, y, hole_type in corner_positions:
            add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
        
        # Central holes if needed
        if l > 200:
            mid_x = l / 2
            central_positions = [
                (mid_x, ft, "top_central"),        # center-bottom
                (mid_x, t - ft, "top_central")     # center-top
            ]
            for x, y, hole_type in central_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
    
    # Left and right faces: top holes (thickness x height)
    for face_name in ["left", "right"]:
        face = peca["faces"][face_name]
        
        # Corner holes with correct classification
        corner_positions = [
            (ft, ft, "top_corner"),            # corner 1
            (t - ft, ft, "top_corner"),        # corner 2
            (ft, h - ft, "top_corner"),        # corner 3  
            (t - ft, h - ft, "top_corner")     # corner 4
        ]
        
        for x, y, hole_type in corner_positions:
            add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)
        
        # Central holes if needed
        if h > 200:
            mid_y = h / 2
            central_positions = [
                (ft, mid_y, "top_central"),           # center-left
                (t - ft, mid_y, "top_central")        # center-right
            ]
            for x, y, hole_type in central_positions:
                add_hole_if_not_exists(face["holes"], x, y, hole_type, "glue", depth=20)

def map_piece_points(piece):
    """Map all significant points of a piece (vertices, edge points, face centers)"""
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
    """Find points between two pieces that are close to each other"""
    points1 = map_piece_points(piece1)
    points2 = map_piece_points(piece2)
    
    proximities = []
    
    # Check proximity between all vertices
    for i, p1 in enumerate(points1['vertices']):
        for j, p2 in enumerate(points2['vertices']):
            distance = ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)**0.5
            if distance <= tolerance:
                proximities.append({
                    'type': 'vertex_to_vertex',
                    'piece1_point': p1,
                    'piece2_point': p2,
                    'distance': distance,
                    'piece1_vertex': i,
                    'piece2_vertex': j
                })
    
    # Check proximity between vertices and face centers
    for face_name, center2 in points2['face_centers'].items():
        for i, p1 in enumerate(points1['vertices']):
            distance = ((p1[0] - center2[0])**2 + (p1[1] - center2[1])**2 + (p1[2] - center2[2])**2)**0.5
            if distance <= tolerance:
                proximities.append({
                    'type': 'vertex_to_face',
                    'piece1_point': p1,
                    'piece2_point': center2,
                    'piece2_face': face_name,
                    'distance': distance,
                    'piece1_vertex': i
                })
    
    # Check proximity between face centers and vertices
    for face_name, center1 in points1['face_centers'].items():
        for j, p2 in enumerate(points2['vertices']):
            distance = ((center1[0] - p2[0])**2 + (center1[1] - p2[1])**2 + (center1[2] - p2[2])**2)**0.5
            if distance <= tolerance:
                proximities.append({
                    'type': 'face_to_vertex',
                    'piece1_point': center1,
                    'piece2_point': p2,
                    'piece1_face': face_name,
                    'distance': distance,
                    'piece2_vertex': j
                })
    
    # Check face-to-face proximity (faces that are close/touching)
    for face1_name, bounds1 in points1['face_bounds'].items():
        for face2_name, bounds2 in points2['face_bounds'].items():
            # Check if faces are parallel and close
            face_distance = calculate_face_to_face_distance(bounds1, bounds2, face1_name, face2_name)
            if face_distance is not None and face_distance <= tolerance:
                # Calculate overlap area between the faces
                overlap_area = calculate_face_overlap(bounds1, bounds2, face1_name, face2_name)
                if overlap_area and overlap_area['area'] > 10:  # Minimum 10 sq mm overlap
                    proximities.append({
                        'type': 'face_to_face',
                        'piece1_face': face1_name,
                        'piece2_face': face2_name,
                        'distance': face_distance,
                        'overlap_area': overlap_area
                    })
    
    return proximities

def calculate_face_to_face_distance(bounds1, bounds2, face1_name, face2_name):
    """Calculate distance between two faces if they are parallel and close"""
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
        # Left/right faces
        if face1_name == 'right' and face2_name == 'left':
            return abs(bounds1['max'][0] - bounds2['min'][0])
        elif face1_name == 'left' and face2_name == 'right':
            return abs(bounds2['max'][0] - bounds1['min'][0])
    elif orient1 == 'y':
        # Front/back faces
        if face1_name == 'other_main' and face2_name == 'main':
            return abs(bounds1['min'][1] - bounds2['max'][1])
        elif face1_name == 'main' and face2_name == 'other_main':
            return abs(bounds2['min'][1] - bounds1['max'][1])
    elif orient1 == 'z':
        # Top/bottom faces
        if face1_name == 'top' and face2_name == 'bottom':
            return abs(bounds1['min'][2] - bounds2['max'][2])
        elif face1_name == 'bottom' and face2_name == 'top':
            return abs(bounds2['min'][2] - bounds1['max'][2])
    
    return None

def calculate_face_overlap(bounds1, bounds2, face1_name, face2_name):
    """Calculate overlap area between two parallel faces"""
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
    """Detect connections using point-based proximity as suggested by client"""
    connections = []
    conn_id = 1
    seen_connections = set()  # Track face pairs to prevent duplicates
    
    for i, piece1 in enumerate(pieces):
        for j, piece2 in enumerate(pieces):
            if i >= j:
                continue
            
            proximities = find_proximity_points(piece1, piece2, tolerance=5.0)
            
            if proximities:
                # Group proximities by type and create connections
                face_to_face_proximities = [p for p in proximities if p['type'] == 'face_to_face']
                
                for proximity in face_to_face_proximities:
                    face1 = proximity['piece1_face']
                    face2 = proximity['piece2_face']
                    
                    # Create unique identifier for this face pair to prevent duplicates
                    connection_key = tuple(sorted([
                        (i, face1),
                        (j, face2)
                    ]))
                    
                    # Only create connection if we haven't seen this face pair before
                    if connection_key not in seen_connections:
                        seen_connections.add(connection_key)
                        
                        connections.append({
                            'id': conn_id,
                            'piece1': i,
                            'piece2': j,
                            'proximity': proximity,
                            'face1': face1,
                            'face2': face2,
                            'overlap_area': proximity['overlap_area']
                        })
                        conn_id += 1
    
    return connections

def map_holes_between_pieces(pieces, connections, template_thickness):
    """Map holes between connected pieces using proximity-based connections"""
    
    for conn in connections:
        p1 = pieces[conn['piece1']]
        p2 = pieces[conn['piece2']]
        
        # Get the connecting faces from proximity detection
        face1 = conn['face1']
        face2 = conn['face2']
        overlap_area = conn['overlap_area']
        
        # Create connection areas on both pieces based on proximity overlap
        create_connection_areas_from_proximity(p1, p2, face1, face2, conn['id'], overlap_area)
        
        # Map holes between the connecting faces
        map_face_holes_proximity(p1, p2, face1, face2, conn['id'], template_thickness)

def create_connection_areas_from_proximity(p1, p2, face1, face2, conn_id, overlap_area):
    """Create connection areas based on proximity overlap area"""
    
    # Convert overlap area to face coordinates for piece 1
    area1 = convert_proximity_overlap_to_face_coordinates(p1, face1, overlap_area, conn_id)
    if area1:
        p1["faces"][face1]["connectionAreas"].append({
            "x_min": arredondar(area1['x_min']),
            "y_min": arredondar(area1['y_min']),
            "x_max": arredondar(area1['x_max']),
            "y_max": arredondar(area1['y_max']),
            "fill": "black",
            "opacity": 0.05,
            "connectionId": conn_id
        })
    
    # Convert overlap area to face coordinates for piece 2  
    area2 = convert_proximity_overlap_to_face_coordinates(p2, face2, overlap_area, conn_id)
    if area2:
        p2["faces"][face2]["connectionAreas"].append({
            "x_min": arredondar(area2['x_min']),
            "y_min": arredondar(area2['y_min']),
            "x_max": arredondar(area2['x_max']),
            "y_max": arredondar(area2['y_max']),
                    "fill": "black",
                    "opacity": 0.05,
                    "connectionId": conn_id
        })

def convert_proximity_overlap_to_face_coordinates(piece, face_name, overlap_area, conn_id):
    """Convert proximity overlap area to face-local coordinates"""
    # Create a small stripe area within the piece bounds
    # Use connectionId to offset position and avoid duplicates
    
    if face_name in ["main", "other_main"]:
        # Length x Height faces
        max_x = piece["length"]
        max_y = piece["height"]
        
    elif face_name in ["top", "bottom"]:
        # Length x Thickness faces  
        max_x = piece["length"]
        max_y = piece["thickness"]
        
    elif face_name in ["left", "right"]:
        # Thickness x Height faces
        max_x = piece["thickness"]
        max_y = piece["height"]
    else:
        return None
    
    # Create a small 3x3mm stripe area
    stripe_width = min(3.0, max_x)
    stripe_height = min(3.0, max_y)
    
    # Offset position based on connectionId to avoid duplicates
    # Use connectionId to create different positions
    offset_x = ((conn_id - 1) % 3) * 4.0  # Offset by 4mm for each connection
    offset_y = ((conn_id - 1) // 3) * 4.0  # Stack vertically if needed
    
    # Position stripe with offset
    stripe_x_min = min(offset_x, max_x - stripe_width)
    stripe_x_max = stripe_x_min + stripe_width
    stripe_y_min = min(offset_y + max_y / 2 - stripe_height / 2, max_y - stripe_height)
    stripe_y_max = stripe_y_min + stripe_height
    
    # Ensure coordinates are within bounds
    stripe_x_min = max(0, stripe_x_min)
    stripe_x_max = min(max_x, stripe_x_max)
    stripe_y_min = max(0, stripe_y_min)
    stripe_y_max = min(max_y, stripe_y_max)
    
    return {
        'x_min': stripe_x_min,
        'y_min': stripe_y_min,
        'x_max': stripe_x_max,
        'y_max': stripe_y_max
    }

def create_simple_connection_area(piece, face_name, area_size):
    """DEPRECATED: Create a simple connection area on a face"""
    # This function is now deprecated - keeping for backwards compatibility
    # Use convert_overlap_to_face_coordinates instead for real overlap areas
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

def classify_hole_type(x, y, piece, face_name):
    """Classify hole type based on exact position on face"""
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

def map_face_holes_proximity(p1, p2, face1, face2, conn_id, template_thickness):
    """Map holes between connecting faces using proximity-based connection"""
    
    # Get connection areas to determine which holes to connect
    conn_areas_1 = [area for area in p1["faces"][face1]["connectionAreas"] if area["connectionId"] == conn_id]
    conn_areas_2 = [area for area in p2["faces"][face2]["connectionAreas"] if area["connectionId"] == conn_id]
    
    if not conn_areas_1 or not conn_areas_2:
        return
    
    area1 = conn_areas_1[0]
    area2 = conn_areas_2[0]
    
    # Create subjective holes in the connection areas - EXACTLY ONE hole per piece per connection
    area1_center_x = (area1["x_min"] + area1["x_max"]) / 2
    area1_center_y = (area1["y_min"] + area1["y_max"]) / 2
    area2_center_x = (area2["x_min"] + area2["x_max"]) / 2
    area2_center_y = (area2["y_min"] + area2["y_max"]) / 2
    
    # Check if a hole with this connectionId already exists on each face
    def connection_hole_exists(face_holes, conn_id):
        for hole in face_holes:
            if hole.get("connectionId") == conn_id:
                return True
        return False
    
    # Determine hole type based on position and face
    hole_type_1 = classify_hole_type(area1_center_x, area1_center_y, p1, face1)
    hole_type_2 = classify_hole_type(area2_center_x, area2_center_y, p2, face2)
    
    # Determine hardware based on hole type
    if hole_type_1.startswith("flap"):
        hardware_1 = "dowel_M_with_glue"
        depth_1 = 10
        diameter_1 = 8
    else:
        hardware_1 = "glue"
        depth_1 = 20
        diameter_1 = None
        
    if hole_type_2.startswith("flap"):
        hardware_2 = "dowel_M_with_glue"
        depth_2 = 10
        diameter_2 = 8
    else:
        hardware_2 = "glue"
        depth_2 = 20
        diameter_2 = None
    
    # Create subjective holes ONLY if no hole with this connectionId exists
    face1_holes = p1["faces"][face1]["holes"]
    face2_holes = p2["faces"][face2]["holes"]
    
    # Create hole on piece 1 if no connection hole exists for this connectionId
    if not connection_hole_exists(face1_holes, conn_id):
        subjective_hole_1 = criar_hole(
            area1_center_x, area1_center_y, hole_type_1, template_thickness, 
            hardware_1, conn_id, depth_1, diameter_1
        )
        face1_holes.append(subjective_hole_1)
    
    # Create hole on piece 2 if no connection hole exists for this connectionId
    if not connection_hole_exists(face2_holes, conn_id):
        subjective_hole_2 = criar_hole(
            area2_center_x, area2_center_y, hole_type_2, template_thickness,
            hardware_2, conn_id, depth_2, diameter_2
        )
        face2_holes.append(subjective_hole_2)
    
    # DO NOT assign connectionId to existing holes - only the holes we create should have connectionIds
    # This prevents multiple holes from getting the same connectionId

def clean_unconnected_holes(pieces):
    """Remove holes that don't have a connectionId (unconnected holes) - but keep singer holes and ensure all pieces have main faces"""
    for piece in pieces:
        for face_name, face in piece["faces"].items():
            # Keep ONLY holes that have connectionId (connected/subjective holes) OR are singer holes (reinforcement)
            # Remove systematic/objective holes that aren't connected
            face["holes"] = [hole for hole in face["holes"] 
                           if "connectionId" in hole or 
                              hole["type"].startswith("singer_")]

def ensure_all_pieces_have_faces(pieces, template_thickness):
    """Ensure every piece has at least main faces with singer holes for reinforcement"""
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

def add_singer_reinforcement_holes(pieces, connections, template_thickness):
    """Add singer reinforcement holes for face-to-top connections"""
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
    """Add singer holes to a specific face"""
    face = piece["faces"][face_name]
    ft = piece["half_thickness"]
    
    def hole_exists_near_position(face_holes, x, y, min_distance=5.0):
        """Check if any hole exists within min_distance of the position"""
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

def select_model_template(pieces):
    """Select model template based on thickness with most top holes"""
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

def processar_json_entrada(input_path, output_path):
    with open(input_path, "r") as f:
        data = json.load(f)

    views = extrair_views_por_peca(data)
    pecas_3d = []
    
    # Build 3D pieces
    for nome, v in views.items():
        peca = construir_peca_3d(nome, v)
        if peca:
            pecas_3d.append(peca)

    # Select template thickness
    template_thickness = select_model_template(pecas_3d)
    if not template_thickness:
        template_thickness = 20
    
    # Add systematic holes to all pieces
    for peca in pecas_3d:
        adicionar_holes_sistematicos(peca, template_thickness)
    
    # Detect connections between pieces
    connections = detect_connections_by_proximity(pecas_3d)
    
    # Map holes between connected pieces
    map_holes_between_pieces(pecas_3d, connections, template_thickness)
    
    # Clean unconnected holes (keep connected holes and singer holes)
    clean_unconnected_holes(pecas_3d)
    
    # Add singer reinforcement holes to all pieces
    for peca in pecas_3d:
        # Add singer holes to opposite main face if this piece has connections
        has_connections = any(face["connectionAreas"] for face in peca["faces"].values())
        if has_connections:
            # Add singer holes to both main faces for reinforcement
            add_singer_holes_to_face(peca, "main", template_thickness)
            add_singer_holes_to_face(peca, "other_main", template_thickness)
    
    # Ensure all pieces have at least main faces with singer holes
    ensure_all_pieces_have_faces(pecas_3d, template_thickness)

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

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

# Run with test files
processar_json_entrada("input_test.json", "output.json")
