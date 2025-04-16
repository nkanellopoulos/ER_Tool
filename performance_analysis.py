"""
Performance analysis utilities for the ER tool.

This module provides functions to analyze and improve performance
of diagram generation and rendering.
"""

import os
import subprocess
import time


def analyze_dot_file(dot_path: str):
    """
    Analyze a DOT file and provide insights.

    Args:
        dot_path: Path to the DOT file to analyze
    """
    if not os.path.exists(dot_path):
        print(f"Error: File {dot_path} does not exist")
        return

    # Get file size
    size_kb = os.path.getsize(dot_path) / 1024
    print(f"DOT file size: {size_kb:.2f} KB")

    # Count nodes and edges
    with open(dot_path, "r") as f:
        content = f.read()

    node_count = content.count(" [label=<")
    edge_count = content.count(" -> ")

    print(f"Node count: {node_count}")
    print(f"Edge count: {edge_count}")

    # Measure rendering time
    print("\nTesting rendering performance...")
    for format in ["svg", "png", "pdf"]:
        output_path = f"{dot_path}.{format}"
        start_time = time.time()

        # Run graphviz
        try:
            result = subprocess.run(
                ["dot", f"-T{format}", dot_path, "-o", output_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

            elapsed = time.time() - start_time

            if result.returncode == 0:
                output_size = os.path.getsize(output_path) / 1024
                print(
                    f"  {format.upper()} rendering: {elapsed:.2f} seconds, file size: {output_size:.2f} KB"
                )
            else:
                print(f"  {format.upper()} rendering failed: {result.stderr}")

            # Clean up
            if os.path.exists(output_path):
                os.unlink(output_path)

        except subprocess.TimeoutExpired:
            print(f"  {format.upper()} rendering timed out after 60 seconds")

    # Provide recommendations
    print("\nRecommendations:")
    if node_count > 50:
        print(
            f"- Consider using overview mode for large diagrams (current: {node_count} tables)"
        )
    if edge_count > 100:
        print(f"- Large number of relationships ({edge_count}) may slow down rendering")
    if size_kb > 500:
        print(
            f"- DOT file is very large ({size_kb:.2f} KB), try reducing the number of tables shown"
        )

    print(
        "\nConsider using PNG format for very large diagrams as it renders faster than SVG"
    )
    print("For filtered views, try to limit to under 30 tables for best performance")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        analyze_dot_file(sys.argv[1])
    else:
        print("Usage: python performance_analysis.py <path_to_dot_file>")
