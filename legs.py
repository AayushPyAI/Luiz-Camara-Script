import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from collections import Counter

# Configurações (valores do guia)
MARGIN = 1.0  # Margem em mm (página 4) - 1mm per side for symmetric margins
HOLE_DIAMETER = 8.0  # Diâmetro dos furos (página 4)
HOLE_DEPTH_MAIN = 10.0  # Profundidade para face main (página 4)
HOLE_DEPTH_OTHER_MAIN = 40.0  # Profundidade para singer holes (página 4)
HOLE_DEPTH_TOP = 20.0  # Profundidade para faces de espessura (página 4)
MAX_HOLE_SPACING = 200.0  # Distância máxima entre furos (página 2)
MIN_OVERLAP = 10.0  # Sobreposição mínima para conexão (página 2)
SINGER_MIN_DISTANCE = 50.0  # Distância mínima para singer_central (página 3)

@dataclass
class Bounds3D:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

@dataclass
class Piece:
    name: str
    bounds: Bounds3D
    length: float
    height: float
    thickness: float
    quantity: int
    faces: list

def round_to_one_decimal(value: float) -> float:
    """Arredonda para 1 casa decimal, ajustando para inteiro se próximo (página 1)."""
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 0.1:
        rounded = float(round(rounded))
    return rounded

def get_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> Optional[Tuple[float, float]]:
    """Calcula sobreposição com mínimo de 10mm (página 2)."""
    o_min = max(a_min, b_min)
    o_max = min(a_max, b_max)
    if o_max - o_min >= MIN_OVERLAP:
        return (round_to_one_decimal(o_min), round_to_one_decimal(o_max))
    return None

def get_connection_faces(piece_1: Piece, piece_2: Piece, primary_axis: str = 'z') -> Optional[Tuple[str, str, str, float, float, float, float]]:
    """Identifica faces conectadas e limites da sobreposição (página 2)."""
    x_overlap = get_overlap(piece_1.bounds.x_min, piece_1.bounds.x_max, piece_2.bounds.x_min, piece_2.bounds.x_max)
    y_overlap = get_overlap(piece_1.bounds.y_min, piece_1.bounds.y_max, piece_2.bounds.y_min, piece_2.bounds.y_max)
    z_overlap = get_overlap(piece_1.bounds.z_min, piece_1.bounds.z_max, piece_2.bounds.z_min, piece_2.bounds.z_max)
    
    
    # Tolerance for considering pieces as touching  
    tolerance = 1.0  # 1mm tolerance as originally specified
    
    # Enhanced logic: Always check Y-axis first for leg-to-fundo connections
    piece1_name = piece_1.name.lower()
    piece2_name = piece_2.name.lower()
    is_leg_to_fundo = ('perna' in piece1_name and 'fundo' in piece2_name) or ('fundo' in piece1_name and 'perna' in piece2_name)
    
    if is_leg_to_fundo:
        # For leg-to-fundo connections, always prioritize Y-axis detection first
        y_connection = check_y_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance)
        if y_connection:
            return y_connection
    
    # Prioritize connection types based on primary_axis for multi-view processing
    if primary_axis == 'x':
        # X-axis primary: prioritize lateral (left-right) connections first
        return check_x_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_y_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_z_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance)
    elif primary_axis == 'y':
        # Y-axis primary: prioritize vertical connections first  
        return check_y_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_x_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_z_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance)
    else:
        # Z-axis primary (default): prioritize front-back connections first
        return check_z_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_y_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance) or \
               check_x_axis_connections(piece_1, piece_2, x_overlap, y_overlap, z_overlap, tolerance)

def check_y_axis_connections(piece_1: Piece, piece_2: Piece, x_overlap, y_overlap, z_overlap, tolerance):
    """Check for Y-axis connections (vertical - table top to leg)."""
    # Check for table-top-to-leg connections (piece_1 above piece_2)
    # Allow near-touching pieces in Z direction within tolerance
    has_z_connection = (z_overlap is not None or 
                       abs(piece_1.bounds.z_min - piece_2.bounds.z_max) <= tolerance or
                       abs(piece_2.bounds.z_min - piece_1.bounds.z_max) <= tolerance)
    

    # Enhanced Y-axis detection for both X-axis and Z-axis oriented legs
    if (y_overlap is None and piece_1.bounds.y_min >= piece_2.bounds.y_max and 
        has_z_connection):
        
        # Check if this is a leg-to-fundo connection
        piece1_name = piece_1.name.lower()
        piece2_name = piece_2.name.lower()
        is_leg_to_fundo = ('perna' in piece1_name and 'fundo' in piece2_name) or ('fundo' in piece1_name and 'perna' in piece2_name)
        
        if is_leg_to_fundo:
            # For leg-to-fundo connections, handle both X-axis and Z-axis oriented legs
            if x_overlap is not None:
                # X-axis oriented leg (like Perna 4, 3)
                x_min, x_max = x_overlap
                if z_overlap is not None:
                    z_min, z_max = z_overlap
                else:
                    z_min = max(piece_1.bounds.z_min, piece_2.bounds.z_min)
                    z_max = min(piece_1.bounds.z_max, piece_2.bounds.z_max)
                return 'y', 'main', 'main', x_min, x_max, z_min, z_max
            elif z_overlap is not None:
                # Z-axis oriented leg (like Perna 2, 1)
                z_min, z_max = z_overlap
                if x_overlap is not None:
                    x_min, x_max = x_overlap
                else:
                    x_min = max(piece_1.bounds.x_min, piece_2.bounds.x_min)
                    x_max = min(piece_1.bounds.x_max, piece_2.bounds.x_max)
                return 'y', 'main', 'main', x_min, x_max, z_min, z_max
            else:
                # Edge case: no overlap but pieces are close
                # Use the touching area between pieces
                x_min = max(piece_1.bounds.x_min, piece_2.bounds.x_min)
                x_max = min(piece_1.bounds.x_max, piece_2.bounds.x_max)
                z_min = max(piece_1.bounds.z_min, piece_2.bounds.z_min)
                z_max = min(piece_1.bounds.z_max, piece_2.bounds.z_max)
                return 'y', 'main', 'main', x_min, x_max, z_min, z_max
        
        # Original logic for other Y-axis connections
        if x_overlap is not None:
            x_min, x_max = x_overlap
            
            # Handle Z coordinates for overlapping or near-touching pieces
            if z_overlap is not None:
                z_min, z_max = z_overlap
            else:
                # Use the touching area between pieces
                z_min = max(piece_1.bounds.z_min, piece_2.bounds.z_min)
                z_max = min(piece_1.bounds.z_max, piece_2.bounds.z_max)
            
            # Advanced face detection for legs at different positions
            leg_x_center = (piece_2.bounds.x_min + piece_2.bounds.x_max) / 2
            leg_z_center = (piece_2.bounds.z_min + piece_2.bounds.z_max) / 2
            tampo_x_center = (piece_1.bounds.x_min + piece_1.bounds.x_max) / 2
            tampo_z_center = (piece_1.bounds.z_min + piece_1.bounds.z_max) / 2
            
            # Determine which tampo face connects based on leg position relative to tampo center
            x_distance = abs(leg_x_center - tampo_x_center)
            z_distance = abs(leg_z_center - tampo_z_center)
            
            # Use a more sophisticated approach based on piece characteristics
            if piece_1.thickness < min(piece_1.length, piece_1.height) / 3:
                # Piece 1 is a thin horizontal panel (like tampo)
                face_1 = 'main'  # Use main face for thin horizontal pieces
            else:
                # Thicker piece - determine face based on relative positions
                if x_distance > piece_1.length * 0.3:  # Leg is far from X center
                    face_1 = 'left' if leg_x_center < tampo_x_center else 'right'
                elif z_distance > piece_1.height * 0.3:  # Leg is far from Z center  
                    face_1 = 'top' if leg_z_center < tampo_z_center else 'bottom'
                else:
                    face_1 = 'main'  # Leg is centrally located
            
            return 'y', face_1, 'main', x_min, x_max, z_min, z_max
    
    # Original touching piece logic for Y-axis
    elif y_overlap is None and abs(piece_1.bounds.y_max - piece_2.bounds.y_min) < tolerance:
        # Conexão face-topo: main do tampo com top da perna
        x_min, x_max = x_overlap if x_overlap else (piece_2.bounds.x_min, piece_2.bounds.x_max)
        z_min, z_max = z_overlap if z_overlap else (piece_2.bounds.z_min, piece_2.bounds.z_max)
        return 'y', 'main', 'top', x_min, x_max, z_min, z_max
    elif y_overlap is None and abs(piece_2.bounds.y_max - piece_1.bounds.y_min) < tolerance:
        # Reverse connection
        x_min, x_max = x_overlap if x_overlap else (piece_1.bounds.x_min, piece_1.bounds.x_max)
        z_min, z_max = z_overlap if z_overlap else (piece_1.bounds.z_min, piece_1.bounds.z_max)
        return 'y', 'top', 'main', x_min, x_max, z_min, z_max
    
    return None

def check_x_axis_connections(piece_1: Piece, piece_2: Piece, x_overlap, y_overlap, z_overlap, tolerance):
    """Check for X-axis connections (lateral - left to right)."""
    if x_overlap is None and abs(piece_1.bounds.x_max - piece_2.bounds.x_min) <= tolerance:
        # Piece 1's right edge connects to piece 2's left edge
        y_min, y_max = y_overlap if y_overlap else (max(piece_1.bounds.y_min, piece_2.bounds.y_min), 
                                                     min(piece_1.bounds.y_max, piece_2.bounds.y_max))
        z_min, z_max = z_overlap if z_overlap else (max(piece_1.bounds.z_min, piece_2.bounds.z_min),
                                                     min(piece_1.bounds.z_max, piece_2.bounds.z_max))
        return 'x', 'right', 'left', y_min, y_max, z_min, z_max
    elif x_overlap is None and abs(piece_2.bounds.x_max - piece_1.bounds.x_min) <= tolerance:
        # Piece 2's right edge connects to piece 1's left edge
        y_min, y_max = y_overlap if y_overlap else (max(piece_1.bounds.y_min, piece_2.bounds.y_min),
                                                     min(piece_1.bounds.y_max, piece_2.bounds.y_max))
        z_min, z_max = z_overlap if z_overlap else (max(piece_1.bounds.z_min, piece_2.bounds.z_min),
                                                     min(piece_1.bounds.z_max, piece_2.bounds.z_max))
        return 'x', 'left', 'right', y_min, y_max, z_min, z_max
    
    return None

def check_z_axis_connections(piece_1: Piece, piece_2: Piece, x_overlap, y_overlap, z_overlap, tolerance):
    """Check for Z-axis connections (front to back)."""
    if z_overlap is None and abs(piece_1.bounds.z_max - piece_2.bounds.z_min) <= tolerance:
        # Piece 1's back edge connects to piece 2's front edge
        x_min, x_max = x_overlap if x_overlap else (piece_2.bounds.x_min, piece_2.bounds.x_max)
        y_min, y_max = y_overlap if y_overlap else (piece_2.bounds.y_min, piece_2.bounds.y_max)
        
        # Determine appropriate edge faces based on piece orientation
        # If pieces are thin panels (thickness much smaller than length/height), use edge faces
        if piece_1.thickness < min(piece_1.length, piece_1.height) / 2:
            face_1 = 'bottom' if piece_1.bounds.y_min > piece_2.bounds.y_max else 'top'
        else:
            face_1 = 'main'
            
        if piece_2.thickness < min(piece_2.length, piece_2.height) / 2:
            face_2 = 'top' if piece_2.bounds.y_min < piece_1.bounds.y_max else 'bottom'
        else:
            face_2 = 'main'
            
        return 'z', face_1, face_2, x_min, x_max, y_min, y_max
        
    elif z_overlap is None and abs(piece_2.bounds.z_max - piece_1.bounds.z_min) <= tolerance:
        # Piece 2's back edge connects to piece 1's front edge
        x_min, x_max = x_overlap if x_overlap else (piece_1.bounds.x_min, piece_1.bounds.x_max)
        y_min, y_max = y_overlap if y_overlap else (piece_1.bounds.y_min, piece_1.bounds.y_max)
        
        # Determine appropriate edge faces based on piece orientation
        if piece_2.thickness < min(piece_2.length, piece_2.height) / 2:
            face_2 = 'bottom' if piece_2.bounds.y_min > piece_1.bounds.y_max else 'top'
        else:
            face_2 = 'main'
            
        if piece_1.thickness < min(piece_1.length, piece_1.height) / 2:
            face_1 = 'top' if piece_1.bounds.y_min < piece_2.bounds.y_max else 'bottom'
        else:
            face_1 = 'main'
            
        return 'z', face_1, face_2, x_min, x_max, y_min, y_max
    
    return None

def add_connection_area(piece: Piece, face_side: str, x_min: float, x_max: float, y_min: float, y_max: float, connection_id: int):
    """Adiciona área de conexão com margem simétrica de 1mm em todos os lados. Permite múltiplas CAs por face."""
    if face_side not in [face['faceSide'] for face in piece.faces]:
        piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
    
    face_obj = next(face for face in piece.faces if face['faceSide'] == face_side)
    
    # Apply symmetric margins on all sides (inset by MARGIN on each side)
    x_min += MARGIN
    x_max -= MARGIN
    y_min += MARGIN
    y_max -= MARGIN
    
    # Ensure valid dimensions after margin application
    if x_max <= x_min or y_max <= y_min:
        return  # Invalid area after margins
    
    # Check for overlaps with existing connection areas
    new_area = {
        'x_min': x_min,
        'x_max': x_max, 
        'y_min': y_min,
        'y_max': y_max
    }
    
    # Strict rectangle overlap detection
    for existing_ca in face_obj['connectionAreas']:
        if (new_area['x_min'] < existing_ca['x_max'] and new_area['x_max'] > existing_ca['x_min'] and
            new_area['y_min'] < existing_ca['y_max'] and new_area['y_max'] > existing_ca['y_min']):
            return  # Overlaps with existing CA - skip adding
    
    # Add connection area
    face_obj['connectionAreas'].append({
        'x_min': round_to_one_decimal(x_min),
        'y_min': round_to_one_decimal(y_min),
        'x_max': round_to_one_decimal(x_max),
        'y_max': round_to_one_decimal(y_max),
        'fill': 'black',
        'opacity': 0.05,
        'connectionId': connection_id
    })

def add_initial_holes(piece: Piece, face_side: str):
    """Adiciona furos objetivos iniciais em todas as faces (página 2)."""
    half_thickness = piece.thickness / 2
    depth = HOLE_DEPTH_MAIN if face_side in ['main', 'other_main'] else HOLE_DEPTH_TOP
    hole_type_prefix = 'flap' if face_side in ['main', 'other_main'] else 'top'
    
    x_max = piece.length if face_side in ['main', 'other_main', 'top', 'bottom'] else piece.thickness
    y_max = piece.height if face_side in ['main', 'other_main', 'left', 'right'] else piece.thickness
    
    # Furos nos cantos
    corners = [
        (half_thickness, half_thickness),
        (half_thickness, y_max - half_thickness),
        (x_max - half_thickness, half_thickness),
        (x_max - half_thickness, y_max - half_thickness)
    ]
    for x, y in corners:
        add_hole(piece, face_side, x, y, f'{hole_type_prefix}_corner', None, depth)
    
    # Furos intermediários se distância > 200mm
    if x_max - 2 * half_thickness > MAX_HOLE_SPACING:
        num_x_holes = int(math.ceil((x_max - 2 * half_thickness) / MAX_HOLE_SPACING)) + 1
        step_x = (x_max - 2 * half_thickness) / (num_x_holes - 1)
        for i in range(1, num_x_holes - 1):
            x = half_thickness + i * step_x
            add_hole(piece, face_side, x, half_thickness, f'{hole_type_prefix}_central', None, depth)
            add_hole(piece, face_side, x, y_max - half_thickness, f'{hole_type_prefix}_central', None, depth)
    
    if y_max - 2 * half_thickness > MAX_HOLE_SPACING:
        num_y_holes = int(math.ceil((y_max - 2 * half_thickness) / MAX_HOLE_SPACING)) + 1
        step_y = (y_max - 2 * half_thickness) / (num_y_holes - 1)
        for i in range(1, num_y_holes - 1):
            y = half_thickness + i * step_y
            add_hole(piece, face_side, half_thickness, y, f'{hole_type_prefix}_central', None, depth)
            add_hole(piece, face_side, x_max - half_thickness, y, f'{hole_type_prefix}_central', None, depth)

def add_hole(piece: Piece, face_side: str, x: float, y: float, hole_type: str, connection_id: Optional[int], depth: float):
    """Adiciona um furo com hardware apropriado (página 4)."""
    if face_side not in [face['faceSide'] for face in piece.faces]:
        piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
    
    # Prevent duplicate holes at the same coordinates
    rounded_x = round_to_one_decimal(x)
    rounded_y = round_to_one_decimal(y)
    
    for face in piece.faces:
        if face['faceSide'] == face_side:
            # Check if hole already exists at these coordinates
            for existing_hole in face['holes']:
                if (existing_hole['x'] == rounded_x and 
                    existing_hole['y'] == rounded_y):
                    # Update existing hole with connection_id if needed
                    if connection_id is not None and 'connectionId' not in existing_hole:
                        existing_hole['connectionId'] = connection_id
                    return  # Don't add duplicate hole
    
    ferragem = 'dowel_M_with_glue' if hole_type in ['flap_corner', 'flap_central', 'face_central'] else \
               'dowel_G_with_glue' if hole_type in ['singer_flap', 'singer_central', 'singer_channel'] else \
               'glue'
    
    hole = {
        'x': rounded_x,
        'y': rounded_y,
        'type': hole_type,
        'targetType': '20',
        'ferragemSymbols': [ferragem],
        'ring': True,
        'color': 'blue',
        'symbol': hole_type.upper(),
        'depth': depth,
        'diameter': HOLE_DIAMETER
    }
    if connection_id is not None:
        hole['connectionId'] = connection_id
    
    for face in piece.faces:
        if face['faceSide'] == face_side:
            face['holes'].append(hole)

def add_initial_holes(piece: Piece, face_side: str):
    """Adiciona furos objetivos iniciais em todas as faces (página 2)."""
    half_thickness = piece.thickness / 2
    depth = HOLE_DEPTH_MAIN if face_side in ['main', 'other_main'] else HOLE_DEPTH_TOP
    hole_type_prefix = 'flap' if face_side in ['main', 'other_main'] else 'top'
    
    x_max = piece.length if face_side in ['main', 'other_main', 'top', 'bottom'] else piece.thickness
    y_max = piece.height if face_side in ['main', 'other_main', 'left', 'right'] else piece.thickness
    
    # Furos nos cantos
    corners = [
        (half_thickness, half_thickness),
        (half_thickness, y_max - half_thickness),
        (x_max - half_thickness, half_thickness),
        (x_max - half_thickness, y_max - half_thickness)
    ]
    for x, y in corners:
        add_hole(piece, face_side, x, y, f'{hole_type_prefix}_corner', None, depth)
    
    # Furos intermediários se distância > 200mm
    if x_max - 2 * half_thickness > MAX_HOLE_SPACING:
        num_x_holes = int(math.ceil((x_max - 2 * half_thickness) / MAX_HOLE_SPACING)) + 1
        step_x = (x_max - 2 * half_thickness) / (num_x_holes - 1)
        for i in range(1, num_x_holes - 1):
            x = half_thickness + i * step_x
            add_hole(piece, face_side, x, half_thickness, f'{hole_type_prefix}_central', None, depth)
            add_hole(piece, face_side, x, y_max - half_thickness, f'{hole_type_prefix}_central', None, depth)
    
    if y_max - 2 * half_thickness > MAX_HOLE_SPACING:
        num_y_holes = int(math.ceil((y_max - 2 * half_thickness) / MAX_HOLE_SPACING)) + 1
        step_y = (y_max - 2 * half_thickness) / (num_y_holes - 1)
        for i in range(1, num_y_holes - 1):
            y = half_thickness + i * step_y
            add_hole(piece, face_side, half_thickness, y, f'{hole_type_prefix}_central', None, depth)
            add_hole(piece, face_side, x_max - half_thickness, y, f'{hole_type_prefix}_central', None, depth)

def clean_holes_outside_connection_areas(piece: Piece):
    """Remove furos objetivos fora das áreas de conexão (página 3)."""
    for face in piece.faces:
        valid_holes = []
        for hole in face['holes']:
            if 'connectionId' in hole:
                in_area = False
                for area in face['connectionAreas']:
                    if (area['x_min'] <= hole['x'] <= area['x_max'] and
                        area['y_min'] <= hole['y'] <= area['y_max'] and
                        area['connectionId'] == hole['connectionId']):
                        in_area = True
                        break
                if in_area:
                    valid_holes.append(hole)
            else:
                valid_holes.append(hole)  # Manter furos sem connectionId (ex.: singer)
        face['holes'] = valid_holes

def calculate_face_coordinates(piece: Piece, face_side: str, axis: str, min_1: float, max_1: float, min_2: float, max_2: float) -> Tuple[float, float, float, float]:
    """Calculate local face coordinates for connection areas without margins (margins applied in add_connection_area)."""
    
    # Map actual global overlap coordinates to local face coordinates
    # This positions CA at the real connection area, not face center
    
    if axis == 'y':  # Vertical connections (table top to leg)
        if face_side in ['main', 'other_main']:
            # For main faces: X overlap maps to X, Z overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.x_min)
            x_max = min(piece.length, max_1 - piece.bounds.x_min)
            y_min = max(0, min_2 - piece.bounds.z_min)
            y_max = min(piece.height, max_2 - piece.bounds.z_min)
        elif face_side in ['top', 'bottom']:
            # For top/bottom faces: X overlap maps to X, Z overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.x_min)
            x_max = min(piece.length, max_1 - piece.bounds.x_min)
            y_min = max(0, min_2 - piece.bounds.z_min)
            y_max = min(piece.thickness, max_2 - piece.bounds.z_min)
        else:
            # For left/right faces: Z overlap maps to X, Y overlap maps to Y  
            x_min = max(0, min_2 - piece.bounds.z_min)
            x_max = min(piece.thickness, max_2 - piece.bounds.z_min)
            y_min = max(0, min_1 - piece.bounds.y_min)
            y_max = min(piece.height, max_1 - piece.bounds.y_min)
                
    elif axis == 'x':  # Lateral connections (left to right)
        if face_side in ['main', 'other_main']:
            # For main faces: Y overlap maps to X, Z overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.y_min)
            x_max = min(piece.height, max_1 - piece.bounds.y_min)
            y_min = max(0, min_2 - piece.bounds.z_min)
            y_max = min(piece.length, max_2 - piece.bounds.z_min)
        elif face_side in ['left', 'right']:
            # For left/right faces: Y overlap maps to X, Z overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.y_min)
            x_max = min(piece.height, max_1 - piece.bounds.y_min)
            y_min = max(0, min_2 - piece.bounds.z_min)
            y_max = min(piece.thickness, max_2 - piece.bounds.z_min)
        else:
            # For top/bottom faces: Y overlap maps to X, Z overlap maps to Y  
            x_min = max(0, min_1 - piece.bounds.y_min)
            x_max = min(piece.length, max_1 - piece.bounds.y_min)
            y_min = max(0, min_2 - piece.bounds.z_min)
            y_max = min(piece.thickness, max_2 - piece.bounds.z_min)
                
    else:  # axis == 'z' - Front/back connections
        if face_side in ['main', 'other_main']:
            # For main faces: X overlap maps to X, Y overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.x_min)
            x_max = min(piece.length, max_1 - piece.bounds.x_min)
            y_min = max(0, min_2 - piece.bounds.y_min)
            y_max = min(piece.height, max_2 - piece.bounds.y_min)
        elif face_side in ['top', 'bottom']:
            # For top/bottom faces: X overlap maps to X, Y overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.x_min)
            x_max = min(piece.length, max_1 - piece.bounds.x_min)
            y_min = max(0, min_2 - piece.bounds.y_min)
            y_max = min(piece.thickness, max_2 - piece.bounds.y_min)
        else:
            # For left/right faces: X overlap maps to X, Y overlap maps to Y
            x_min = max(0, min_1 - piece.bounds.x_min)
            x_max = min(piece.thickness, max_1 - piece.bounds.x_min)
            y_min = max(0, min_2 - piece.bounds.y_min)
            y_max = min(piece.height, max_2 - piece.bounds.y_min)

    # Ensure valid coordinates (all positive, x_min < x_max, y_min < y_max)
    if x_max <= x_min or y_max <= y_min or x_min < 0 or y_min < 0:
        # Fallback to edge-positioned small area (without margins - will be applied later)
        if face_side in ['left', 'right']:
            x_min = 0
            x_max = min(50.0, piece.thickness)
            y_min = 0
            y_max = min(20.0, piece.height)
        elif face_side in ['top', 'bottom']:
            x_min = 0
            x_max = min(50.0, piece.length)
            y_min = 0
            y_max = min(20.0, piece.thickness)
        else:  # main, other_main
            x_min = 0
            x_max = min(50.0, piece.length)
            y_min = 0
            y_max = min(20.0, piece.height)
        
    return (x_min, x_max, y_min, y_max)

def add_singer_holes(piece: Piece, main_holes: List[Dict], connection_id: int, face_side: str):
    """Adiciona furos singer na face oposta (página 3)."""
    opposite_face = 'other_main' if face_side == 'main' else 'main'
    for hole in main_holes:
        x, y = hole['x'], piece.height - hole['y']  # Espelhar verticalmente
        hole_type = 'singer_flap' if (abs(x - piece.thickness / 2) < 0.05 or abs(x - piece.length + piece.thickness / 2) < 0.05 or
                                      abs(y - piece.thickness / 2) < 0.05 or abs(y - piece.height + piece.thickness / 2) < 0.05) else 'singer_central'
        if hole_type == 'singer_central' and (min(x, piece.length - x, y, piece.height - y) < SINGER_MIN_DISTANCE):
            continue
        add_hole(piece, opposite_face, x, y, hole_type, None, HOLE_DEPTH_OTHER_MAIN)

def map_holes_to_connection(piece_1: Piece, piece_2: Piece, connection_id: int, face_1: str, face_2: str, x_min: float, x_max: float, y_min_1: float, y_max_1: float, y_min_2: float, y_max_2: float):
    """Mapeia furos subjetivos nas áreas de conexão pareadas (página 3)."""
    holes_1 = []
    for face in piece_1.faces:
        if face['faceSide'] == face_1:
            for hole in face['holes']:
                if 'connectionId' in hole and hole['connectionId'] == connection_id:
                    holes_1.append(hole)
    
    # Mapear furos subjetivos na peça secundária
    x_length = x_max - x_min
    y_length = y_max_2 - y_min_2
    for hole in holes_1:
        x = hole['x'] - x_min
        y = hole['y'] - y_min_1 + y_min_2
        if face_2 in ['top', 'bottom']:
            y = (y_min_2 + y_max_2) / 2  # Centralizar na espessura
        hole_type = 'top_corner' if hole['type'] == 'flap_corner' else 'top_central' if hole['type'] == 'flap_central' else 'face_central'
        if 0 <= x <= x_length and 0 <= y <= y_length:
            add_hole(piece_2, face_2, x, y, hole_type, connection_id, HOLE_DEPTH_TOP)
    
    # Adicionar furos singer na face oposta da peça principal (se face-topo)
    if face_1 in ['main', 'other_main'] and face_2 in ['top', 'bottom', 'left', 'right']:
        add_singer_holes(piece_1, holes_1, connection_id, face_1)

def create_connection(piece_1: Piece, piece_2: Piece, connection_id: int):
    """Cria conexão entre peças, com áreas e furos (páginas 2-4)."""
    connection = get_connection_faces(piece_1, piece_2)
    if not connection:
        return
    
    axis, face_1, face_2, min_1, max_1, min_2, max_2 = connection
    
    # Calculate connection area coordinates for each piece in their local face coordinate system
    x_min_1, x_max_1, y_min_1, y_max_1 = calculate_face_coordinates(piece_1, face_1, axis, min_1, max_1, min_2, max_2)
    x_min_2, x_max_2, y_min_2, y_max_2 = calculate_face_coordinates(piece_2, face_2, axis, min_1, max_1, min_2, max_2)
    
    # Adicionar áreas de conexão
    add_connection_area(piece_1, face_1, x_min_1, x_max_1, y_min_1, y_max_1, connection_id)
    add_connection_area(piece_2, face_2, x_min_2, x_max_2, y_min_2, y_max_2, connection_id)
    
    # Atribuir connectionId aos furos objetivos dentro da área
    for face in piece_1.faces:
        if face['faceSide'] == face_1:
            for hole in face['holes']:
                if ('connectionId' not in hole and
                    x_min_1 <= hole['x'] <= x_max_1 and
                    y_min_1 <= hole['y'] <= y_max_1):
                    hole['connectionId'] = connection_id
    
    for face in piece_2.faces:
        if face['faceSide'] == face_2:
            for hole in face['holes']:
                if ('connectionId' not in hole and
                    x_min_2 <= hole['x'] <= x_max_2 and
                    y_min_2 <= hole['y'] <= y_max_2):
                    hole['connectionId'] = connection_id
    
    # Mapear furos subjetivos
    map_holes_to_connection(piece_1, piece_2, connection_id, face_1, face_2, x_min_1, x_max_1, y_min_1, y_max_1, x_min_2, y_max_2)

def process_single_axis_connections(pieces: List[Piece], main_piece: Piece) -> int:
    """Process connections primarily from Z-axis with targeted Y-axis for leg-to-fundo connections."""
    connection_id = 1
    all_connections = []  # Store all detected connections to avoid duplicates
    
    print("Single-axis connection processing:")
    
    # Primary Z-axis processing (this was working well)
    connections_z = 0
    print(f"  Processing Z-axis primary view...")
    
    # Primary connections: main piece to others (Z-axis)
    for piece in pieces:
        if piece != main_piece:
            connection = get_connection_faces(main_piece, piece, 'z')
            if connection:
                axis, face_1, face_2, min_1, max_1, min_2, max_2 = connection
                connection_key = (main_piece.name, piece.name, axis, face_1, face_2)
                
                if connection_key not in all_connections:
                    create_connection(main_piece, piece, connection_id)
                    all_connections.append(connection_key)
                    connection_id += 1
                    connections_z += 1
    
    # Secondary connections: piece to piece (Z-axis only, selective)
    for i, piece1 in enumerate(pieces):
        for j, piece2 in enumerate(pieces):
            if i < j and piece1 != main_piece and piece2 != main_piece:
                connection = get_connection_faces(piece1, piece2, 'z')
                if connection:
                    axis, face_1, face_2, min_1, max_1, min_2, max_2 = connection
                    connection_key = (piece1.name, piece2.name, axis, face_1, face_2)
                    
                    # Apply selective filtering for secondary connections
                    if connection_key not in all_connections and should_allow_secondary_connection(piece1, piece2, axis):
                        create_connection(piece1, piece2, connection_id)
                        all_connections.append(connection_key)
                        connection_id += 1
                        connections_z += 1
    
    print(f"    Found {connections_z} connections from Z-axis view")
    
    # Targeted Y-axis processing for leg-to-fundo connections only
    connections_y = 0
    print(f"  Processing targeted Y-axis for leg-to-fundo connections...")
    
    # Find fundo piece
    fundo_piece = None
    for piece in pieces:
        if 'fundo' in piece.name.lower():
            fundo_piece = piece
            break
    
    if fundo_piece:
        # Check each leg for Y-axis connection to fundo
        for piece in pieces:
            if 'perna' in piece.name.lower():
                connection = get_connection_faces(piece, fundo_piece, 'y')
                if connection:
                    axis, face_1, face_2, min_1, max_1, min_2, max_2 = connection
                    connection_key = (piece.name, fundo_piece.name, axis, face_1, face_2)
                    
                    if connection_key not in all_connections:
                        create_connection(piece, fundo_piece, connection_id)
                        all_connections.append(connection_key)
                        connection_id += 1
                        connections_y += 1
    
    print(f"    Found {connections_y} leg-to-fundo connections from Y-axis view")
    print(f"  Single-axis processing complete: {len(all_connections)} unique connections found")
    return connection_id

def should_allow_secondary_connection(piece1: Piece, piece2: Piece, axis: str) -> bool:
    """Determine if a secondary connection should be allowed based on piece types and axis."""
    # Prevent leg-to-leg connections (they should only connect to fundo, tampo, subtampo)
    piece1_name = piece1.name.lower()
    piece2_name = piece2.name.lower()
    
    # If both pieces are legs, don't allow connection
    if 'perna' in piece1_name and 'perna' in piece2_name:
        return False
    
    # Allow X and Z axis connections (lateral and front-back)
    # Also allow Y-axis connections if both pieces are horizontal panels
    if axis in ['x', 'z']:
        return True
    elif axis == 'y':
        # Check if both pieces are horizontal panels
        piece1_height = piece1.bounds.y_max - piece1.bounds.y_min
        piece1_width_x = piece1.bounds.x_max - piece1.bounds.x_min
        piece1_width_z = piece1.bounds.z_max - piece1.bounds.z_min
        max_horizontal_dim1 = max(piece1_width_x, piece1_width_z)
        is_horizontal_panel1 = piece1_height < max_horizontal_dim1 * 0.3
        
        piece2_height = piece2.bounds.y_max - piece2.bounds.y_min
        piece2_width_x = piece2.bounds.x_max - piece2.bounds.x_min
        piece2_width_z = piece2.bounds.z_max - piece2.bounds.z_min
        max_horizontal_dim2 = max(piece2_width_x, piece2_width_z)
        is_horizontal_panel2 = piece2_height < max_horizontal_dim2 * 0.3
        
        return is_horizontal_panel1 and is_horizontal_panel2
    
    return False

def create_systematic_connection_areas(pieces: List[Piece], next_connection_id: int):
    """Create connection areas based on systematic pattern - preserve multi-view CAs and add systematic ones."""
    connection_id = next_connection_id
    
    # Calculate reference size for identical tampo/subtampo CAs from actual piece data
    tampo_subtampo_pieces = [p for p in pieces if 'tampo' in p.name.lower()]
    if tampo_subtampo_pieces:
        # Use the smallest dimension from tampo/subtampo pieces as reference
        # This ensures both tampo and subtampo get identical CA dimensions
        reference_size = min(min(p.length, p.height) for p in tampo_subtampo_pieces)
    else:
        reference_size = None
    
    for piece in pieces:
        # Determine piece type and create appropriate systematic connection areas
        piece_name_lower = piece.name.lower()
        
        if piece_name_lower == 'tampo':
            # Clear existing CAs for tampo and create identical CA
            for face in piece.faces:
                if face['faceSide'] == 'main':
                    face['connectionAreas'] = []
            create_identical_connection_area(piece, 'main', connection_id, reference_size)
            connection_id += 1
        elif piece_name_lower == 'subtampo':
            # Clear ALL CAs for subtampo (multi-view may add unwanted CAs to other faces)
            for face in piece.faces:
                face['connectionAreas'] = []
            create_identical_connection_area(piece, 'main', connection_id, reference_size)
            connection_id += 1
        elif piece_name_lower == 'fundo':
            # For fundo: clear ALL CAs and ensure we have ONLY 4 edge CAs (no main face CA)
            for face in piece.faces:
                face['connectionAreas'] = []
            connection_id = create_fundo_edge_only_connection_areas(piece, connection_id)
        elif 'perna' in piece_name_lower:
            # For legs: clear systematic CAs and preserve only necessary detected CAs
            if 'top' not in [face['faceSide'] for face in piece.faces]:
                piece.faces.append({'faceSide': 'top', 'holes': [], 'connectionAreas': []})
            if 'main' not in [face['faceSide'] for face in piece.faces]:
                piece.faces.append({'faceSide': 'main', 'holes': [], 'connectionAreas': []})
            
            # Clear systematic CAs from top and main faces only (preserve edge face CAs from detection)
            for face in piece.faces:
                if face['faceSide'] in ['top', 'main']:
                    face['connectionAreas'] = []
            
            # Clean unwanted edge face CAs that shouldn't be there for legs
            for face in piece.faces:
                if face['faceSide'] in ['left', 'right', 'bottom']:
                    # Remove systematic CAs but preserve genuine connection CAs
                    # Only keep CAs that have corresponding connection IDs in other pieces
                    valid_cas = []
                    for ca in face['connectionAreas']:
                        # Check if this CA's connection ID exists in other pieces (genuine connection)
                        connection_id_exists = False
                        for other_piece in pieces:
                            if other_piece != piece:
                                for other_face in other_piece.faces:
                                    for other_ca in other_face['connectionAreas']:
                                        if other_ca.get('connectionId') == ca.get('connectionId'):
                                            connection_id_exists = True
                                            break
                                    if connection_id_exists:
                                        break
                            if connection_id_exists:
                                break
                        if connection_id_exists:
                            valid_cas.append(ca)
                    face['connectionAreas'] = valid_cas
            
            # Add 1 CA on top face and 2 CAs on main face for legs
            connection_id = create_leg_multiple_connection_areas(piece, 'top', connection_id, pieces)
            connection_id = create_leg_multiple_connection_areas(piece, 'main', connection_id, pieces)
        else:
            # Default - clear main face and create central CA
            for face in piece.faces:
                if face['faceSide'] == 'main':
                    face['connectionAreas'] = []
            create_central_connection_area(piece, 'main', connection_id)
            connection_id += 1

def create_central_connection_area(piece: Piece, face_side: str, connection_id: int):
    """Create a central connection area on the specified face."""
    if face_side in ['main', 'other_main']:
        # Ensure the face exists before adding CA
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Calculate central area (50% of piece dimensions)
        center_x = piece.length / 2
        center_y = piece.height / 2
        area_size = min(piece.length, piece.height) * 0.3  # 30% of smaller dimension
        
        x_min = center_x - area_size / 2
        x_max = center_x + area_size / 2
        y_min = center_y - area_size / 2
        y_max = center_y + area_size / 2
        
        add_connection_area(piece, face_side, x_min, x_max, y_min, y_max, connection_id)

def create_large_central_connection_area(piece: Piece, face_side: str, connection_id: int):
    """Create a large central connection area covering the whole main face (like subtampo)."""
    if face_side in ['main', 'other_main']:
        # Ensure the face exists before adding CA
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Create CA covering the WHOLE face with minimal margins (just for the 1mm symmetric margin that gets applied)
        # The add_connection_area function will apply 1mm margins automatically
        x_min = 0
        x_max = piece.length  
        y_min = 0
        y_max = piece.height
        
        add_connection_area(piece, face_side, x_min, x_max, y_min, y_max, connection_id)

def create_corner_connection_areas(piece: Piece, face_side: str):
    """Create 4 corner connection areas on the specified face."""
    if face_side in ['main', 'other_main']:
        # Ensure the face exists before adding CAs
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Calculate corner positions
        margin = min(piece.length, piece.height) * 0.1  # 10% margin
        area_size = min(piece.length, piece.height) * 0.15  # 15% of smaller dimension
        
        # Top-left corner
        add_connection_area(piece, face_side, 
                          margin, margin + area_size, 
                          piece.height - margin - area_size, piece.height - margin, 1)
        
        # Top-right corner
        add_connection_area(piece, face_side, 
                          piece.length - margin - area_size, piece.length - margin, 
                          piece.height - margin - area_size, piece.height - margin, 2)
        
        # Bottom-left corner
        add_connection_area(piece, face_side, 
                          margin, margin + area_size, 
                          margin, margin + area_size, 3)
        
        # Bottom-right corner
        add_connection_area(piece, face_side, 
                          piece.length - margin - area_size, piece.length - margin, 
                          margin, margin + area_size, 4)



def create_fundo_edge_only_connection_areas(piece: Piece, start_connection_id: int) -> int:
    """Create connection areas for fundo piece - ONLY on edge faces (no main face)."""
    connection_id = start_connection_id
    
    # Ensure all edge faces exist
    for face_side in ['top', 'bottom', 'left', 'right']:
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
    
    # Create exactly 4 CAs - one on each edge face only
    for face_side in ['top', 'bottom', 'left', 'right']:
        if face_side in ['top', 'bottom']:
            # Top and bottom faces: full length x thickness
            add_connection_area(piece, face_side, 0, piece.length, 0, piece.thickness, connection_id)
        else:  # left, right
            # Left and right faces: thickness x full height  
            add_connection_area(piece, face_side, 0, piece.thickness, 0, piece.height, connection_id)
        connection_id += 1
    
    return connection_id

def create_full_coverage_connection_area(piece: Piece, face_side: str, connection_id: int):
    """Create a full coverage connection area on the specified face."""
    if face_side == 'top':
        # Ensure the face exists before adding CA
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Full coverage for leg top faces with proper dimensions
        # Use the actual piece dimensions for accurate positioning
        x_min = 0
        x_max = piece.length
        y_min = 0
        y_max = piece.thickness
        
        add_connection_area(piece, face_side, x_min, x_max, y_min, y_max, connection_id)

def create_leg_multiple_connection_areas(piece: Piece, face_side: str, start_connection_id: int, pieces: List[Piece]) -> int:
    """Create connection areas on legs - 1 CA on top face, 2 CAs on main face (horizontal + vertical)."""
    connection_id = start_connection_id
    
    if face_side == 'top':
        # Ensure the face exists before adding CAs
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Create 1 CA on the top face of legs (full coverage)
        add_connection_area(piece, face_side, 0, piece.length, 0, piece.thickness, connection_id)
        connection_id += 1
    
    elif face_side == 'main':
        # Ensure the face exists before adding CAs
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Create 2 CAs on the main face of legs:
        # 1. Horizontal CA (existing - for leg-to-fundo connections)
        # 2. Vertical CA (new - for leg-to-tampo connections)
        
        # Horizontal CA - almost full width, positioned at bottom (for leg-to-fundo)
        horizontal_height = min(piece.thickness, 17.6)  # Reduced height to avoid overlap with vertical CA
        horizontal_width = piece.length * 0.98 + 2.0  # 98% + 2mm to reach 97.6mm target
        # Position at bottom of the face (y starts from bottom, not top)
        horizontal_y_start = piece.height - horizontal_height
        add_connection_area(piece, face_side, 0, horizontal_width, horizontal_y_start, piece.height, connection_id)
        connection_id += 1
        
        # Vertical CA - dynamically match fundo edge CA dimensions (for leg-to-tampo)
        # Find fundo piece to get its edge CA dimensions dynamically
        fundo_edge_width = piece.thickness  # Default fallback
        fundo_edge_height = piece.height * 0.9  # Default fallback
        
        # Look for fundo piece to get its actual edge CA dimensions
        # Use a more robust approach to ensure ALL legs get the same dimensions
        fundo_found = False
        for other_piece in pieces:
            if 'fundo' in other_piece.name.lower():
                # Find the tallest edge CA (this will be the main edge CA we need)
                best_ca = None
                best_height = 0
                for face in other_piece.faces:
                    if face['faceSide'] in ['left', 'right'] and face['connectionAreas']:
                        for ca in face['connectionAreas']:
                            ca_height = ca['y_max'] - ca['y_min']
                            # Look for the tallest edge CA (should be ~177.6mm)
                            if ca_height > best_height and ca_height > 100.0:  # Must be tall enough
                                best_height = ca_height
                                best_ca = ca
                
                if best_ca:
                    fundo_edge_width = best_ca['x_max'] - best_ca['x_min']
                    fundo_edge_height = best_ca['y_max'] - best_ca['y_min']
                    fundo_found = True
                    break
        
        # If fundo not found or no suitable CA, use the known exact dimensions
        if not fundo_found:
            fundo_edge_width = 17.6
            fundo_edge_height = 177.6
        
        # Use fundo's edge CA dimensions for the vertical CA
        # Add 2mm to compensate for the 1mm margins on each side applied by add_connection_area
        vertical_width = fundo_edge_width + 2.0  # Compensate for margins to get exact fundo dimensions
        vertical_height = fundo_edge_height + 2.0  # Compensate for margins to get exact fundo dimensions
        
        # Ensure vertical_width and vertical_height are always defined
        if 'vertical_width' not in locals():
            vertical_width = fundo_edge_width + 2.0  # Add 2mm to get exact 17.6mm after margins
        if 'vertical_height' not in locals():
            vertical_height = fundo_edge_height + 2.0  # Add 2mm to get exact 177.6mm after margins
            
        # Position at the right edge to avoid overlap with horizontal CA
        vertical_x_start = piece.length - vertical_width
        # Position vertical CA from top to avoid overlap with horizontal CA
        # Ensure vertical CA ends before horizontal CA starts (horizontal CA starts at y_min: 181.0)
        # The fundo edge CA height (177.6mm) should fit within the available space
        # Available space: 181.0 (horizontal CA start) - 1.0 (vertical CA start) = 180.0mm
        # Fundo edge CA height: 177.6mm, so it should fit perfectly
        vertical_y_start = 1.0  # Start from top with 1mm margin (same as fundo)
        

        

        add_connection_area(piece, face_side, vertical_x_start, vertical_x_start + vertical_width, vertical_y_start, vertical_y_start + vertical_height, connection_id)
        connection_id += 1
    
    return connection_id

def create_identical_connection_area(piece: Piece, face_side: str, connection_id: int, reference_size: float = None):
    """Create identical connection area coordinates for tampo and subtampo (same measures)."""
    if face_side in ['main', 'other_main']:
        # Ensure the face exists before adding CA
        if face_side not in [face['faceSide'] for face in piece.faces]:
            piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
        
        # Calculate target CA size - use reference_size for identical measures across pieces
        if reference_size is not None:
            # Use the dynamically calculated reference size for identical measures
            target_ca_size = reference_size  # Full size coverage (margins applied in add_connection_area)
        else:
            # Fallback: proportional to current piece
            target_ca_size = min(piece.length, piece.height) * 0.95
        
        # For tampo and subtampo, center the CA on each piece's own dimensions
        # This ensures proper centering while maintaining identical CA size
        center_x = piece.length / 2
        center_y = piece.height / 2
        half_size = target_ca_size / 2
        
        x_min = center_x - half_size
        x_max = center_x + half_size
        y_min = center_y - half_size
        y_max = center_y + half_size
        
        # Ensure the CA doesn't exceed face boundaries
        x_min = max(0, x_min)
        x_max = min(piece.length, x_max)
        y_min = max(0, y_min)
        y_max = min(piece.height, y_max)
        
        add_connection_area(piece, face_side, x_min, x_max, y_min, y_max, connection_id)



def select_model_template(pieces: List[Piece]) -> str:
    """Seleciona template com base na espessura com mais furos top (página 4)."""
    thickness_counts = Counter()
    for piece in pieces:
        for face in piece.faces:
            if face['faceSide'] in ['top', 'bottom', 'left', 'right']:
                for hole in face['holes']:
                    if hole['type'] in ['top_corner', 'top_central']:
                        thickness_counts[piece.thickness] += 1
    
    if not thickness_counts:
        return '20'
    
    max_count = max(thickness_counts.values())
    candidates = [t for t, c in thickness_counts.items() if c == max_count]
    return str(min([17, 20, 25, 30], key=lambda x: abs(x - min(candidates))))

def adjust_holes_for_template(pieces: List[Piece], template_thickness: str):
    """Ajusta furos para o template selecionado (página 4)."""
    template_thickness = float(template_thickness)
    for piece in pieces:
        if piece.thickness > template_thickness + 0.05:
            for face in piece.faces:
                if face['faceSide'] in ['top', 'bottom', 'left', 'right']:
                    new_holes = []
                    for hole in face['holes']:
                        if hole['type'] in ['top_corner', 'top_central']:
                            x, y = hole['x'], piece.height / 2
                            for main_face in ['main', 'other_main']:
                                add_hole(piece, main_face, x, y, 'flap_central', hole.get('connectionId'), HOLE_DEPTH_MAIN)
                        else:
                            new_holes.append(hole)
                    face['holes'] = new_holes

def process_illustrator_data(data: dict) -> dict:
    """Processa dados de entrada conforme o guia (páginas 1-6)."""
    pieces_dict = {}
    for layer in data['layers']:
        layer_name = layer['name'].lower()
        for item in layer['items']:
            piece_name = item['nome']
            if piece_name not in pieces_dict:
                pieces_dict[piece_name] = {'vista de cima': {}, 'frontal': {}, 'vista lateral': {}}
            pieces_dict[piece_name][layer_name] = {
                'x': round_to_one_decimal(item['posicao']['x'] * 10),
                'y': round_to_one_decimal(item['posicao']['y'] * 10),
                'width': round_to_one_decimal(item['dimensoes']['largura'] * 10),
                'height': round_to_one_decimal(item['dimensoes']['altura'] * 10)
            }
    
    pieces = []
    for piece_name, views in pieces_dict.items():
        top = views.get('vista de cima', {})
        front = views.get('frontal', {})
        side = views.get('vista lateral', {})
        
        if not (top and front and side):
            continue
        
        dim_x = max(top.get('width', 0), front.get('width', 0))
        dim_y = max(front.get('height', 0), side.get('height', 0))
        dim_z = max(top.get('height', 0), side.get('width', 0))
        
        dimensions = sorted([dim_x, dim_y, dim_z], reverse=True)
        height, length, thickness = dimensions
        
        x_min = top.get('x', 0)
        y_max = front.get('y', 0)
        z_max = top.get('y', 0)
        
        bounds = Bounds3D(
            x_min=round_to_one_decimal(x_min),
            x_max=round_to_one_decimal(x_min + dim_x),
            y_min=round_to_one_decimal(y_max - dim_y),
            y_max=round_to_one_decimal(y_max),
            z_min=round_to_one_decimal(z_max - dim_z),
            z_max=round_to_one_decimal(z_max)
        )
        
        piece = Piece(
            name=piece_name,
            bounds=bounds,
            length=round_to_one_decimal(length),
            height=round_to_one_decimal(height),
            thickness=round_to_one_decimal(thickness),
            quantity=1,
            faces=[]
        )
        
        # Adicionar furos objetivos - skip main faces for fundo piece (only connects via edges)
        if piece_name.lower() == 'fundo':
            # Fundo only gets holes on edge faces, not main faces
            for face_side in ['top', 'bottom', 'left', 'right']:
                add_initial_holes(piece, face_side)
        else:
            # Other pieces get holes on all faces
            for face_side in ['main', 'other_main', 'top', 'bottom', 'left', 'right']:
                add_initial_holes(piece, face_side)
        
        pieces.append(piece)
    
    # Identificar peça principal (maior área = tampo)
    main_piece = max(pieces, key=lambda p: p.length * p.height) if pieces else None
    if not main_piece:
        return {'pieces': []}
    

    
    # Ajustar coordenadas para peça principal na origem
    shift_x = main_piece.bounds.x_min
    shift_y = main_piece.bounds.y_min
    shift_z = main_piece.bounds.z_min
    for piece in pieces:
        piece.bounds.x_min -= shift_x
        piece.bounds.x_max -= shift_x
        piece.bounds.y_min -= shift_y
        piece.bounds.y_max -= shift_y
        piece.bounds.z_min -= shift_z
        piece.bounds.z_max -= shift_z
        piece.bounds = Bounds3D(
            x_min=round_to_one_decimal(piece.bounds.x_min),
            x_max=round_to_one_decimal(piece.bounds.x_max),
            y_min=round_to_one_decimal(piece.bounds.y_min),
            y_max=round_to_one_decimal(piece.bounds.y_max),
            z_min=round_to_one_decimal(piece.bounds.z_min),
            z_max=round_to_one_decimal(piece.bounds.z_max)
        )
    
    # Single-axis connection processing: primarily Z-axis with targeted Y-axis for leg-to-fundo
    connection_id = process_single_axis_connections(pieces, main_piece)
    
    # Create systematic connection areas based on piece type and position
    create_systematic_connection_areas(pieces, connection_id)
    
    # Limpar furos fora das áreas de conexão
    for piece in pieces:
        clean_holes_outside_connection_areas(piece)
    
    # Selecionar e ajustar template
    template_thickness = select_model_template(pieces)
    adjust_holes_for_template(pieces, template_thickness)
    
    # Atualizar targetType
    for piece in pieces:
        for face in piece.faces:
            for hole in face['holes']:
                hole['targetType'] = template_thickness
    
    # Convert pieces to serializable format
    serializable_pieces = []
    for piece in pieces:
        piece_dict = vars(piece)
        piece_dict['bounds'] = vars(piece.bounds)  # Convert Bounds3D to dict
        serializable_pieces.append(piece_dict)
    
    return {'pieces': serializable_pieces}

if __name__ == "__main__":
    try:
        import json
        
        print("🚀 Starting furniture JSON processor...")
        
        # Load input data
        print("Loading input file: illustrator_positions.json")
        try:
            with open('illustrator_positions.json', 'r', encoding='utf-8') as f:
                input_data = json.load(f)
        except UnicodeDecodeError:
            # Try different encodings
            for encoding in ['latin-1', 'cp1252', 'utf-8-sig']:
                try:
                    with open('illustrator_positions.json', 'r', encoding=encoding) as f:
                        input_data = json.load(f)
                    print(f"File loaded with {encoding} encoding")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            else:
                raise Exception("Could not decode file with any common encoding")
        
        # Process the data
        print("Processing furniture data...")
        result = process_illustrator_data(input_data)
        
        # Save output
        print("Saving output to: output_illustrator.json")
        with open('output_illustrator_new.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print("✅ Processing complete!")
        print(f"📊 Processed {len(result.get('pieces', []))} pieces")
        
        # Show summary
        if result.get('pieces'):
            print("\nPieces found:")
            for i, piece in enumerate(result['pieces'], 1):
                print(f"  {i}. {piece['name']} - {piece['length']}x{piece['height']}x{piece['thickness']}mm")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
