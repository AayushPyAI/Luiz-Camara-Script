import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from collections import Counter

# Configurações (valores do guia)
MARGIN = 0.01  # Margem em mm (página 4)
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

def get_connection_faces(piece_1: Piece, piece_2: Piece) -> Optional[Tuple[str, str, str, float, float, float, float]]:
    """Identifica faces conectadas e limites da sobreposição (página 2)."""
    x_overlap = get_overlap(piece_1.bounds.x_min, piece_1.bounds.x_max, piece_2.bounds.x_min, piece_2.bounds.x_max)
    y_overlap = get_overlap(piece_1.bounds.y_min, piece_1.bounds.y_max, piece_2.bounds.y_min, piece_2.bounds.y_max)
    z_overlap = get_overlap(piece_1.bounds.z_min, piece_1.bounds.z_max, piece_2.bounds.z_min, piece_2.bounds.z_max)
    
    # Check for table-top-to-leg connections (piece_1 above piece_2)
    if (y_overlap is None and piece_1.bounds.y_min >= piece_2.bounds.y_max and 
        x_overlap is not None and z_overlap is not None):
        # Table top sitting on leg: main face of piece_1 connects to top face of piece_2
        x_min, x_max = x_overlap
        z_min, z_max = z_overlap
        return 'y', 'main', 'top', x_min, x_max, z_min, z_max
    
    # Original touching piece logic
    if y_overlap is None and abs(piece_1.bounds.y_max - piece_2.bounds.y_min) < 0.05:
        # Conexão face-topo: main do tampo com top da perna
        x_min, x_max = x_overlap if x_overlap else (piece_2.bounds.x_min, piece_2.bounds.x_max)
        z_min, z_max = z_overlap if z_overlap else (piece_2.bounds.z_min, piece_2.bounds.z_max)
        return 'y', 'main', 'top', x_min, x_max, z_min, z_max
    if x_overlap is None and abs(piece_1.bounds.x_max - piece_2.bounds.x_min) < 0.05:
        # Conexão lateral: right do tampo com left da perna
        y_min, y_max = y_overlap if y_overlap else (piece_2.bounds.y_min, piece_2.bounds.y_max)
        z_min, z_max = z_overlap if z_overlap else (piece_2.bounds.z_min, piece_2.bounds.z_max)
        return 'x', 'right', 'left', y_min, y_max, z_min, z_max
    if z_overlap is None and abs(piece_1.bounds.z_max - piece_2.bounds.z_min) < 0.05:
        # Conexão vertical: main do tampo com top da perna
        x_min, x_max = x_overlap if x_overlap else (piece_2.bounds.x_min, piece_2.bounds.x_max)
        y_min, y_max = y_overlap if y_overlap else (piece_2.bounds.y_min, piece_2.bounds.y_max)
        return 'z', 'main', 'top', x_min, x_max, y_min, y_max
    return None

def add_connection_area(piece: Piece, face_side: str, x_min: float, x_max: float, y_min: float, y_max: float, connection_id: int):
    """Adiciona área de conexão com margem de 0.01mm (página 4)."""
    if face_side not in [face['faceSide'] for face in piece.faces]:
        piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
    
    if abs(x_min - piece.bounds.x_min) < 0.05:
        x_min += MARGIN
    if abs(x_max - piece.bounds.x_max) < 0.05:
        x_max -= MARGIN
    if abs(y_min - piece.bounds.y_min) < 0.05:
        y_min += MARGIN
    if abs(y_max - piece.bounds.y_max) < 0.05:
        y_max -= MARGIN
    
    area = {
        'x_min': round_to_one_decimal(x_min),
        'y_min': round_to_one_decimal(y_min),
        'x_max': round_to_one_decimal(x_max),
        'y_max': round_to_one_decimal(y_max),
        'fill': 'black',
        'opacity': 0.05,
        'connectionId': connection_id
    }
    
    for face in piece.faces:
        if face['faceSide'] == face_side:
            face['connectionAreas'].append(area)

def add_hole(piece: Piece, face_side: str, x: float, y: float, hole_type: str, connection_id: Optional[int], depth: float):
    """Adiciona um furo com hardware apropriado (página 4)."""
    if face_side not in [face['faceSide'] for face in piece.faces]:
        piece.faces.append({'faceSide': face_side, 'holes': [], 'connectionAreas': []})
    
    ferragem = 'dowel_M_with_glue' if hole_type in ['flap_corner', 'flap_central', 'face_central'] else \
               'dowel_G_with_glue' if hole_type in ['singer_flap', 'singer_central', 'singer_channel'] else \
               'glue'
    
    hole = {
        'x': round_to_one_decimal(x),
        'y': round_to_one_decimal(y),
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
    
    # For Y-axis connections (table top to leg): min_1,max_1 = X overlap, min_2,max_2 = Z overlap
    if axis == 'y':
        # Piece 1 (table top) main face connection area
        if face_1 in ['main', 'other_main']:
            x_min_1, x_max_1 = min_1, max_1  # X overlap
            y_min_1, y_max_1 = min_2, max_2  # Z overlap
        
        # Piece 2 (leg) top face connection area  
        if face_2 in ['top', 'bottom']:
            x_min_2, x_max_2 = min_1, max_1  # X overlap (relative to leg's coordinate system)
            y_min_2, y_max_2 = min_2, max_2  # Z overlap (relative to leg's coordinate system)
            
            # Convert to leg's local coordinates
            x_min_2 = x_min_2 - piece_2.bounds.x_min
            x_max_2 = x_max_2 - piece_2.bounds.x_min  
            y_min_2 = y_min_2 - piece_2.bounds.z_min
            y_max_2 = y_max_2 - piece_2.bounds.z_min
    
    # For other connection types (keep original logic for now)
    elif axis == 'x':
        if face_1 in ['main', 'other_main']:
            x_min_1, x_max_1 = min_1, max_1
            y_min_1, y_max_1 = 0.0, piece_1.thickness
        else:
            x_min_1, x_max_1 = 0.0, piece_1.length
            y_min_1, y_max_1 = min_1, max_1
            
        if face_2 in ['left', 'right']:
            x_min_2, x_max_2 = 0.0, piece_2.thickness
            y_min_2, y_max_2 = min_2, max_2
    
    elif axis == 'z':
        if face_1 in ['main', 'other_main']:
            x_min_1, x_max_1 = min_1, max_1
            y_min_1, y_max_1 = 0.0, piece_1.thickness
        else:
            x_min_1, x_max_1 = 0.0, piece_1.length
            y_min_1, y_max_1 = min_2, max_2
            
        if face_2 in ['top', 'bottom']:
            x_min_2, x_max_2 = min_1, max_1
            y_min_2, y_max_2 = 0.0, piece_2.thickness
    
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
        
        # Adicionar furos objetivos em todas as faces
        for face_side in ['main', 'other_main', 'top', 'bottom', 'left', 'right']:
            add_initial_holes(piece, face_side)
        
        pieces.append(piece)
    
    # Identificar peça principal
    main_piece = max(pieces, key=lambda p: p.height) if pieces else None
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
    
    # Criar conexões
    connection_id = 1
    for piece in pieces:
        if piece != main_piece:
            connection = get_connection_faces(main_piece, piece)
            if connection:
                create_connection(main_piece, piece, connection_id)
                connection_id += 1
    
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
