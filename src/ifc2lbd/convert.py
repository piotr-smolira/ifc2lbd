"""Core conversion logic from IFC to LBD Turtle format."""
import itertools
import sys
from pathlib import Path
import time
import cProfile
import pstats
from io import StringIO
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import ifcopenshell
from ifc.ifc_options import load_ifc, stream_ifc
from lbd.namespaces import get_namespaces
from lbd.TTL_writer_strings_spf import string_writer_mini_ifcOWL, string_writer_ifcOWL
from lbd.TTL_writer_strings_stream import string_writer_mini_ifcOWL_stream
from lbd.TTL_writer import string_stream_refactored, string_stream_functional
from .geometry import geometry_processor

# Map converter names to writer functions (for loaded models)
CONVERTERS = {
    "mini_ifcowl": string_writer_mini_ifcOWL,
    "ifcowl": string_writer_ifcOWL,
    "mini_ifcowl_wkt": string_writer_mini_ifcOWL,
    "ifcowl_wkt": string_writer_ifcOWL,
    # "ifcowl_express": string_writer_ifcowl_express,s
}

# Map converter names to streaming writer functions
STREAM_CONVERTERS = {
    "mini_ifcowl": string_writer_mini_ifcOWL_stream,
    "mini_ifcowl_complete": string_stream_refactored,
    "mini_ifcowl_complete2": string_stream_functional,
    # "ifcowl_express": Not yet implemented for streaming
}

WITH_GEOMETRY_PROCESSING = {"mini_ifcowl_wkt", "ifcowl_wkt"}

def ifc_to_lbd_ttl(input_ifc_path: str, output_ttl_path: str, stream: bool = False, verbose: bool = False, profile: bool = False, converter: str = "mini_ifcowl", return_metrics: bool = False, single_pass: bool = False) -> dict | None:
    """
    Convert a single IFC file to LBD Turtle format.
    
    Args:
        input_ifc_path: Path to input IFC file
        output_ttl_path: Path to output TTL file
        stream: If True, stream the IFC file instead of loading to memory
        verbose: If True, print timing information
        profile: If True, run with cProfile and save stats
        converter: Which converter to use ('mini_ifcowl', 'ifcowl', 'mini_reference')
        return_metrics: If True, return a dict with conversion metrics for benchmarking
        single_pass: If True, skip entity type mapping (only for mini_ifcowl_optimized)
        
    Returns:
        dict with metrics if return_metrics=True, otherwise None
    """
    if stream and converter not in STREAM_CONVERTERS:
        raise ValueError(f"Streaming not yet implemented for converter '{converter}'. Available for streaming: {list(STREAM_CONVERTERS.keys())}")
    
    if not stream and converter not in CONVERTERS:
        raise ValueError(f"Unknown converter '{converter}'. Available: {list(CONVERTERS.keys())}")
    
    if profile:
        profiler = cProfile.Profile()
        profiler.enable()
    
    start_total = time.time()

    proc: Optional[geometry_processor] = None
    
    # Load or stream IFC model
    start_load = time.time()
    if stream:
        ifc_model_or_iterator, file_path = stream_ifc(input_ifc_path)
        # For streaming, we pass the file path to get schema
        schema_source = file_path if file_path else ifc_model_or_iterator
    else:
        ifc_model_or_iterator = load_ifc(input_ifc_path)
        schema_source = ifc_model_or_iterator
    
    load_time = time.time() - start_load
    if verbose:
        print(f"{'Streaming' if stream else 'Loading'} IFC: {load_time:.3f}s")
    
    # Get namespaces for conversion
    namespaces = get_namespaces(schema_source)
    if not stream and converter in WITH_GEOMETRY_PROCESSING:
        proc = geometry_processor(ifc_model_or_iterator)
        proc.process(namespaces.get("inst"))
        proc.remove_from_file()

    # Writer
    start_write = time.time()
    if stream:
        writer_function = STREAM_CONVERTERS[converter]
        # Pass use_typed_refs parameter for optimized converter
        if converter == "mini_ifcowl_optimized":
            writer_result = writer_function(input_ifc_path, output_ttl_path, namespaces, use_typed_refs=not single_pass)
        else:
            writer_result = writer_function(input_ifc_path, output_ttl_path, namespaces)
    else:
        writer_function = CONVERTERS[converter]
        writer_result = writer_function(ifc_model_or_iterator, output_ttl_path, namespaces, geometry=proc)
    
    write_time = time.time() - start_write
    if verbose:
        print(f"Writing TTL: {write_time:.3f}s")
    
    total_time = time.time() - start_total
    if verbose:
        print(f"Total conversion: {total_time:.3f}s")
    
    if profile:
        profiler.disable()
        stats_file = output_ttl_path.replace('.ttl', '_profile.stats')
        profiler.dump_stats(stats_file)
        
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print()
        print("="*80)
        print("TOP 20 FUNCTIONS BY CUMULATIVE TIME:")
        print("="*80)
        print(s.getvalue())
        print(f"Profile stats saved to: {stats_file}")
        print(f"To analyze: python -m pstats {stats_file}")
    
    # Return metrics if requested (for benchmarking)
    if return_metrics:
        metrics = {
            'input_file': input_ifc_path,
            'output_file': output_ttl_path,
            'stream_mode': stream,
            'converter': converter,
            'load_time': load_time,
            'write_time': write_time,
            'total_time': total_time,
        }
        # Merge in writer-specific metrics (entities_processed, triples_written)
        if writer_result:
            metrics.update(writer_result)
        return metrics
    
    return None

    if return_metrics:
        return {
            'load_time': load_time,
            'write_time': write_time,
            'total_time': total_time
        }


# Not there yet.
def ifc_to_lbd_trig(input_ifc_path: str, output_trig_path: str, stream: bool = False, verbose: bool = False, profile: bool = False, converter: str = "mini_ifcowl") -> None:
    """
    Convert a single IFC file to LBD (Linked Building Data) TriG format.
    Used when processing multiple files to keep each in separate named graphs.
    
    Args:
        input_ifc_path: Path to input IFC file
        output_trig_path: Path to output TRIG file
        stream: If True, stream the IFC file instead of loading to memory
        verbose: If True, print timing information
        profile: If True, run with cProfile and save stats
        converter: Which converter to use ('mini_ifcowl', 'ifcowl', 'mini_reference')
    """
    if converter not in CONVERTERS:
        raise ValueError(f"Unknown converter '{converter}'. Available: {list(CONVERTERS.keys())}")
    
    if stream:
        ifc_model = stream_ifc(input_ifc_path)
    else:
        ifc_model = load_ifc(input_ifc_path)
    
    namespaces = get_namespaces(ifc_model)
    
    file_name = Path(input_ifc_path).stem
    
    with open(output_trig_path, 'w', encoding='utf-8') as f:
        f.write("# LBD TriG output\n")
        f.write(f"# Converted from: {input_ifc_path}\n")
        f.write(f"# Mode: {'Streaming' if stream else 'Loaded to memory'}\n")
        f.write("\n")
        f.write("@prefix lbd: <https://w3id.org/lbd#> .\n")
        f.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")
        f.write("\n")
        f.write(f"<http://example.org/graph/{file_name}> {{\n")
        f.write("    # TODO: Add actual conversion logic using string_writer_mini_ifcOWL\n")
        f.write("}\n")
