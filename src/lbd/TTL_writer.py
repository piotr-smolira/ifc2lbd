"""Better TTL writer.

Uses resources (IFC schemas converter to JSON and also presented in Python).
It is to handle SELECT, SET, LIST, ARRAY.

"""

from collections import defaultdict
from typing import Any, Dict, Iterator, Optional, Tuple, List
from pathlib import Path
import ifcopenshell
import datetime
import sys

# Add resources directory for schema imports
sys.path.append(str(Path(__file__).parent.parent.parent / "resources/ifc_schemas"))


# ============================================================================
# SCHEMA REGISTRY
# ============================================================================

class SchemaRegistry:
    """Optional unified interface to schema metadata.
    
    Combines collection types and SELECT types in one place.
    """
    
    def __init__(self, schema_name: str):
        """Initialize registry for given schema.
        
        Args:
            schema_name: Schema identifier like 'IFC4X3_ADD2'
        """
        self.schema_name = schema_name.lower()
        self.collection_types = self._load_collection_types()
        # SELECT types will be loaded when available
        self.select_types = {}  # Future: self._load_select_types()
    
    def _load_collection_types(self) -> dict:
        """Load collection type map for schema."""
        if "4x3" in self.schema_name:
            from ifc4x3_add2_collection_types import COLLECTION_TYPE_MAP
        elif "ifc4" in self.schema_name:
            from ifc4_collection_types import COLLECTION_TYPE_MAP
        elif "2x3" in self.schema_name:
            from ifc2x3_collection_types import COLLECTION_TYPE_MAP
        else:
            raise ValueError(f"Unknown schema: {self.schema_name}")
        return COLLECTION_TYPE_MAP
    
    def get_collection_type(self, entity_type: str, attr_name: str) -> Optional[str]:
        """Get collection type (LIST/SET/ARRAY) for an attribute.
        
        Returns:
            'LIST', 'SET', 'ARRAY', or None if not a collection
        """
        return self.collection_types.get(entity_type, {}).get(attr_name)
    
    def is_select_attribute(self, entity_type: str, attr_name: str) -> bool:
        """Check if attribute uses SELECT type (future implementation)."""
        return attr_name in self.select_types.get(entity_type, {})


# ============================================================================
# VALUE FORMATTING 
# ============================================================================

def format_literal(value: Any, scientific_floats: bool = True) -> str:
    """Format a primitive value with proper XSD typing.
    
    Args:
        value: Python primitive (str, int, float, bool)
        scientific_floats: If True, format floats in scientific notation (e.g., 5.84E-1)
        
    Returns:
        Formatted TTL literal with XSD type if applicable
    """
    val_type = type(value)
    
    if val_type is str:
        return f'"{value}"'
    elif val_type is bool:
        return f'{str(value).lower()}'
    elif val_type is int:
        return f'{value}'
    elif val_type is float:
        if scientific_floats:
            # Format with scientific notation like: 5.84313725490196E-1
            formatted = f"{value:.15E}".replace('E+', 'E').replace('E-0', 'E-').replace('E0', 'E')
            return f'"{formatted}"^^xsd:double'
        else:
            return f'"{value}"^^xsd:double'
    else:
        return f'"{str(value)}"'


def format_collection_items(items: list, scientific_floats: bool = True) -> str:
    """Format items for RDF collection syntax: ( item1 item2 ... )
    
    Handles nested collections recursively.
    
    Args:
        items: List of values to format
        scientific_floats: If True, format floats in scientific notation
        
    Returns:
        Formatted RDF collection string
    """
    if not items:
        return "()"
    
    formatted = []
    for item in items:
        if isinstance(item, dict) and 'ref' in item:
            formatted.append(f"inst:ref_{item['ref']}")
        elif isinstance(item, (list, tuple)):
            # Recursive: nested collection
            formatted.append(format_collection_items(item, scientific_floats))
        else:
            formatted.append(format_literal(item, scientific_floats))
    
    return f"( {' '.join(formatted)} )"


# ============================================================================
# SELECT TYPE HANDLER
# ============================================================================

class SelectTypeHandler:
    """Handles SELECT type attributes that create separate typed entities.
    
    SELECT types in IFC (like IfcValue, IfcUnit) create additional entities:
    
    Input:  {'NominalValue': {'type': 'IfcLabel', 'value': 'Wall'}}
    Output: 
        - Main entity: ifc:NominalValue inst:ref_123_t1
        - Typed entity: inst:ref_123_t1 ifc:IfcLabel "Wall" .
    """
    
    def __init__(self, entity_id: int, ifc_prefix: str, scientific_floats: bool = True):
        """Initialize handler for a specific entity.
        
        Args:
            entity_id: ID of the main entity being processed
            ifc_prefix: Prefix for IFC types (e.g., 'ifc:')
            scientific_floats: If True, format floats in scientific notation
        """
        self.entity_id = entity_id
        self.ifc_prefix = ifc_prefix
        self.scientific_floats = scientific_floats
        self.counter = 0
        self.typed_triples: List[str] = []  # Accumulate separate entity definitions
    
    def process_select_value(self, select_dict: dict) -> str:
        """Process a SELECT typed value, return reference ID.
        
        Args:
            select_dict: Dict with 'type' and 'value' keys
            
        Returns:
            Reference ID to use in main entity (e.g., 'inst:ref_123_t1')
        """
        self.counter += 1
        typed_id = f"inst:ref_{self.entity_id}_t{self.counter}"
        
        ifc_type = select_dict['type']
        typed_val = select_dict['value']
        
        # Format the value appropriately
        if isinstance(typed_val, (list, tuple)):
            val_str = format_collection_items(typed_val, self.scientific_floats)
        else:
            val_str = format_literal(typed_val, self.scientific_floats)
        
        # Store the typed entity triple
        self.typed_triples.append(
            f"{typed_id} {self.ifc_prefix}{ifc_type} {val_str} .\n"
        )
        
        return typed_id
    
    def get_typed_triples(self) -> List[str]:
        """Get all accumulated typed entity triples."""
        return self.typed_triples


# ============================================================================
# COLLECTION HANDLER
# ============================================================================

class CollectionHandler:
    """Handles LIST/SET/ARRAY attributes.
    
    Different collection types have different TTL representations:
    - LIST/ARRAY: RDF collection ( item1 item2 item3 )
    - SET: Comma-separated object list
    """
    
    def __init__(self, select_handler: SelectTypeHandler, ifc_prefix: str, scientific_floats: bool = True):
        """Initialize handler.
        
        Args:
            select_handler: Handler for SELECT types (for items that need it)
            ifc_prefix: Prefix for IFC types
            scientific_floats: If True, format floats in scientific notation
        """
        self.select_handler = select_handler
        self.ifc_prefix = ifc_prefix
        self.scientific_floats = scientific_floats
    
    def process_collection(self, items: list, coll_type: Optional[str]) -> Tuple[str, int]:
        """Process a collection attribute.
        
        Args:
            items: List of items from stream2
            coll_type: 'LIST', 'SET', 'ARRAY', or None
            
        Returns:
            Tuple of (formatted_output, triple_count)
        """
        if not items:
            return "()", 1
        
        # Process all items
        formatted_items = []
        nested_sizes = []
        
        for item in items:
            formatted, size = self._process_single_item(item)
            formatted_items.append(formatted)
            if size:
                nested_sizes.append(size)
        
        # Format based on collection type
        if coll_type == 'SET':
            # Comma-separated for unordered sets
            output = ', '.join(formatted_items)
            triple_count = len(formatted_items)
        elif coll_type in ('LIST', 'ARRAY'):
            # RDF collection for ordered lists
            output = f"( {' '.join(formatted_items)} )"
            triple_count = 1 + (2 * len(formatted_items))
            # Add nested collection triples
            for n in nested_sizes:
                triple_count += 2 * n
        else:
            # Fallback: check if all items are entity references
            all_refs = all(isinstance(it, str) and it.startswith('inst:ref_') 
                          for it in formatted_items)
            
            if all_refs:
                # All entity references - comma-separated
                output = ', '.join(formatted_items)
                triple_count = len(formatted_items)
            else:
                # Mixed types - use RDF collection
                output = f"( {' '.join(formatted_items)} )"
                triple_count = 1 + (2 * len(formatted_items))
                for n in nested_sizes:
                    triple_count += 2 * n
        
        return output, triple_count
    
    def _process_single_item(self, item: Any) -> Tuple[str, int]:
        """Process a single item in a collection.
        
        Args:
            item: Item from collection
            
        Returns:
            Tuple of (formatted_item, nested_size_or_0)
        """
        item_type = type(item)
        
        if item_type is dict:
            ref = item.get('ref')
            if ref:
                return f"inst:ref_{ref}", 0
            elif 'type' in item and 'value' in item:
                # SELECT type - delegate to handler
                typed_id = self.select_handler.process_select_value(item)
                return typed_id, 0
        elif item_type in (list, tuple):
            # Nested collection
            nested = format_collection_items(item, self.scientific_floats)
            return nested, len(item)
        else:
            # Primitive literal
            return format_literal(item, self.scientific_floats), 0


# ============================================================================
# MAIN ATTRIBUTE PROCESSOR
# ============================================================================

class AttributeProcessor:
    """Main processor for entity attributes.
    
    Coordinates between SelectTypeHandler and CollectionHandler
    to process all attribute types correctly.
    """
    
    def __init__(self, entity_id: int, entity_type: str, 
                 ifc_prefix: str, registry: SchemaRegistry, scientific_floats: bool = True):
        """Initialize processor for a specific entity.
        
        Args:
            entity_id: Entity ID
            entity_type: Entity type (e.g., 'IfcWall')
            ifc_prefix: Prefix for IFC types
            registry: Schema registry for metadata lookups
            scientific_floats: If True, format floats in scientific notation
        """
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.ifc_prefix = ifc_prefix
        self.registry = registry
        self.scientific_floats = scientific_floats
        
        # Specialized handlers
        self.select_handler = SelectTypeHandler(entity_id, ifc_prefix, scientific_floats)
        self.collection_handler = CollectionHandler(self.select_handler, ifc_prefix, scientific_floats)
    
    def process_attribute(self, key: str, value: Any) -> Tuple[str, int]:
        """Process a single attribute.
        
        Args:
            key: Attribute name
            value: Attribute value from stream2
            
        Returns:
            Tuple of (formatted_triple_fragment, triple_count)
        """
        val_type = type(value)
        
        # Get collection type from schema
        coll_type = self.registry.get_collection_type(self.entity_type, key)
        
        # Handle collections
        if val_type in (list, tuple):
            output, count = self.collection_handler.process_collection(value, coll_type)
            return f" ;\n\t{self.ifc_prefix}{key} {output}", count
        
        # Handle dictionaries (references or SELECT types)
        elif val_type is dict:
            ref = value.get('ref')
            if ref:
                return f" ;\n\t{self.ifc_prefix}{key} inst:ref_{ref}", 1
            elif 'type' in value and 'value' in value:
                typed_id = self.select_handler.process_select_value(value)
                return f" ;\n\t{self.ifc_prefix}{key} {typed_id}", 1
        
        # Handle primitive literals
        else:
            literal = format_literal(value, self.scientific_floats)
            return f" ;\n\t{self.ifc_prefix}{key} {literal}", 1
    
    def get_typed_triples(self) -> List[str]:
        """Get all accumulated typed entity triples."""
        return self.select_handler.get_typed_triples()


# ============================================================================
# ROCKSDB ADAPTER
# ============================================================================

def normalize_value(value):
    """Recursively normalize values from RocksDB to stream2 format."""
    if hasattr(value, 'id'):
        return {'ref': value.id()}
    elif isinstance(value, (list, tuple)):
        return type(value)(normalize_value(v) for v in value)
    else:
        return value


def entity_to_dict(entity) -> Dict[str, Any]:
    """Convert RocksDB entity to stream2 dictionary format."""
    try:
        info = entity.get_info()
    except Exception as e:
        print(f"Warning: Failed to get info for entity #{entity.id()}: {e}", file=sys.stderr)
        info = {}
    
    normalized_info = {k: normalize_value(v) for k, v in info.items()}
    normalized_info['id'] = entity.id()
    normalized_info['type'] = entity.is_a()
    
    return normalized_info


def get_entity_stream(source_path: str) -> Iterator[Dict[str, Any]]:
    """Unified interface for both IFC and RocksDB sources."""
    source_path_obj = Path(source_path)
    
    if source_path.endswith('.rdb') or source_path_obj.is_dir():
        # RocksDB source
        fi = ifcopenshell.open(source_path)
        for entity in fi:
            yield entity_to_dict(entity)
    else:
        # IFC source
        yield from ifcopenshell.stream2(source_path)


# ============================================================================
# HEADER WRITER
# ============================================================================

def write_header(namespaces: Dict[str, str]) -> str:
    """Generate TTL header with metadata and namespace declarations.
    
    Args:
        namespaces: Dict of prefix -> URI mappings
        
    Returns:
        Formatted header string
    """
    BASE = namespaces.get("BASE", "http://example.org/base#")
    
    lines = [
        "# Turtle TTL output generated by refactored LBD writer.\n",
        f"# Generated on: {datetime.datetime.now().isoformat()}\n",
        f"# baseURI: {BASE}\n",
        f"# imports: {namespaces.get('mifc', namespaces.get('ifc'))}\n",
        "\n",
        f"BASE <{BASE}>\n"
    ]
    
    for prefix, uri in namespaces.items():
        if prefix != "BASE":
            lines.append(f"PREFIX {prefix}: <{uri}>\n")
    
    lines.append("\n")
    lines.append("inst:\ta\towl:Ontology ;\n")
    lines.append("\towl:imports\tifc: .\n\n")
    
    return ''.join(lines)


# ============================================================================
# MAIN WRITER FUNCTION
# ============================================================================

def string_stream_refactored(source_path: str, output_ttl_path: str, 
                             namespaces: Dict[str, str], 
                             buffer_size: int = 100000,
                             scientific_floats: bool = True) -> dict:
    """Refactored streaming writer.
    
    Args:
        source_path: Path to IFC file (.ifc) or RocksDB (.rdb)
        output_ttl_path: Path to output TTL file
        namespaces: Namespace dictionary
        buffer_size: Number of entities to buffer before flushing
        scientific_floats: If True, format floats in scientific notation (default: False)
        
    Returns:
        Dict with metrics (triple_count, entities_processed)
    """
    # Detect schema from source
    if source_path.endswith('.rdb') or Path(source_path).is_dir():
        fi = ifcopenshell.open(source_path)
        schema_name = fi.schema
    else:
        # For IFC files, we need to peek at first entity
        for entity_dict in ifcopenshell.stream2(source_path):
            # Just read schema from file metadata
            # For now, hardcode or pass as parameter
            schema_name = "IFC4X3_ADD2"
            break
    
    # Initialize schema registry
    registry = SchemaRegistry(schema_name)
    
    triple_count = 0
    entities_processed = 0
    buffer = []
    ifc_prefix = 'ifc:'
    
    with open(output_ttl_path, 'w', encoding='utf-8') as f:
        # Write header
        f.write(write_header(namespaces))
        triple_count += 2
        
        # Process entities
        for instance_dict in get_entity_stream(source_path):
            entity_id = instance_dict.get('id')
            entity_type = instance_dict.get('type')
            
            if not entity_id or entity_id == 0 or not entity_type:
                continue
            
            entities_processed += 1
            
            # Create processor for this entity
            processor = AttributeProcessor(
                entity_id, entity_type, ifc_prefix, registry, scientific_floats
            )
            
            # Build entity
            entity_parts = [f"inst:ref_{entity_id} a {ifc_prefix}{entity_type}"]
            triple_count += 1
            
            # Process all attributes
            for key, value in instance_dict.items():
                if key in ('id', 'type') or value is None:
                    continue
                
                fragment, count = processor.process_attribute(key, value)
                entity_parts.append(fragment)
                triple_count += count
            
            # Write main entity
            buffer.append(''.join(entity_parts) + ' .\n\n')
            
            # Write typed value entities (SELECT types)
            buffer.extend(processor.get_typed_triples())
            
            # Flush buffer periodically
            if len(buffer) >= buffer_size:
                f.write(''.join(buffer))
                buffer.clear()
        
        # Final flush
        if buffer:
            f.write(''.join(buffer))
    
    return {
        'triples_written': triple_count,
        'entities_processed': entities_processed
    }


# ============================================================================
# Just functions approach.
# ============================================================================

def string_stream_functional(source_path: str, output_ttl_path: str, 
                             namespaces: Dict[str, str]) -> dict:
    """Alternative functional implementation (no classes).
    """
    registry = SchemaRegistry("IFC4X3_ADD2")
    triple_count = 0
    entities_processed = 0
    ifc_prefix = 'ifc:'
    
    # Closure variables for SELECT handler
    typed_value_counter = 0
    typed_triples = []
    
    def process_select(entity_id: int, select_dict: dict) -> str:
        nonlocal typed_value_counter
        typed_value_counter += 1
        typed_id = f"inst:ref_{entity_id}_t{typed_value_counter}"
        
        ifc_type = select_dict['type']
        val = select_dict['value']
        val_str = format_collection_items(val) if isinstance(val, (list, tuple)) else format_literal(val)
        
        typed_triples.append(f"{typed_id} {ifc_prefix}{ifc_type} {val_str} .\n")
        return typed_id
    
    def process_item(entity_id: int, item: Any) -> Tuple[str, int]:
        if isinstance(item, dict):
            if 'ref' in item:
                return f"inst:ref_{item['ref']}", 0
            elif 'type' in item and 'value' in item:
                return process_select(entity_id, item), 0
        elif isinstance(item, (list, tuple)):
            return format_collection_items(item), len(item)
        else:
            return format_literal(item), 0
    
    def process_collection(entity_id: int, items: list, coll_type: Optional[str]) -> Tuple[str, int]:
        if not items:
            return "()", 1
        
        formatted_items = []
        nested_sizes = []
        
        for item in items:
            fmt, size = process_item(entity_id, item)
            formatted_items.append(fmt)
            if size:
                nested_sizes.append(size)
        
        if coll_type == 'SET':
            return ', '.join(formatted_items), len(formatted_items)
        else:
            output = f"( {' '.join(formatted_items)} )"
            count = 1 + (2 * len(formatted_items)) + sum(2 * n for n in nested_sizes)
            return output, count
    
    with open(output_ttl_path, 'w', encoding='utf-8') as f:
        f.write(write_header(namespaces))
        triple_count += 2
        
        for instance_dict in get_entity_stream(source_path):
            entity_id = instance_dict.get('id')
            entity_type = instance_dict.get('type')
            
            if not entity_id or entity_id == 0 or not entity_type:
                continue
            
            entities_processed += 1
            typed_value_counter = 0  # Reset per entity
            typed_triples.clear()
            
            parts = [f"inst:ref_{entity_id} a {ifc_prefix}{entity_type}"]
            triple_count += 1
            
            for key, value in instance_dict.items():
                if key in ('id', 'type') or value is None:
                    continue
                
                val_type = type(value)
                coll_type = registry.get_collection_type(entity_type, key)
                
                if val_type in (list, tuple):
                    output, count = process_collection(entity_id, value, coll_type)
                    parts.append(f" ;\n\t{ifc_prefix}{key} {output}")
                    triple_count += count
                elif val_type is dict:
                    if 'ref' in value:
                        parts.append(f" ;\n\t{ifc_prefix}{key} inst:ref_{value['ref']}")
                        triple_count += 1
                    elif 'type' in value and 'value' in value:
                        typed_id = process_select(entity_id, value)
                        parts.append(f" ;\n\t{ifc_prefix}{key} {typed_id}")
                        triple_count += 1
                else:
                    parts.append(f" ;\n\t{ifc_prefix}{key} {format_literal(value)}")
                    triple_count += 1
            
            f.write(''.join(parts) + ' .\n\n')
            f.writelines(typed_triples)
    
    return {'triples_written': triple_count, 'entities_processed': entities_processed}
