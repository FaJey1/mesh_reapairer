from __future__ import annotations

import argparse
from pathlib import Path

from mesh_reapairer import repair_mesh
from mesh_reapairer.infrastructure.io import load_mesh, save_mesh


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments for the mesh_reapairer CLI.
    """
    parser = argparse.ArgumentParser(
        prog="mesh-reapairer",
        description="Detect and repair self-intersections in polygonal meshes.",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to the input mesh file (JSON format).",
    )
    parser.add_argument(
        "output",
        type=str,
        help="Path to write the repaired mesh (JSON format).",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Enable visualization of the repair process (reserved for future use).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point used by the console script.
    """
    args = parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    mesh = load_mesh(input_path)
    repaired = repair_mesh(mesh, enable_visualization=args.visualize)
    save_mesh(repaired, output_path)


if __name__ == "__main__":
    main()
